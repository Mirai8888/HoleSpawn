"""
Playwright browser management: single headless Chromium, cookie-based session, stealth.

Enhanced with:
- Viewport randomization
- Session cookie persistence/restore
- Optional proxy support
"""

import json
import logging
import random
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .auth import load_cookies

logger = logging.getLogger(__name__)

SESSION_PATH = Path.home() / ".config" / "holespawn" / "twitter-session.json"

# Randomized user agents for anti-detection
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


async def stealth_page(page: Page) -> None:
    """Apply anti-detection patches to reduce automation fingerprint."""
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    await page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
    """)
    await page.add_init_script("""
        window.chrome = { runtime: {} };
    """)
    # Additional stealth: hide automation indicators
    await page.add_init_script("""
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)


def _load_session_cookies() -> list[dict] | None:
    """Load persisted session cookies if available."""
    try:
        if not SESSION_PATH.exists():
            return None
        import time
        if time.time() - SESSION_PATH.stat().st_mtime > 86400:
            return None
        data = json.loads(SESSION_PATH.read_text())
        if isinstance(data, list) and data:
            logger.debug("Restoring %d session cookies", len(data))
            return data
    except Exception as e:
        logger.debug("Could not load session cookies: %s", e)
    return None


class BrowserManager:
    """Single Playwright browser instance; reuse across scraping operations."""

    def __init__(self, proxy: str | None = None) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._proxy = proxy

    async def start(self) -> None:
        """Launch headless Chromium and load saved X cookies."""
        self._playwright = await async_playwright().start()

        launch_args = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }
        if self._proxy:
            launch_args["proxy"] = {"server": self._proxy}

        self._browser = await self._playwright.chromium.launch(**launch_args)

        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864},
        ]
        vp = random.choice(viewports)

        self._context = await self._browser.new_context(
            viewport=vp,
            user_agent=random.choice(_USER_AGENTS),
            locale="en-US",
        )

        # Load auth cookies first
        await load_cookies(self._context)

        # Then overlay any persisted session cookies
        session_cookies = _load_session_cookies()
        if session_cookies:
            try:
                await self._context.add_cookies(session_cookies)
            except Exception as e:
                logger.debug("Could not restore session cookies: %s", e)

    async def new_page(self) -> Page:
        """New page in the authenticated context."""
        if self._context is None:
            raise RuntimeError("BrowserManager not started")
        return await self._context.new_page()

    async def stop(self) -> None:
        """Clean shutdown."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._context = None

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()
