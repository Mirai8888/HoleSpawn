"""
Discord profile ingestion for HoleSpawn.
Accepts Discord export format (user-supplied). HoleSpawn does not provide scraping tools.
"""

from typing import Any

from .loader import SocialContent


def load_from_discord(discord_data: dict[str, Any]) -> SocialContent:
    """
    Load SocialContent from a Discord export payload.

    Expects dict with at least:
      - messages: list of { content, timestamp?, channel_id?, channel_name?, server_id?, server_name?, reactions? }
      - optional: reactions_given, servers, interactions, activity_patterns, user_id, username

    Returns SocialContent with posts = message contents, raw_text = concatenated,
    and discord_data = full payload for profile/design/content to use.
    """
    if not isinstance(discord_data, dict):
        return SocialContent(posts=[], raw_text="", discord_data=None)

    messages = discord_data.get("messages") or []
    posts: list[str] = []
    for m in messages:
        if isinstance(m, dict):
            content = m.get("content") or m.get("body") or ""
            if isinstance(content, str) and content.strip():
                posts.append(content.strip())
        elif isinstance(m, str) and m.strip():
            posts.append(m.strip())

    raw_text = "\n".join(posts) if posts else ""
    return SocialContent(posts=posts, raw_text=raw_text, discord_data=discord_data)
