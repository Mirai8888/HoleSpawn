"""
Synchronous wrappers for ScraperClient. Use in sync code (ingest, recorder, network).
"""

import asyncio
from typing import Any

from .client import ScraperClient


def _run(coro: Any) -> Any:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("Use async ScraperClient when already in an async context")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def fetch_tweets(username: str, max_tweets: int = 100) -> list[dict]:
    async def _() -> list[dict]:
        async with ScraperClient() as s:
            return await s.fetch_tweets(username, max_tweets=max_tweets)
    return _run(_())


def fetch_following(username: str, max_results: int = 500) -> list[str]:
    async def _() -> list[str]:
        async with ScraperClient() as s:
            return await s.fetch_following(username, max_results=max_results)
    return _run(_())


def fetch_followers(username: str, max_results: int = 500) -> list[str]:
    async def _() -> list[str]:
        async with ScraperClient() as s:
            return await s.fetch_followers(username, max_results=max_results)
    return _run(_())


def fetch_user_profile(username: str) -> dict | None:
    async def _() -> dict | None:
        async with ScraperClient() as s:
            return await s.fetch_user_profile(username)
    return _run(_())


def fetch_interactions(username: str, max_tweets: int = 200) -> list[dict]:
    async def _() -> list[dict]:
        async with ScraperClient() as s:
            return await s.fetch_interactions(username, max_tweets=max_tweets)
    return _run(_())


def fetch_tweets_raw(username: str, max_tweets: int = 500) -> list[dict] | None:
    """Raw tweet dicts for recording; same shape as Apify raw output."""
    items = fetch_tweets(username, max_tweets=max_tweets)
    return items if items else None
