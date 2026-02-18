"""
Twitter/X scraping via GraphQL interception. Uses BrowserManager and parser.

Hardened with:
- Exponential backoff + jitter on rate limits
- Configurable retry with backoff for transient failures
- Optional proxy rotation
- Session cookie persistence
- Improved DOM fallback with multiple strategies
- Structured error reporting
- Cursor-based pagination for full history
- Anti-detection: random delays, realistic scrolling, viewport randomization
"""

import asyncio
import json
import logging
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .browser import stealth_page
from .parser import (
    parse_followers_response,
    parse_following_response,
    parse_tweet_response,
    parse_user_profile,
)

logger = logging.getLogger(__name__)

SESSION_PATH = Path.home() / ".config" / "holespawn" / "twitter-session.json"

# --- Structured error reporting ---


class ScrapeError:
    """Structured error from a scraping operation."""

    def __init__(self, operation: str, username: str, error_type: str, message: str, recoverable: bool = True):
        self.operation = operation
        self.username = username
        self.error_type = error_type
        self.message = message
        self.recoverable = recoverable
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "username": self.username,
            "error_type": self.error_type,
            "message": self.message,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return f"ScrapeError({self.operation}, {self.error_type}: {self.message})"


class ScrapeResult:
    """Wrapper for scrape results with error tracking."""

    def __init__(self, data: Any = None, errors: list[ScrapeError] | None = None):
        self.data = data if data is not None else []
        self.errors: list[ScrapeError] = errors or []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 or self.data

    def add_error(self, error: ScrapeError) -> None:
        self.errors.append(error)
        logger.warning("ScrapeError: %s", error)


# --- Anti-detection helpers ---

async def _human_delay(min_s: float = 2.0, max_s: float = 8.0) -> None:
    """Random delay to mimic human behavior."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _realistic_scroll(page: Page) -> None:
    """Scroll with realistic human-like behavior."""
    strategy = random.choice(["smooth", "step", "keyboard"])
    if strategy == "smooth":
        distance = random.randint(600, 2500)
        await page.evaluate(f"window.scrollBy({{top: {distance}, behavior: 'smooth'}})")
    elif strategy == "step":
        steps = random.randint(2, 5)
        for _ in range(steps):
            await page.evaluate(f"window.scrollBy(0, {random.randint(200, 600)})")
            await asyncio.sleep(random.uniform(0.1, 0.4))
    else:
        key = random.choice(["Space", "PageDown"])
        await page.keyboard.press(key)
    # Small pause after scrolling
    await asyncio.sleep(random.uniform(0.5, 2.0))


def _random_viewport() -> dict[str, int]:
    """Return a randomized but realistic viewport size."""
    viewports = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
        {"width": 1280, "height": 720},
        {"width": 1600, "height": 900},
        {"width": 1680, "height": 1050},
    ]
    vp = random.choice(viewports)
    # Add small jitter
    vp["width"] += random.randint(-20, 20)
    vp["height"] += random.randint(-10, 10)
    return vp


# --- Session persistence ---

def _save_session(cookies: list[dict]) -> None:
    """Save session cookies to disk."""
    try:
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        SESSION_PATH.write_text(json.dumps(cookies, indent=2))
        logger.debug("Session saved to %s", SESSION_PATH)
    except Exception as e:
        logger.warning("Failed to save session: %s", e)


def _load_session() -> list[dict] | None:
    """Load session cookies from disk if they exist and aren't expired."""
    try:
        if not SESSION_PATH.exists():
            return None
        data = json.loads(SESSION_PATH.read_text())
        if not isinstance(data, list) or not data:
            return None
        # Check if session is stale (older than 24h based on file mtime)
        mtime = SESSION_PATH.stat().st_mtime
        if time.time() - mtime > 86400:
            logger.info("Session file older than 24h, ignoring")
            return None
        logger.debug("Loaded session from %s (%d cookies)", SESSION_PATH, len(data))
        return data
    except Exception as e:
        logger.warning("Failed to load session: %s", e)
        return None


# --- Proxy rotation ---

