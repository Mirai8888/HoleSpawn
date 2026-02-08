"""
Optional: fetch a Twitter user's following list via Apify (paid API).
Requires APIFY_API_TOKEN. Returns [] if no token; raises ApifyError on API failure.
"""

import os

from holespawn.errors import ApifyError

# Default: Twitter Following Scraper (Apify Store). Override with APIFY_FOLLOWING_ACTOR.
APIFY_FOLLOWING_ACTOR_DEFAULT = "powerai/twitter-following-scraper"


def fetch_following_apify(
    username: str,
    max_results: int = 200,
    actor_id: str | None = None,
) -> list[str]:
    """
    Fetch the list of usernames that a Twitter user follows, via Apify.
    Requires APIFY_API_TOKEN. Returns list of screen names (without @).
    Returns [] if no token, actor unavailable, or on error.
    """
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    if not token:
        return []
    username = (username or "").strip().lstrip("@").strip()
    if not username:
        return []
    actor = actor_id or os.getenv("APIFY_FOLLOWING_ACTOR") or APIFY_FOLLOWING_ACTOR_DEFAULT
    try:
        from apify_client import ApifyClient
    except ImportError:
        return []

    client = ApifyClient(token)
    try:
        run_input = {"screenname": username, "maxResults": min(max_results, 1000)}
        run = client.actor(actor).call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as e:
        raise ApifyError(f"Following list failed for @{username}: {e}") from e

    handles = []
    for item in items:
        if isinstance(item, dict):
            # Common field names from following/followers actors
            h = (
                item.get("screen_name")
                or item.get("username")
                or item.get("handle")
                or item.get("screenName")
            )
            if h:
                handles.append(str(h).strip().lstrip("@"))
        elif isinstance(item, str):
            handles.append(item.strip().lstrip("@"))
    return handles[:max_results]
