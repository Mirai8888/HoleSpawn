"""
Map "audience susceptibility" from a person's following list:
aggregate themes, sentiment, and inferred susceptibility from followed accounts' content.
Uses free tools only (file, Bluesky public API, Mastodon with user token).
"""

import re
from dataclasses import dataclass, field

from holespawn.profile import build_profile
from holespawn.ingest import SocialContent

try:
    from .sources import fetch_posts_bluesky
except ImportError:
    fetch_posts_bluesky = None


@dataclass
class AudienceProfile:
    """Aggregate profile of who the subject follows → what their audience is susceptible to."""

    themes: list[tuple[str, float]] = field(default_factory=list)
    sentiment_compound: float = 0.0
    sentiment_positive: float = 0.0
    sentiment_negative: float = 0.0
    intensity: float = 0.0
    sample_phrases: list[str] = field(default_factory=list)
    summary: str = ""  # short text: "audience is most susceptible to X, Y, Z"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).replace("&nbsp;", " ").strip()


def _fetch_posts_for_handles(
    handles: list[str],
    sample_size: int,
    posts_per_handle: int = 20,
) -> list[str]:
    """Fetch recent posts for a sample of handles. Bluesky only (no auth); Mastodon needs token per-instance."""
    posts = []
    # Prefer Bluesky handles (no auth)
    bluesky_handles = [h for h in handles if "bsky" in h or ".bsky.social" in h or (h and "." in h and "@" not in h)]
    if not bluesky_handles:
        bluesky_handles = handles[:sample_size]
    sample = bluesky_handles[:sample_size]
    for handle in sample:
        try:
            if "bsky" in handle or ".bsky.social" in handle or (handle and "." in handle and "@" not in handle):
                if fetch_posts_bluesky:
                    batch = fetch_posts_bluesky(handle, limit=posts_per_handle)
                    posts.extend(batch)
            # Mastodon: handle like user@instance.social — would need instance + token; skip for simplicity in auto-fetch
        except Exception:
            continue
    return posts


def map_audience_susceptibility(
    following_handles: list[str],
    *,
    sample_size: int = 25,
    posts_per_handle: int = 15,
    fetch_posts: bool = True,
    existing_posts: list[str] | None = None,
) -> AudienceProfile:
    """
    Map what the subject's audience (who they follow) is most susceptible to.
    - following_handles: list of handles from load_following_from_file or fetch_following_bluesky/mastodon.
    - sample_size: how many followed accounts to sample for post fetch.
    - posts_per_handle: max posts per account when fetching.
    - fetch_posts: if True, fetch recent posts for sample via Bluesky public API (free).
    - existing_posts: if provided, use these as audience content instead of fetching (e.g. from file).
    """
    posts = list(existing_posts) if existing_posts else []
    if fetch_posts and not posts and following_handles:
        raw = _fetch_posts_for_handles(following_handles, sample_size, posts_per_handle)
        posts = [_strip_html(t) for t in raw if t.strip()]
    if not posts:
        return AudienceProfile(
            themes=[],
            summary="No audience content available. Add --following-file with handles and ensure Bluesky handles (user.bsky.social) for auto-fetch, or provide audience posts in a file.",
        )
    content = SocialContent(posts=posts)
    profile = build_profile(content)
    # Build a short susceptibility summary from top themes and sentiment
    top_themes = [t[0] for t in profile.themes[:12]]
    sentiment = "positive" if profile.sentiment_compound > 0.15 else "negative" if profile.sentiment_compound < -0.15 else "mixed"
    summary = (
        f"Audience (who they follow) engages with: {', '.join(top_themes[:8])}. "
        f"Overall tone: {sentiment}. "
        f"Emotional intensity: {'high' if profile.intensity > 0.5 else 'moderate' if profile.intensity > 0.2 else 'low'}. "
        f"Content that resonates with this audience tends to mirror these themes and tone."
    )
    return AudienceProfile(
        themes=profile.themes,
        sentiment_compound=profile.sentiment_compound,
        sentiment_positive=profile.sentiment_positive,
        sentiment_negative=profile.sentiment_negative,
        intensity=profile.intensity,
        sample_phrases=profile.sample_phrases,
        summary=summary,
    )