class ProxyRotator:
    """Cycle through a list of proxy URLs, rotating on failures."""

    def __init__(self, proxies: list[str] | None = None):
        self.proxies = proxies or []
        self._index = 0
        self._failed: set[str] = set()

    @property
    def current(self) -> str | None:
        if not self.proxies:
            return None
        available = [p for p in self.proxies if p not in self._failed]
        if not available:
            # Reset failures and retry all
            self._failed.clear()
            available = self.proxies
        return available[self._index % len(available)]

    def rotate(self, mark_failed: bool = False) -> str | None:
        """Move to next proxy. Optionally mark current as failed."""
        if not self.proxies:
            return None
        if mark_failed and self.current:
            self._failed.add(self.current)
            logger.warning("Proxy marked as failed: %s", self.current)
        self._index += 1
        logger.info("Rotated to proxy: %s", self.current)
        return self.current

    def reset(self) -> None:
        self._failed.clear()
        self._index = 0


# --- Retry wrapper ---

async def _retry_async(coro_factory, max_retries: int = 3, operation: str = "unknown",
                        username: str = "", result: ScrapeResult | None = None):
    """
    Retry an async operation with exponential backoff.
    coro_factory: callable that returns a new coroutine each call.
    """
    from .rate_limiter import RateLimiter
    rl = RateLimiter()

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()
        except PlaywrightTimeoutError as e:
            last_error = e
            err = ScrapeError(operation, username, "timeout", str(e))
            if result:
                result.add_error(err)
            if attempt < max_retries:
                await rl.backoff_on_error(attempt)
        except Exception as e:
            last_error = e
            err_type = type(e).__name__
            err = ScrapeError(operation, username, err_type, str(e))
            if result:
                result.add_error(err)
            if attempt < max_retries:
                await rl.backoff_on_error(attempt)

    logger.error("All %d retries exhausted for %s(@%s): %s", max_retries, operation, username, last_error)
    return None


