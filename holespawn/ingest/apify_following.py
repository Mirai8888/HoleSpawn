"""
Fetch a Twitter user's following list via self-hosted scraper (Playwright).
Requires X session: python -m holespawn.scraper login
"""

from holespawn.errors import ScraperError
from holespawn.scraper.sync import fetch_following


def fetch_following_apify(
    username: str,
    max_results: int = 200,
    actor_id: str | None = None,
) -> list[str]:
    """
    Fetch the list of usernames that a Twitter user follows, via self-hosted scraper.
    Returns list of screen names (without @). Raises ScraperError if no session or fetch fails.
    (actor_id ignored; kept for API compatibility.)
    """
    username = (username or "").strip().lstrip("@").strip()
    if not username:
        return []
    try:
        return fetch_following(username, max_results=min(max_results, 1000))
    except FileNotFoundError as e:
        raise ScraperError(
            "No X session cookies. Run: python -m holespawn.scraper login"
        ) from e
