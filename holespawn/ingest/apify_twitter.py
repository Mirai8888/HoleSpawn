"""
Twitter/X ingestion via self-hosted scraper (Playwright). Replaces Apify.
Requires X session cookies: python -m holespawn.scraper login
"""

import logging
from typing import Any

from holespawn.errors import ScraperError
from holespawn.scraper.sync import fetch_tweets, fetch_tweets_raw as _fetch_tweets_raw

from .loader import SocialContent

logger = logging.getLogger(__name__)


def _normalize_username(username: str) -> str:
    """Strip @ and whitespace."""
    return (username or "").strip().lstrip("@").strip()


def _item_to_text(item: Any) -> str:
    """Extract tweet text from a single dataset item (scraper or legacy Apify format)."""
    if isinstance(item, dict):
        return (
            item.get("full_text")
            or item.get("text")
            or item.get("content")
            or item.get("tweet")
            or ""
        )
    return str(item)


def _item_media_urls(item: Any) -> list[str]:
    """Extract image URLs from a single dataset item."""
    urls: list[str] = []
    if not isinstance(item, dict):
        return urls
    # Scraper format: media_urls list
    for u in item.get("media_urls") or []:
        if u and isinstance(u, str) and u not in urls:
            urls.append(u)
    for key in ("extended_entities", "entities", "media"):
        container = item.get(key)
        if key == "media":
            media_list = container if isinstance(container, list) else None
        elif isinstance(container, dict):
            media_list = container.get("media")
        else:
            media_list = None
        if not isinstance(media_list, list):
            continue
        for m in media_list:
            if not isinstance(m, dict):
                continue
            mtype = (m.get("type") or "").lower()
            if mtype and mtype not in ("photo", "image", ""):
                continue
            u = m.get("media_url_https") or m.get("media_url") or m.get("url")
            if u and isinstance(u, str) and u not in urls:
                urls.append(u)
    return urls


def fetch_twitter_apify(username: str, max_tweets: int = 500) -> SocialContent | None:
    """
    Fetch tweets for a Twitter user via self-hosted scraper.
    Returns None if no session (run: python -m holespawn.scraper login) or no tweets.
    Raises ScraperError on session/auth failure.
    """
    username = _normalize_username(username)
    if not username:
        return None
    try:
        tweets = fetch_tweets(username, max_tweets=max_tweets)
    except FileNotFoundError as e:
        raise ScraperError(
            "No X session cookies. Run: python -m holespawn.scraper login"
        ) from e
    except Exception as e:
        logger.warning("Scraper failed for @%s: %s", username, e)
        return None
    if not tweets:
        return None
    posts = []
    media_urls = []
    seen_media = set()
    for t in tweets:
        text = _item_to_text(t).strip()
        if text:
            posts.append(text)
        for u in _item_media_urls(t):
            if u not in seen_media:
                seen_media.add(u)
                media_urls.append(u)
    return SocialContent(
        posts=posts, raw_text="\n".join(posts), media_urls=media_urls
    )


def fetch_twitter_apify_raw(username: str, max_tweets: int = 500) -> list[dict] | None:
    """
    Fetch raw tweet items for a Twitter user (for recording).
    Returns list of tweet dicts or None. Requires X session (python -m holespawn.scraper login).
    """
    username = _normalize_username(username)
    if not username:
        return None
    try:
        return _fetch_tweets_raw(username, max_tweets=max_tweets)
    except FileNotFoundError as e:
        raise ScraperError(
            "No X session cookies. Run: python -m holespawn.scraper login"
        ) from e
    except Exception as e:
        logger.warning("Scraper failed for @%s: %s", username, e)
        return None
