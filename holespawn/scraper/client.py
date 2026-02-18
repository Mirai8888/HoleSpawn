"""
Unified scraper client: drop-in replacement for Apify. Async API.

Enhanced with proxy rotation, retry configuration, and session persistence support.
"""

from .browser import BrowserManager
from .cache import ScrapeCache
from .rate_limiter import RateLimiter
from .twitter import TwitterScraper


class ScraperClient:
    """
    Async client for tweets, following, followers, profile, interactions.
    Use as: async with ScraperClient() as scraper: ...

    Args:
        cache_enabled: Enable response caching (default True).
        max_retries: Max retry attempts for transient failures (default 3).
        proxies: Optional list of proxy URLs for rotation.
        save_session: Persist browser session cookies (default True).
        proxy: Single proxy URL for the browser (for BrowserManager).
    """

    def __init__(
        self,
        cache_enabled: bool = True,
        max_retries: int = 3,
        proxies: list[str] | None = None,
        save_session: bool = True,
        proxy: str | None = None,
    ) -> None:
        # If proxies provided but no single proxy, use first as browser proxy
        browser_proxy = proxy or (proxies[0] if proxies else None)
        self.browser = BrowserManager(proxy=browser_proxy)
        self.twitter = TwitterScraper(
            self.browser,
            max_retries=max_retries,
            proxies=proxies,
            save_session=save_session,
        )
        self.rate_limiter = RateLimiter()
        self.cache = ScrapeCache() if cache_enabled else None

    async def __aenter__(self) -> "ScraperClient":
        await self.browser.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.browser.stop()

    async def fetch_tweets(self, username: str, max_tweets: int = 100) -> list[dict]:
        if self.cache:
            cached = self.cache.get("tweets", username, ttl_hours=1, max_tweets=max_tweets)
            if cached is not None:
                return list(cached) if isinstance(cached, list) else []
        await self.rate_limiter.wait()
        self.rate_limiter.reset_backoff()
        tweets = await self.twitter.fetch_tweets(username, max_tweets)
        if self.cache and tweets:
            self.cache.set("tweets", username, tweets, max_tweets=max_tweets)
        return tweets

    async def fetch_following(self, username: str, max_results: int = 500) -> list[str]:
        if self.cache:
            cached = self.cache.get("following", username, ttl_hours=6, max_results=max_results)
            if cached is not None:
                return list(cached) if isinstance(cached, list) else []
        await self.rate_limiter.wait()
        self.rate_limiter.reset_backoff()
        following = await self.twitter.fetch_following(username, max_results)
        if self.cache and following:
            self.cache.set("following", username, following, max_results=max_results)
        return following

    async def fetch_followers(self, username: str, max_results: int = 500) -> list[str]:
        if self.cache:
            cached = self.cache.get("followers", username, ttl_hours=6, max_results=max_results)
            if cached is not None:
                return list(cached) if isinstance(cached, list) else []
        await self.rate_limiter.wait()
        self.rate_limiter.reset_backoff()
        followers = await self.twitter.fetch_followers(username, max_results)
        if self.cache and followers:
            self.cache.set("followers", username, followers, max_results=max_results)
        return followers

    async def fetch_user_profile(self, username: str) -> dict | None:
        if self.cache:
            cached = self.cache.get("profile", username, ttl_hours=24)
            if cached is not None:
                return cached if isinstance(cached, dict) else None
        await self.rate_limiter.wait()
        self.rate_limiter.reset_backoff()
        profile = await self.twitter.fetch_user_profile(username)
        if self.cache and profile:
            self.cache.set("profile", username, profile)
        return profile

    async def fetch_interactions(self, username: str, max_tweets: int = 200) -> list[dict]:
        if self.cache:
            cached = self.cache.get("interactions", username, ttl_hours=1, max_tweets=max_tweets)
            if cached is not None:
                return list(cached) if isinstance(cached, list) else []
        await self.rate_limiter.wait()
        self.rate_limiter.reset_backoff()
        interactions = await self.twitter.fetch_interactions(username, max_tweets)
        if self.cache and interactions:
            self.cache.set("interactions", username, interactions, max_tweets=max_tweets)
        return interactions