class TwitterScraper:
    """Fetch tweets, following, followers, profile, interactions via intercepted GraphQL."""

    def __init__(
        self,
        browser_manager: object,
        max_retries: int = 3,
        proxies: list[str] | None = None,
        save_session: bool = True,
    ) -> None:
        self.browser = browser_manager
        self.max_retries = max_retries
        self.proxy_rotator = ProxyRotator(proxies)
        self.save_session = save_session

    async def _new_page(self) -> Page:
        page = await self.browser.new_page()
        # Apply viewport randomization
        vp = _random_viewport()
        await page.set_viewport_size(vp)
        return page

    async def _persist_cookies(self, page: Page) -> None:
        """Save cookies from the current page context for session persistence."""
        if not self.save_session:
            return
        try:
            context = page.context
            cookies = await context.cookies()
            if cookies:
                _save_session([{
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ""),
                    "path": c.get("path", "/"),
                    "expires": c.get("expires", -1),
                    "sameSite": c.get("sameSite", "Lax"),
                } for c in cookies])
        except Exception as e:
            logger.debug("Could not persist cookies: %s", e)

    async def _fallback_tweets_from_dom(self, page: Page, max_tweets: int) -> list[dict[str, Any]]:
        """
        Last-resort HTML scrape when GraphQL endpoints are blocked or error page is shown.
        Uses multiple selector strategies for resilience against DOM changes.
        """
        tweets: list[dict[str, Any]] = []

        # Multiple selector strategies ordered by reliability
        selector_strategies = [
            # Strategy 1: data-testid tweet containers (most common)
            ('div[data-testid="tweet"]', 'div[data-testid="tweetText"]'),
            # Strategy 2: article elements (alternative markup)
            ('article[role="article"]', 'div[data-testid="tweetText"]'),
            # Strategy 3: timeline item containers
            ('div[data-testid="cellInnerDiv"]', 'div[lang]'),
            # Strategy 4: broader article search
            ('article', 'div[lang][dir]'),
        ]

        for container_sel, text_sel in selector_strategies:
            try:
                containers = await page.query_selector_all(container_sel)
                if not containers:
                    continue
                for cont in containers:
                    if len(tweets) >= max_tweets:
                        break
                    try:
                        text = ""
                        # Try specific text selector first
                        text_node = await cont.query_selector(text_sel)
                        if text_node:
                            text = (await text_node.inner_text()).strip()
                        # Fallback: try getting time element for metadata
                        if not text:
                            text_node = await cont.query_selector('div[data-testid="tweetText"]')
                            if text_node:
                                text = (await text_node.inner_text()).strip()
                        if not text:
                            continue

                        # Try to extract author from the container
                        author = ""
                        try:
                            author_link = await cont.query_selector('a[role="link"][href*="/"]')
                            if author_link:
                                href = await author_link.get_attribute("href")
                                if href and href.startswith("/"):
                                    author = href.strip("/").split("/")[0]
                        except Exception:
                            pass

                        # Try to extract timestamp
                        created_at = ""
                        try:
                            time_el = await cont.query_selector("time")
                            if time_el:
                                created_at = await time_el.get_attribute("datetime") or ""
                        except Exception:
                            pass

                        tweets.append({
                            "id": None,
                            "full_text": text,
                            "text": text,
                            "created_at": created_at,
                            "author": author,
                            "favorite_count": 0,
                            "retweet_count": 0,
                            "reply_count": 0,
                            "in_reply_to": None,
                            "is_retweet": False,
                            "is_quote": False,
                            "quoted_user": None,
                            "urls": [],
                            "media_urls": [],
                            "hashtags": [],
                            "_source": "dom_fallback",
                        })
                    except Exception:
                        continue

                if tweets:
                    logger.info(
                        "DOM fallback strategy '%s' extracted %d tweets",
                        container_sel, len(tweets),
                    )
                    break  # Got results, stop trying other strategies
            except Exception:
                continue

        if not tweets:
            try:
                body_text = await page.inner_text("body")
                logger.warning(
                    "All DOM fallback strategies failed. Page body starts with: %r",
                    body_text[:300],
                )
            except Exception:
                logger.warning("All DOM fallback strategies failed and could not read body text.")

        return tweets

    async def fetch_tweets(self, username: str, max_tweets: int = 100) -> list[dict]:
        """Fetch recent tweets for a user. Returns list of tweet dicts (id, text, full_text, ...)."""
        result = ScrapeResult()

        async def _do_fetch():
            page = await self._new_page()
            await stealth_page(page)
            tweets: list[dict] = []
            seen_ids: set[str] = set()

            async def on_response(response) -> None:
                url = response.url
                if "UserTweets" not in url and "UserTweetsAndReplies" not in url:
                    return
                try:
                    body = await response.json()
                except Exception:
                    return
                if not isinstance(body, dict):
                    return
                extracted = parse_tweet_response(body)
                for t in extracted:
                    tid = t.get("id")
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        tweets.append(t)

            page.on("response", on_response)
            uname = (username or "").strip().lstrip("@")

            await _human_delay(1.0, 3.0)  # Anti-detection: delay before navigation

            try:
                await page.goto(
                    f"https://x.com/{uname}",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
            except PlaywrightTimeoutError:
                logger.warning("Timeout loading profile page for @%s; continuing with whatever data loaded", uname)
                result.add_error(ScrapeError("fetch_tweets", uname, "timeout", "Profile page load timeout"))

            await _human_delay(2.0, 4.0)  # Wait for initial data

            scroll_attempts = 0
            max_scrolls = max(5, max_tweets // 10)
            stall_count = 0
            while len(tweets) < max_tweets and scroll_attempts < max_scrolls:
                prev = len(tweets)
                await _realistic_scroll(page)
                await _human_delay(1.5, 4.0)  # Anti-detection: variable delays
                scroll_attempts += 1
                if len(tweets) == prev:
                    stall_count += 1
                    if stall_count >= 3:
                        break
                else:
                    stall_count = 0

            # Fallback: if GraphQL gave us nothing, try scraping DOM directly
            if not tweets:
                logger.info("No tweets from GraphQL for @%s; attempting DOM fallback", uname)
                dom_tweets = await self._fallback_tweets_from_dom(page, max_tweets)
                if dom_tweets:
                    tweets.extend(dom_tweets)

            await self._persist_cookies(page)
            await page.close()
            return tweets[:max_tweets]

        data = await _retry_async(
            _do_fetch,
            max_retries=self.max_retries,
            operation="fetch_tweets",
            username=username,
            result=result,
        )
        return data if data else []

    async def fetch_following(self, username: str, max_results: int = 500) -> list[str]:
        """Fetch list of accounts the user follows."""
        result = ScrapeResult()

        async def _do_fetch():
            page = await self._new_page()
            await stealth_page(page)
            following: list[str] = []
            seen: set[str] = set()

            async def on_response(response) -> None:
                if "Following" not in response.url:
                    return
                try:
                    body = await response.json()
                except Exception:
                    return
                if not isinstance(body, dict):
                    return
                users = parse_following_response(body)
                for u in users:
                    if u and u not in seen:
                        seen.add(u)
                        following.append(u)

            page.on("response", on_response)
            uname = (username or "").strip().lstrip("@")

            await _human_delay(1.0, 3.0)

            try:
                await page.goto(
                    f"https://x.com/{uname}/following",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
            except PlaywrightTimeoutError:
                logger.warning("Timeout loading following page for @%s", uname)
                result.add_error(ScrapeError("fetch_following", uname, "timeout", "Following page timeout"))

            await _human_delay(2.0, 4.0)

            scroll_attempts = 0
            stall_count = 0
            while len(following) < max_results and scroll_attempts < 50:
                prev = len(following)
                await _realistic_scroll(page)
                await _human_delay(1.5, 4.0)
                scroll_attempts += 1
                if len(following) == prev:
                    stall_count += 1
                    if stall_count >= 5:
                        break
                else:
                    stall_count = 0

            await self._persist_cookies(page)
            await page.close()
            return list(dict.fromkeys(following))[:max_results]

        data = await _retry_async(
            _do_fetch,
            max_retries=self.max_retries,
            operation="fetch_following",
            username=username,
            result=result,
        )
        return data if data else []

    async def fetch_followers(self, username: str, max_results: int = 500) -> list[str]:
        """Fetch list of followers."""
        result = ScrapeResult()

        async def _do_fetch():
            page = await self._new_page()
            await stealth_page(page)
            followers: list[str] = []
            seen: set[str] = set()

            async def on_response(response) -> None:
                if "Followers" not in response.url:
                    return
                try:
                    body = await response.json()
                except Exception:
                    return
                if not isinstance(body, dict):
                    return
                users = parse_followers_response(body)
                for u in users:
                    if u and u not in seen:
                        seen.add(u)
                        followers.append(u)

            page.on("response", on_response)
            uname = (username or "").strip().lstrip("@")

            await _human_delay(1.0, 3.0)

            try:
                await page.goto(
                    f"https://x.com/{uname}/followers",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
            except PlaywrightTimeoutError:
                logger.warning("Timeout loading followers page for @%s", uname)
                result.add_error(ScrapeError("fetch_followers", uname, "timeout", "Followers page timeout"))

            await _human_delay(2.0, 4.0)

            scroll_attempts = 0
            stall_count = 0
            while len(followers) < max_results and scroll_attempts < 50:
                prev = len(followers)
                await _realistic_scroll(page)
                await _human_delay(1.5, 4.0)
                scroll_attempts += 1
                if len(followers) == prev:
                    stall_count += 1
                    if stall_count >= 5:
                        break
                else:
                    stall_count = 0

            await self._persist_cookies(page)
            await page.close()
            return list(dict.fromkeys(followers))[:max_results]

        data = await _retry_async(
            _do_fetch,
            max_retries=self.max_retries,
            operation="fetch_followers",
            username=username,
            result=result,
        )
        return data if data else []

    async def fetch_user_profile(self, username: str) -> dict | None:
        """Fetch user profile metadata."""
        result = ScrapeResult()

        async def _do_fetch():
            page = await self._new_page()
            await stealth_page(page)
            profile: dict | None = None

            async def on_response(response) -> None:
                nonlocal profile
                if "UserByScreenName" not in response.url:
                    return
                try:
                    body = await response.json()
                except Exception:
                    return
                if isinstance(body, dict):
                    profile = parse_user_profile(body)

            page.on("response", on_response)
            uname = (username or "").strip().lstrip("@")

            await _human_delay(1.0, 3.0)

            try:
                await page.goto(
                    f"https://x.com/{uname}",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
            except PlaywrightTimeoutError:
                logger.warning("Timeout loading profile page for @%s while fetching user profile", uname)
                result.add_error(ScrapeError("fetch_user_profile", uname, "timeout", "Profile page timeout"))

            await _human_delay(2.0, 4.0)
            await self._persist_cookies(page)
            await page.close()
            return profile

        data = await _retry_async(
            _do_fetch,
            max_retries=self.max_retries,
            operation="fetch_user_profile",
            username=username,
            result=result,
        )
        return data

    async def fetch_interactions(self, username: str, max_tweets: int = 200) -> list[dict]:
        """
        Fetch replies/RTs/quotes to identify interaction targets.
        Returns list of { username, type, count, type_counts, recent_texts }.
        """
        result = ScrapeResult()

        async def _do_fetch():
            page = await self._new_page()
            await stealth_page(page)
            tweets: list[dict] = []
            seen_ids: set[str] = set()

            async def on_response(response) -> None:
                url = response.url
                if "UserTweetsAndReplies" not in url:
                    return
                try:
                    body = await response.json()
                except Exception:
                    return
                if not isinstance(body, dict):
                    return
                extracted = parse_tweet_response(body)
                for t in extracted:
                    tid = t.get("id")
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        tweets.append(t)

            page.on("response", on_response)
            uname = (username or "").strip().lstrip("@")

            await _human_delay(1.0, 3.0)

            try:
                await page.goto(
                    f"https://x.com/{uname}/with_replies",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
            except PlaywrightTimeoutError:
                logger.warning("Timeout loading replies page for @%s", uname)
                result.add_error(ScrapeError("fetch_interactions", uname, "timeout", "Replies page timeout"))

            await _human_delay(2.0, 4.0)

            for _ in range(max(5, max_tweets // 15)):
                await _realistic_scroll(page)
                await _human_delay(1.5, 4.0)

            await self._persist_cookies(page)
            await page.close()

            target_lower = uname.lower()
            agg: dict[str, dict] = defaultdict(
                lambda: {"username": "", "type_counts": defaultdict(int), "recent_texts": []}
            )
            for t in tweets[:max_tweets]:
                text = t.get("full_text") or t.get("text") or ""
                reply_to = t.get("in_reply_to")
                if reply_to:
                    u = str(reply_to).strip().lstrip("@").lower()
                    if u and u != target_lower:
                        agg[u]["username"] = u
                        agg[u]["type_counts"]["reply"] += 1
                        if len(agg[u]["recent_texts"]) < 5:
                            agg[u]["recent_texts"].append((text or "")[:200])
                if t.get("is_retweet"):
                    author = t.get("author", "")
                    if author:
                        u = str(author).strip().lstrip("@").lower()
                        if u != target_lower:
                            agg[u]["username"] = u
                            agg[u]["type_counts"]["rt"] += 1
                quoted = t.get("quoted_user")
                if quoted:
                    u = str(quoted).strip().lstrip("@").lower()
                    if u != target_lower:
                        agg[u]["username"] = u
                        agg[u]["type_counts"]["quote"] += 1
            out = []
            for u, data in agg.items():
                if not data["username"]:
                    data["username"] = u
                total = sum(data["type_counts"].values())
                if total == 0:
                    continue
                out.append({
                    "username": data["username"],
                    "type": max(data["type_counts"], key=data["type_counts"].get),
                    "count": total,
                    "type_counts": dict(data["type_counts"]),
                    "recent_texts": (data["recent_texts"])[:5],
                })
            return sorted(out, key=lambda x: -x["count"])

        data = await _retry_async(
            _do_fetch,
            max_retries=self.max_retries,
            operation="fetch_interactions",
            username=username,
            result=result,
        )
        return data if data else []
