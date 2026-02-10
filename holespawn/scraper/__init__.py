"""
Self-hosted X/Twitter scraper (Playwright). Drop-in replacement for Apify.
"""

from .client import ScraperClient
from .sync import (
    fetch_followers,
    fetch_following,
    fetch_interactions,
    fetch_tweets,
    fetch_tweets_raw,
    fetch_user_profile,
)

__all__ = [
    "ScraperClient",
    "fetch_tweets",
    "fetch_tweets_raw",
    "fetch_following",
    "fetch_followers",
    "fetch_user_profile",
    "fetch_interactions",
]
