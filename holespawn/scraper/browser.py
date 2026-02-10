"""
Playwright browser management: single headless Chromium, cookie-based session, stealth.
"""

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .auth import load_cookies


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


class BrowserManager:
    """Single Playwright browser instance; reuse across scraping operations."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        """Launch headless Chromium and load saved X cookies."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        await load_cookies(self._context)

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
