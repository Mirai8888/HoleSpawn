"""Ingest Twitter/X data: file, Twitter archive ZIP, or optional Apify (paid API)."""

from .loader import load_from_file, load_from_text, SocialContent
from .twitter_archive import load_from_twitter_archive
from .apify_twitter import fetch_twitter_apify
from .apify_following import fetch_following_apify

__all__ = [
    "load_from_file",
    "load_from_text",
    "SocialContent",
    "load_from_twitter_archive",
    "fetch_twitter_apify",
    "fetch_following_apify",
]
