"""Ingest Twitter/X and Discord data: file, archive, or optional Apify (paid API)."""

from .loader import load_from_file, load_from_text, SocialContent
from .twitter_archive import load_from_twitter_archive
from .apify_twitter import fetch_twitter_apify
from .apify_following import fetch_following_apify
from .discord import load_from_discord

__all__ = [
    "load_from_file",
    "load_from_text",
    "SocialContent",
    "load_from_twitter_archive",
    "fetch_twitter_apify",
    "fetch_following_apify",
    "load_from_discord",
]
