"""
Optional Twitter ingestion via Apify (actor u6ppkMWAx2E2MpEuF).
Requires APIFY_API_TOKEN. Returns None if no token; raises ApifyError on API failure.
"""

import os
from pathlib import Path

from holespawn.errors import ApifyError
from .loader import SocialContent

APIFY_TWITTER_ACTOR = "u6ppkMWAx2E2MpEuF"


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
    except Exception as e:
        _reraise_apify_error(e, username)

    posts = []
    for item in items:
        if isinstance(item, dict):
            text = item.get("full_text") or item.get("text") or item.get("content") or ""
        else:
            text = str(item)
        if text and text.strip():
            posts.append(text.strip())
    return SocialContent(posts=posts, raw_text="\n".join(posts)) if posts else None
