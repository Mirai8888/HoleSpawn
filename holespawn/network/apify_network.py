"""
Optional: build network profiles via paid APIs / live scraping.
Fetch a target user's following list, then fetch tweets and profile each account.
Uses the same Twitter scraper as main ingest (self-hosted Playwright).
"""

from dataclasses import asdict
from typing import Any

from holespawn.ingest import fetch_twitter_apify
from holespawn.ingest.apify_following import fetch_following_apify
from holespawn.profile import build_profile


def _profile_to_dict(profile: Any) -> dict[str, Any]:
    """Convert PsychologicalProfile to JSON-serializable dict (themes as list of lists)."""
    d = asdict(profile)
    d["themes"] = [list(t) for t in d["themes"]]
    return d


def fetch_profiles_via_apify(
    target_username: str,
    max_following: int = 50,
    max_tweets_per_user: int = 300,
    include_target: bool = True,
) -> dict[str, dict[str, Any]]:
    """
    Fetch target's following list via Twitter scraper, then for each user fetch tweets and build profile.
    Returns dict: username -> profile dict (same shape as load_profiles_from_dir).
    Capped by max_following to control cost and rate.
    """
    target_username = (target_username or "").strip().lstrip("@")
    if not target_username:
        return {}

    following = fetch_following_apify(target_username, max_results=max_following)
    if not following:
        # Fallback: just profile the target
        following = [target_username] if include_target else []
    elif include_target and target_username not in following:
        following = [target_username] + [u for u in following if u != target_username][
            : max_following - 1
        ]

    profiles: dict[str, dict[str, Any]] = {}
    for username in following:
        content = fetch_twitter_apify(username, max_tweets=max_tweets_per_user)
        if content is None or not list(content.iter_posts()):
            continue
        try:
            profile = build_profile(content)
            profiles[username] = _profile_to_dict(profile)
        except Exception:
            continue
    return profiles
