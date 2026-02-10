"""
Scraper CLI: login (save X session), test (fetch tweets), status (check session).
"""

import asyncio
import sys

from .auth import get_cookie_path, save_cookies
from .browser import BrowserManager
from .client import ScraperClient


async def cmd_login() -> None:
    """Open visible browser to x.com/login; operator logs in; save cookies."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = await context.new_page()
        await page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=30000)
        print("[scraper] Log in to X in the browser window.")
        print("[scraper] Press Enter here once you're logged in and see your feed...")
        input()
        await save_cookies(context)
        path = get_cookie_path()
        print(f"[scraper] Session saved to {path}")
        await browser.close()


async def cmd_test(username: str) -> None:
    """Fetch a few tweets for username and print them."""
    async with ScraperClient() as scraper:
        print(f"[scraper] Fetching tweets for {username}...")
        tweets = await scraper.fetch_tweets(username, max_tweets=10)
        print(f"[scraper] Got {len(tweets)} tweets")
        for t in tweets:
            text = (t.get("full_text") or t.get("text") or "")[:100]
            created = t.get("created_at", "?")
            print(f"  [{created}] {text}")


async def cmd_status() -> None:
    """Check if saved session is still valid."""
    from .auth import check_session, get_cookie_path

    if not get_cookie_path().exists():
        print("[scraper] No session — run: python -m holespawn.scraper login")
        return
    async with BrowserManager() as bm:
        page = await bm.new_page()
        valid = await check_session(page)
        await page.close()
    if valid:
        print("[scraper] Session is valid")
    else:
        print("[scraper] Session expired — run: python -m holespawn.scraper login")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        print("Usage: python -m holespawn.scraper login | test @username | status")
        return 0
    cmd = sys.argv[1].lower()
    if cmd == "login":
        asyncio.run(cmd_login())
    elif cmd == "test":
        if len(sys.argv) < 3:
            print("Usage: python -m holespawn.scraper test @username")
            return 1
        asyncio.run(cmd_test(sys.argv[2]))
    elif cmd == "status":
        asyncio.run(cmd_status())
    else:
        print(f"Unknown command: {cmd}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
