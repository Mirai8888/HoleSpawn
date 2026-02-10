"""
Fetch a Twitter user's following list via live backend.

- If APIFY_API_TOKEN is set, prefer Apify managed scrapers.
- Otherwise, fall back to self-hosted Playwright scraper (requires cookies).
"""

import os

from holespawn.errors import ApifyError, ScraperError
from holespawn.scraper.sync import fetch_following


def fetch_following_apify(
    username: str,
    max_results: int = 200,
    actor_id: str | None = None,
) -> list[str]:
    """
    Fetch the list of usernames that a Twitter user follows.
    Returns list of screen names (without @).

    If APIFY_API_TOKEN is set and apify-client is installed, uses Apify.
    Otherwise uses the self-hosted scraper.
    """
    username = (username or "").strip().lstrip("@").strip()
    if not username:
        return []
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    if token:
        actor = actor_id or os.getenv("APIFY_FOLLOWING_ACTOR") or "powerai/twitter-following-scraper"
        try:
            from apify_client import ApifyClient
        except Exception as e:
            raise ApifyError("apify-client not installed; run: pip install apify-client") from e
        client = ApifyClient(token)
        try:
            run_input = {"screenname": username, "maxResults": min(max_results, 1000)}
            run = client.actor(actor).call(run_input=run_input)
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        except Exception as e:
            raise ApifyError(f"Following list failed for @{username}: {e}") from e

        handles: list[str] = []
        for item in items:
            if isinstance(item, dict):
                h = item.get("screen_name") or item.get("username") or item.get("handle") or item.get("screenName")
                if h:
                    handles.append(str(h).strip().lstrip("@"))
            elif isinstance(item, str):
                handles.append(item.strip().lstrip("@"))
        return handles[:max_results]

    # Fallback: self-hosted scraper
    try:
        return fetch_following(username, max_results=min(max_results, 1000))
    except FileNotFoundError as e:
        raise ScraperError("No X session cookies. Run: python -m holespawn.scraper login") from e
