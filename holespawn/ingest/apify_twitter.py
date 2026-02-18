"""
Twitter/X ingestion via live backends.

- If APIFY_API_TOKEN is set, prefer Apify managed scrapers.
- Otherwise, fall back to self-hosted Playwright scraper (requires cookies).
"""

import logging
import os
from typing import Any

from holespawn.errors import ApifyError, ScraperError
from holespawn.scraper.sync import fetch_tweets
from holespawn.scraper.sync import fetch_tweets_raw as _fetch_tweets_raw

from .loader import SocialContent

logger = logging.getLogger(__name__)

# Primary: profile/timeline scraper (Apify actor id)
APIFY_TWITTER_ACTOR = "u6ppkMWAx2E2MpEuF"

# Fallback scrapers: tried in order when primary returns 0 tweets.
SCRAPER_FALLBACKS = [
    {
        "name": "apidojo/tweet-scraper",
        "build_input": lambda username, max_tweets: {
            "twitterHandles": [username],
            "maxItems": min(max_tweets, 1000),
        },
    },
]


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


def _run_apify_raw(client: Any, actor_id: str, run_input: dict) -> list[dict]:
    """Run one Apify actor; return raw dataset items. Raises on API error."""
    run = client.actor(actor_id).call(run_input=run_input)
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def _apify_token() -> str | None:
    return os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")


def fetch_twitter_apify(username: str, max_tweets: int = 500) -> SocialContent | None:
    """
    Fetch tweets for a Twitter user via live backend.
    Prefers Apify when APIFY_API_TOKEN is set; otherwise uses the self-hosted scraper.
    Returns None on no data.
    """
    username = _normalize_username(username)
    if not username:
        return None
    token = _apify_token()
    if token:
        try:
            from apify_client import ApifyClient
        except Exception as e:
            raise ApifyError("apify-client not installed; run: pip install apify-client") from e
        client = ApifyClient(token)
        primary_input = {"handles": [username], "maxTweets": max_tweets}
        try:
            items = _run_apify_raw(client, APIFY_TWITTER_ACTOR, primary_input)
            if items:
                posts = []
                media_urls = []
                seen_media = set()
                for it in items:
                    text = _item_to_text(it).strip()
                    if text:
                        posts.append(text)
                    for u in _item_media_urls(it):
                        if u not in seen_media:
                            seen_media.add(u)
                            media_urls.append(u)
                if posts:
                    return SocialContent(posts=posts, raw_text="\n".join(posts), media_urls=media_urls)
        except Exception as e:
            raise ApifyError(f"Twitter fetch failed for @{username}: {e}") from e

        for cfg in SCRAPER_FALLBACKS:
            try:
                run_input = cfg["build_input"](username, max_tweets)
                items = _run_apify_raw(client, cfg["name"], run_input)
                if items:
                    posts = []
                    media_urls = []
                    seen_media = set()
                    for it in items:
                        text = _item_to_text(it).strip()
                        if text:
                            posts.append(text)
                        for u in _item_media_urls(it):
                            if u not in seen_media:
                                seen_media.add(u)
                                media_urls.append(u)
                    if posts:
                        return SocialContent(posts=posts, raw_text="\n".join(posts), media_urls=media_urls)
            except Exception as e:
                logger.warning("Apify fallback %s failed for @%s: %s", cfg["name"], username, e)

        return None

    # Fallback: self-hosted scraper
    try:
        tweets = fetch_tweets(username, max_tweets=max_tweets)
    except FileNotFoundError as e:
        raise ScraperError("No X session cookies. Run: python -m holespawn.scraper login") from e
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
    Prefers Apify when APIFY_API_TOKEN is set; otherwise uses the self-hosted scraper.
    """
    username = _normalize_username(username)
    if not username:
        return None
    token = _apify_token()
    if token:
        try:
            from apify_client import ApifyClient
        except Exception as e:
            raise ApifyError("apify-client not installed; run: pip install apify-client") from e
        client = ApifyClient(token)
        primary_input = {"handles": [username], "maxTweets": max_tweets}
        try:
            items = _run_apify_raw(client, APIFY_TWITTER_ACTOR, primary_input)
            if items:
                return items
        except Exception as e:
            logger.warning("Apify primary failed for @%s: %s", username, e)
        for cfg in SCRAPER_FALLBACKS:
            try:
                run_input = cfg["build_input"](username, max_tweets)
                items = _run_apify_raw(client, cfg["name"], run_input)
                if items:
                    return items
            except Exception as e:
                logger.warning("Apify fallback %s failed for @%s: %s", cfg["name"], username, e)
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
