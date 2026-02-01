"""
Optional Twitter ingestion via Apify (actor u6ppkMWAx2E2MpEuF).
Requires APIFY_API_TOKEN. Fails gracefully if no token or actor error.
"""

import os
import re
from pathlib import Path

from .loader import SocialContent

APIFY_TWITTER_ACTOR = "u6ppkMWAx2E2MpEuF"


def _normalize_username(username: str) -> str:
    """Strip @ and whitespace."""
    return (username or "").strip().lstrip("@").strip()


def fetch_twitter_apify(username: str, max_tweets: int = 500) -> SocialContent | None:
    """
    Fetch tweets for a Twitter user via Apify actor u6ppkMWAx2E2MpEuF.
    Requires APIFY_API_TOKEN in environment (or .env). Returns None if no token
    or on failure (graceful).
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
    try:
        run = client.actor(APIFY_TWITTER_ACTOR).call(
            run_input={"handles": [username], "maxTweets": max_tweets},
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception:
        return None

    posts = []
    for item in items:
        if isinstance(item, dict):
            text = item.get("full_text") or item.get("text") or item.get("content") or ""
        else:
            text = str(item)
        if text and text.strip():
            posts.append(text.strip())
    return SocialContent(posts=posts, raw_text="\n".join(posts)) if posts else None
