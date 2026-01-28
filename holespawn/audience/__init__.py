"""Audience mapping: following list → susceptibility profile (free tools: file, Bluesky, Mastodon)."""

from .sources import (
    load_following_from_file,
    fetch_following_bluesky,
    fetch_following_mastodon,
)
from .map_audience import map_audience_susceptibility, AudienceProfile

__all__ = [
    "load_following_from_file",
    "fetch_following_bluesky",
    "fetch_following_mastodon",
    "map_audience_susceptibility",
    "AudienceProfile",
]
