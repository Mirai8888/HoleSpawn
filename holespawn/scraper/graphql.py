#!/usr/bin/env python3
"""
Twitter/X GraphQL Network Scraper

Intercepts Twitter's internal GraphQL API via Playwright to extract
full follower/following lists with structured user data.

Strategy:
1. Navigate to target's following/followers page
2. Intercept the GraphQL API response (includes auth headers automatically)
3. Parse user objects from the structured JSON response
4. For following lists: replay the API call with cursor pagination (complete extraction)
5. For follower lists: use DOM scrolling fallback (Twitter blocks cursor replay on followers)

Requires: Twitter session cookies at the configured cookie path.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

DEFAULT_COOKIE_PATH = Path.home() / ".config" / "twitter" / "cookies.json"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _clean_cookies(raw: list[dict]) -> list[dict]:
    """Clean cookie objects for Playwright compatibility."""
    clean = []
    for c in raw:
        cc = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".x.com"),
            "path": c.get("path", "/"),
        }
        ss = c.get("sameSite", "Lax")
        cc["sameSite"] = ss if ss in ("Strict", "Lax", "None") else "Lax"
        if c.get("expires") and c["expires"] > 0:
            cc["expires"] = c["expires"]
        clean.append(cc)
    return clean


def _parse_timeline_response(data: dict) -> tuple[list[dict], str | None]:
    """Extract user objects and bottom cursor from a GraphQL timeline response."""
    users = []
    cursor = None
    try:
        instructions = data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
        for inst in instructions:
            for entry in inst.get("entries", []):
                entry_id = entry.get("entryId", "")
                content = entry.get("content", {})

                # Cursor entry
                if "cursor-bottom" in entry_id:
                    cursor = content.get("value")
                    continue

                # User entry
                item_content = content.get("itemContent", {})
                user_result = item_content.get("user_results", {}).get("result", {})
                if not user_result:
                    continue

                core = user_result.get("core", {})
                legacy = user_result.get("legacy", {})
                profile_bio = user_result.get("profile_bio", {})
                location = user_result.get("location", {})

                screen_name = core.get("screen_name") or legacy.get("screen_name")
                if not screen_name:
                    continue

                users.append({
                    "id": user_result.get("rest_id", ""),
                    "screen_name": screen_name,
                    "name": core.get("name", legacy.get("name", "")),
                    "bio": profile_bio.get("description", legacy.get("description", "")),
                    "followers_count": legacy.get("followers_count", 0),
                    "following_count": legacy.get("friends_count", 0),
                    "verified": user_result.get("is_blue_verified", False),
                    "location": location.get("location", legacy.get("location", "")),
                    "created_at": core.get("created_at", legacy.get("created_at", "")),
                    "statuses_count": legacy.get("statuses_count", 0),
                    "listed_count": legacy.get("listed_count", 0),
                    "media_count": legacy.get("media_count", 0),
                })
    except (KeyError, TypeError) as e:
        logger.debug(f"Parse error: {e}")

    return users, cursor


def _dedupe(users: list[dict]) -> list[dict]:
    """Deduplicate user list by screen_name."""
    seen = set()
    unique = []
    for u in users:
        sn = u["screen_name"]
        if sn not in seen:
            seen.add(sn)
            unique.append(u)
    return unique


async def scrape_network(
    target: str,
    cookie_path: str | None = None,
    include_followers: bool = True,
    include_following: bool = True,
    rate_limit_delay: float = 1.0,
    scroll_attempts: int = 80,
    headless: bool = True,
) -> dict:
    """
    Scrape a Twitter/X account's network (following + followers).

    Args:
        target: Twitter handle (without @)
        cookie_path: Path to cookies JSON file
        include_followers: Whether to scrape followers
        include_following: Whether to scrape following
        rate_limit_delay: Seconds between paginated API calls
        scroll_attempts: Max scroll iterations for DOM-based scraping
        headless: Run browser headless

    Returns:
        Dict with following, followers, mutuals, and metadata
    """
    cookie_file = Path(cookie_path) if cookie_path else DEFAULT_COOKIE_PATH
    if not cookie_file.exists():
        raise FileNotFoundError(f"Cookie file not found: {cookie_file}")

    raw_cookies = json.loads(cookie_file.read_text())
    cookies = _clean_cookies(raw_cookies)
    req_cookies = {c["name"]: c["value"] for c in raw_cookies}

    following = []
    followers = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=DEFAULT_USER_AGENT,
        )
        await ctx.add_cookies(cookies)

        # --- FOLLOWING (GraphQL cursor pagination) ---
        if include_following:
            logger.info(f"Scraping following for @{target}...")
            following = await _scrape_with_cursor_pagination(
                ctx, target, "following", req_cookies, rate_limit_delay
            )
            logger.info(f"Following: {len(following)} accounts")

        # --- FOLLOWERS (DOM scrolling fallback) ---
        if include_followers:
            logger.info(f"Scraping followers for @{target}...")
            followers = await _scrape_with_dom_scroll(
                ctx, target, "followers", scroll_attempts
            )
            logger.info(f"Followers: {len(followers)} accounts")

        await browser.close()

    # Compute mutuals
    following_set = {u["screen_name"] for u in following}
    followers_set = {u["screen_name"] for u in followers}
    mutuals = sorted(following_set & followers_set)

    return {
        "target": target,
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "following_count": len(following),
        "followers_count": len(followers),
        "mutual_count": len(mutuals),
        "mutuals": mutuals,
        "following": following,
        "followers": followers,
    }


async def _scrape_with_cursor_pagination(
    ctx, target: str, list_type: str, req_cookies: dict, delay: float
) -> list[dict]:
    """
    Scrape a list using GraphQL cursor pagination.
    Works for 'following'. Twitter blocks cursor replay for 'followers'.
    """
    import requests

    page = await ctx.new_page()
    intercepted = {"url": None, "headers": None, "body": None}

    async def capture_req(request):
        url = request.url
        if "graphql" in url.lower() and list_type.capitalize() in url and not intercepted["url"]:
            intercepted["url"] = url
            intercepted["headers"] = dict(request.headers)

    async def capture_resp(response):
        url = response.url
        if "graphql" in url.lower() and list_type.capitalize() in url and not intercepted["body"]:
            try:
                intercepted["body"] = await response.json()
            except Exception:
                pass

    page.on("request", capture_req)
    page.on("response", capture_resp)

    await page.goto(
        f"https://x.com/{target}/{list_type}",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    await asyncio.sleep(5)
    await page.close()

    if not intercepted["url"] or not intercepted["body"]:
        logger.warning(f"No GraphQL request intercepted for {list_type}")
        return []

    # Parse initial response
    all_users, cursor = _parse_timeline_response(intercepted["body"])
    logger.debug(f"Initial batch: {len(all_users)} users, cursor: {cursor}")

    if not cursor:
        return _dedupe(all_users)

    # Replay with cursor pagination
    base_url = intercepted["url"].split("?")[0]
    headers = intercepted["headers"]
    parsed = urlparse(intercepted["url"])
    params = parse_qs(parsed.query)
    original_variables = json.loads(params["variables"][0])
    features = params["features"][0]

    page_num = 1
    while cursor:
        page_num += 1
        new_vars = original_variables.copy()
        new_vars["cursor"] = cursor

        new_params = {
            "variables": json.dumps(new_vars, separators=(",", ":")),
            "features": features,
        }
        if "fieldToggles" in params:
            new_params["fieldToggles"] = params["fieldToggles"][0]

        retries_left = 3
        while retries_left > 0:
            try:
                resp = requests.get(
                    base_url,
                    headers=headers,
                    cookies=req_cookies,
                    params=new_params,
                    timeout=15,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    users, cursor = _parse_timeline_response(data)
                    all_users.extend(users)
                    logger.debug(f"Page {page_num}: +{len(users)} users (total: {len(all_users)})")
                    if not users:
                        cursor = None
                    time.sleep(delay)
                    break
                elif resp.status_code == 429:
                    import random as _rand
                    backoff = min(300, 5 * (2 ** (3 - retries_left)))
                    jitter = backoff * _rand.uniform(-0.25, 0.25)
                    wait = max(1, backoff + jitter)
                    logger.warning(f"Rate limited (429), backoff {wait:.1f}s (retries left: {retries_left})")
                    time.sleep(wait)
                    retries_left -= 1
                elif 500 <= resp.status_code < 600:
                    logger.warning(f"Page {page_num}: HTTP {resp.status_code}, retrying...")
                    retries_left -= 1
                    time.sleep(2 * (3 - retries_left))
                else:
                    logger.warning(f"Page {page_num}: HTTP {resp.status_code}")
                    cursor = None
                    break
            except requests.exceptions.Timeout:
                logger.warning(f"Page {page_num}: timeout, retrying...")
                retries_left -= 1
                time.sleep(2)
            except Exception as e:
                logger.error(f"Page {page_num} error: {e}")
                cursor = None
                break
        else:
            logger.error(f"Page {page_num}: all retries exhausted")
            break

    return _dedupe(all_users)


async def _scrape_with_dom_scroll(
    ctx, target: str, list_type: str, max_scrolls: int
) -> list[dict]:
    """
    Scrape a list using DOM scrolling and GraphQL response interception.
    Fallback method when cursor pagination is blocked.
    """
    page = await ctx.new_page()
    all_responses = []

    async def capture(response):
        url = response.url
        if "graphql" in url.lower() and list_type.capitalize() in url:
            try:
                body = await response.json()
                all_responses.append(body)
            except Exception:
                pass

    page.on("response", capture)

    await page.goto(
        f"https://x.com/{target}/{list_type}",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    await asyncio.sleep(5)

    # Scroll to trigger pagination
    prev_count = len(all_responses)
    stall = 0
    for i in range(max_scrolls):
        # Multiple scroll strategies
        await page.evaluate("""
            window.scrollBy(0, 1000);
            const pc = document.querySelector('[data-testid="primaryColumn"]');
            if (pc) { pc.scrollTop += 1000; }
        """)

        # Alternate keyboard methods
        keys = ["Space", "PageDown", "End"]
        await page.keyboard.press(keys[i % 3])
        await asyncio.sleep(0.8)

        current = len(all_responses)
        if current == prev_count:
            stall += 1
            if stall >= 10:
                break
        else:
            stall = 0
        prev_count = current

    await page.close()

    # Parse all captured responses
    all_users = []
    for resp_data in all_responses:
        users, _ = _parse_timeline_response(resp_data)
        all_users.extend(users)

    return _dedupe(all_users)


async def scrape_user_profile(
    ctx, screen_name: str
) -> dict | None:
    """Scrape a single user's profile data via their profile page."""
    page = await ctx.new_page()
    profile_data = {}

    async def capture(response):
        if "UserByScreenName" in response.url:
            try:
                body = await response.json()
                result = body.get("data", {}).get("user", {}).get("result", {})
                core = result.get("core", {})
                legacy = result.get("legacy", {})
                profile_data.update({
                    "id": result.get("rest_id", ""),
                    "screen_name": core.get("screen_name", screen_name),
                    "name": core.get("name", ""),
                    "bio": result.get("profile_bio", {}).get("description", ""),
                    "followers_count": legacy.get("followers_count", 0),
                    "following_count": legacy.get("friends_count", 0),
                    "verified": result.get("is_blue_verified", False),
                    "location": result.get("location", {}).get("location", ""),
                    "created_at": core.get("created_at", ""),
                    "statuses_count": legacy.get("statuses_count", 0),
                })
            except Exception:
                pass

    page.on("response", capture)
    try:
        await page.goto(f"https://x.com/{screen_name}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
    except Exception:
        pass
    await page.close()
    return profile_data if profile_data else None


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Twitter/X GraphQL Network Scraper")
    parser.add_argument("target", help="Twitter handle (without @)")
    parser.add_argument("--cookies", default=str(DEFAULT_COOKIE_PATH), help="Cookie file path")
    parser.add_argument("--output", "-o", default=None, help="Output JSON path")
    parser.add_argument("--no-followers", action="store_true", help="Skip followers")
    parser.add_argument("--no-following", action="store_true", help="Skip following")
    parser.add_argument("--delay", type=float, default=1.0, help="Rate limit delay (seconds)")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    result = asyncio.run(scrape_network(
        target=args.target,
        cookie_path=args.cookies,
        include_followers=not args.no_followers,
        include_following=not args.no_following,
        rate_limit_delay=args.delay,
        headless=not args.visible,
    ))

    output_path = args.output or f"/tmp/{args.target}_network.json"
    Path(output_path).write_text(json.dumps(result, indent=2))

    print(f"\nResults for @{args.target}:")
    print(f"  Following: {result['following_count']}")
    print(f"  Followers: {result['followers_count']}")
    print(f"  Mutuals: {result['mutual_count']}")
    if result["mutuals"]:
        print(f"  Mutual accounts: {', '.join(result['mutuals'])}")
    print(f"\nSaved to: {output_path}")
