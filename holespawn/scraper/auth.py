"""
X/Twitter session: cookie load/save, interactive login, session check.
"""

import json
from pathlib import Path

from playwright.async_api import BrowserContext, Page

# Default path; override with SCRAPER_COOKIE_PATH env
COOKIE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "x_cookies.json"


def get_cookie_path() -> Path:
    import os
    p = os.environ.get("SCRAPER_COOKIE_PATH")
    return Path(p) if p else COOKIE_PATH


async def load_cookies(context: BrowserContext) -> None:
    """Load saved cookies into Playwright browser context. Raises FileNotFoundError if no cookies."""
    path = get_cookie_path()
    if not path.exists():
        raise FileNotFoundError(
            "No X session cookies found. Run: python -m holespawn.scraper login"
        )
    cookies = json.loads(path.read_text(encoding="utf-8"))
    await context.add_cookies(cookies)


async def save_cookies(context: BrowserContext) -> None:
    """Save current browser cookies for reuse."""
    cookies = await context.cookies()
    path = get_cookie_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")


async def check_session(page: Page) -> bool:
    """Check if the current session is still valid (not redirected to login)."""
    await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
    if "login" in page.url:
        return False
    return True
