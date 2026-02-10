"""
Twitter/X scraping via GraphQL interception. Uses BrowserManager and parser.
"""

import logging
from collections import defaultdict
from typing import Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .browser import stealth_page
from .parser import (
    parse_followers_response,
    parse_following_response,
    parse_tweet_response,
    parse_user_profile,
)

logger = logging.getLogger(__name__)


class TwitterScraper:
    """Fetch tweets, following, followers, profile, interactions via intercepted GraphQL."""

    def __init__(self, browser_manager: object) -> None:
        self.browser = browser_manager

    async def _new_page(self) -> Page:
        return await self.browser.new_page()

    async def _fallback_tweets_from_dom(self, page: Page, max_tweets: int) -> list[dict[str, Any]]:
        """
        Last-resort HTML scrape when GraphQL endpoints are blocked or error page is shown.
        Uses tweet containers with data-testid markers; structure may change, so treat as best-effort.
        """
        tweets: list[dict[str, Any]] = []
        try:
            # Modern X markup: each tweet is usually in div[data-testid="tweet"] with a div[data-testid="tweetText"] inside.
            containers = await page.query_selector_all('div[data-testid="tweet"]')
        except Exception:
            return []
        for cont in containers:
            if len(tweets) >= max_tweets:
                break
            try:
                text_node = await cont.query_selector('div[data-testid="tweetText"]')
                if text_node:
                    text = (await text_node.inner_text()).strip()
                else:
                    text = (await cont.inner_text()).strip()
            except Exception:
                continue
            if not text:
                continue
            tweets.append(
                {
                    "id": None,
                    "full_text": text,
                    "text": text,
                    "created_at": "",
                    "author": "",
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
                }
            )
        if tweets:
            logger.info("Fallback DOM scraper extracted %d tweets", len(tweets))
        else:
            try:
                body_text = await page.inner_text("body")
                logger.warning("Fallback DOM scraper found no tweets. Page body starts with: %r", body_text[:200])
            except Exception:
                logger.warning("Fallback DOM scraper found no tweets and could not read body text.")
        return tweets

    async def fetch_tweets(self, username: str, max_tweets: int = 100) -> list[dict]:
        """Fetch recent tweets for a user. Returns list of tweet dicts (id, text, full_text, ...)."""
        page = await self._new_page()
        await stealth_page(page)
        tweets: list[dict] = []
        seen_ids: set[str] = set()

        def handle_response(response) -> None:
            nonlocal tweets
            url = response.url
            if "UserTweets" not in url and "UserTweetsAndReplies" not in url:
                return
            try:
                import asyncio
                body = asyncio.get_event_loop().run_until_complete(response.json())
            except Exception:
                try:
                    body = response.json()
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
            return

        # Playwright async: we need to attach and then await response.json() in the handler.
        # So we use an async handler that we run in the event loop.
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
        try:
            await page.goto(
                f"https://x.com/{uname}",
                wait_until="domcontentloaded",
                timeout=45000,
            )
        except PlaywrightTimeoutError:
            logger.warning("Timeout loading profile page for @%s; continuing with whatever data loaded", uname)
        scroll_attempts = 0
        max_scrolls = max(5, max_tweets // 10)
        while len(tweets) < max_tweets and scroll_attempts < max_scrolls:
            prev = len(tweets)
            await page.evaluate("window.scrollBy(0, 2000)")
            await page.wait_for_timeout(1500)
            scroll_attempts += 1
            if len(tweets) == prev:
                break
        # Fallback: if GraphQL gave us nothing, try scraping DOM directly
        if not tweets:
            logger.info("No tweets from GraphQL for @%s; attempting DOM fallback", uname)
            dom_tweets = await self._fallback_tweets_from_dom(page, max_tweets)
            if dom_tweets:
                tweets.extend(dom_tweets)
        await page.close()
        return tweets[:max_tweets]

    async def fetch_following(self, username: str, max_results: int = 500) -> list[str]:
        """Fetch list of accounts the user follows."""
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
        try:
            await page.goto(
                f"https://x.com/{uname}/following",
                wait_until="domcontentloaded",
                timeout=45000,
            )
        except PlaywrightTimeoutError:
            logger.warning("Timeout loading following page for @%s; continuing with whatever data loaded", uname)
        scroll_attempts = 0
        while len(following) < max_results and scroll_attempts < 50:
            prev = len(following)
            await page.evaluate("window.scrollBy(0, 2000)")
            await page.wait_for_timeout(1500)
            scroll_attempts += 1
            if len(following) == prev:
                break
        await page.close()
        return list(dict.fromkeys(following))[:max_results]

    async def fetch_followers(self, username: str, max_results: int = 500) -> list[str]:
        """Fetch list of followers."""
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
        try:
            await page.goto(
                f"https://x.com/{uname}/followers",
                wait_until="domcontentloaded",
                timeout=45000,
            )
        except PlaywrightTimeoutError:
            logger.warning("Timeout loading followers page for @%s; continuing with whatever data loaded", uname)
        scroll_attempts = 0
        while len(followers) < max_results and scroll_attempts < 50:
            prev = len(followers)
            await page.evaluate("window.scrollBy(0, 2000)")
            await page.wait_for_timeout(1500)
            scroll_attempts += 1
            if len(followers) == prev:
                break
        await page.close()
        return list(dict.fromkeys(followers))[:max_results]

    async def fetch_user_profile(self, username: str) -> dict | None:
        """Fetch user profile metadata."""
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
            return

        page.on("response", on_response)
        uname = (username or "").strip().lstrip("@")
        try:
            await page.goto(
                f"https://x.com/{uname}",
                wait_until="domcontentloaded",
                timeout=45000,
            )
        except PlaywrightTimeoutError:
            logger.warning("Timeout loading profile page for @%s while fetching user profile", uname)
        await page.wait_for_timeout(2000)
        await page.close()
        return profile

    async def fetch_interactions(self, username: str, max_tweets: int = 200) -> list[dict]:
        """
        Fetch replies/RTs/quotes to identify interaction targets.
        Returns list of { username, type, count, type_counts, recent_texts }.
        """
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
            return

        page.on("response", on_response)
        uname = (username or "").strip().lstrip("@")
        try:
            await page.goto(
                f"https://x.com/{uname}/with_replies",
                wait_until="domcontentloaded",
                timeout=45000,
            )
        except PlaywrightTimeoutError:
            logger.warning("Timeout loading replies page for @%s; continuing with whatever data loaded", uname)
        for _ in range(max(5, max_tweets // 15)):
            await page.evaluate("window.scrollBy(0, 2000)")
            await page.wait_for_timeout(1500)
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
