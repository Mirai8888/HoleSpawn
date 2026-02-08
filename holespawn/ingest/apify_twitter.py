"""
Optional Twitter ingestion via Apify. Tries multiple scrapers in order; if one
returns no tweets, falls back to the next. Requires APIFY_API_TOKEN.
Raises ApifyError on API failure.
"""

import logging
import os
from typing import Any

from holespawn.errors import ApifyError

from .loader import SocialContent

logger = logging.getLogger(__name__)

# Primary: profile/timeline scraper (often blocked by Twitter post-2023)
APIFY_TWITTER_ACTOR = "u6ppkMWAx2E2MpEuF"

# Fallback scrapers: tried in order when primary returns 0 tweets.
# Use pay-per-result actors (no monthly rental) so they work with standard Apify billing.
SCRAPER_FALLBACKS = [
    {
        "name": "apidojo/tweet-scraper",
        "build_input": lambda username, max_tweets: {
            "twitterHandles": [username],
            "maxItems": min(max_tweets, 1000),
        },
    },
]


def _reraise_apify_error(exc: Exception, username: str) -> None:
    """Re-raise as ApifyError for known API/timeout errors; otherwise re-raise original."""
    try:
        from apify_client.errors import ApifyApiError
    except ImportError:
        ApifyApiError = type("Never", (), {})
    try:
        from requests.exceptions import Timeout as RequestsTimeout
    except ImportError:
        RequestsTimeout = type("Never", (), {})

    if isinstance(exc, ApifyApiError):
        status = getattr(exc, "status_code", None) or getattr(
            getattr(exc, "response", None), "status_code", None
        )
        if status == 401:
            raise ApifyError(
                f"Twitter fetch failed for @{username}: invalid or expired Apify API token (401)"
            ) from exc
        if status == 429:
            raise ApifyError(
                f"Twitter fetch failed for @{username}: Apify rate limit exceeded (429)"
            ) from exc
        raise ApifyError(f"Twitter fetch failed for @{username}: {exc}") from exc
    if isinstance(exc, RequestsTimeout):
        raise ApifyError(f"Twitter fetch timed out for @{username}: {exc}") from exc
    raise exc


def _normalize_username(username: str) -> str:
    """Strip @ and whitespace."""
    return (username or "").strip().lstrip("@").strip()


def _item_to_text(item: Any) -> str:
    """Extract tweet text from a single dataset item (works across different actor outputs)."""
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
    """Extract image URLs from a single dataset item (Twitter entities / extended_entities / media)."""
    urls: list[str] = []
    if not isinstance(item, dict):
        return urls
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
            # Prefer photo over video for design extraction
            mtype = (m.get("type") or "").lower()
            if mtype and mtype != "photo" and mtype != "image":
                continue
            u = m.get("media_url_https") or m.get("media_url") or m.get("url")
            if u and isinstance(u, str) and u not in urls:
                urls.append(u)
    return urls


def _run_scraper(client: Any, actor_id: str, run_input: dict) -> tuple[list[str], list[str]]:
    """Run one Apify actor; return (tweet texts, image media URLs). Raises on API error."""
    run = client.actor(actor_id).call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    posts: list[str] = []
    media_urls: list[str] = []
    seen_media: set[str] = set()
    for item in items:
        text = _item_to_text(item).strip()
        if text:
            posts.append(text)
        for u in _item_media_urls(item):
            if u not in seen_media:
                seen_media.add(u)
                media_urls.append(u)
    return posts, media_urls


def fetch_twitter_apify(username: str, max_tweets: int = 500) -> SocialContent | None:
    """
    Fetch tweets for a Twitter user via Apify. Tries the primary actor first; if it
    returns no tweets (e.g. profile behind login), tries fallback scrapers in order.
    Requires APIFY_API_TOKEN. Returns None if no token or if all scrapers return no tweets.
    """
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    if not token:
        return None
    username = _normalize_username(username)
    if not username:
        return None
    try:
        from apify_client import ApifyClient
    except ImportError:
        return None

    client = ApifyClient(token)
    primary_input = {"handles": [username], "maxTweets": max_tweets}

    # 1) Primary scraper
    try:
        posts, media_urls = _run_scraper(client, APIFY_TWITTER_ACTOR, primary_input)
        if posts:
            return SocialContent(
                posts=posts, raw_text="\n".join(posts), media_urls=media_urls
            )
        logger.info(
            "Primary Twitter scraper returned no tweets for @%s, trying fallbacks...",
            username,
        )
    except Exception as e:
        logger.warning(
            "Primary Twitter scraper failed for @%s: %s. Trying fallbacks...",
            username,
            e,
        )

    # 2) Fallback scrapers
    for cfg in SCRAPER_FALLBACKS:
        name = cfg["name"]
        try:
            run_input = cfg["build_input"](username, max_tweets)
            posts, media_urls = _run_scraper(client, name, run_input)
            if posts:
                logger.info(
                    "Fallback scraper %s returned %d tweets for @%s",
                    name,
                    len(posts),
                    username,
                )
                return SocialContent(
                    posts=posts, raw_text="\n".join(posts), media_urls=media_urls
                )
        except Exception as e:
            logger.warning("Fallback %s failed for @%s: %s", name, username, e)
            continue

    return None
