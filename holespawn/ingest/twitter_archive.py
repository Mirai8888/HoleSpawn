"""
Parse Twitter/X archive ZIP files.
Extracts tweets from data/tweets.js (and data/tweets-part*.js).
Handles the "window.YTD.tweets.part0 = " wrapper.
"""

import json
import re
import zipfile
from pathlib import Path

from .loader import SocialContent


def _strip_ytd_wrapper(raw: str) -> str:
    """Remove window.YTD.tweets.partN = prefix so the rest is valid JSON."""
    # Match window.YTD.tweets.part0 = or part1, part2, etc.
    match = re.match(r"^\s*window\.YTD\.tweets\.part\d+\s*=\s*", raw)
    if match:
        return raw[match.end() :].strip()
    return raw.strip()


def _extract_tweets_from_js(content: str) -> list[str]:
    """Parse tweets.js content; return list of full_text."""
    content = _strip_ytd_wrapper(content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    posts = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tweet = item.get("tweet") or item
        if isinstance(tweet, dict):
            text = tweet.get("full_text") or tweet.get("text") or ""
        else:
            text = str(tweet) if tweet else ""
        if text and text.strip():
            posts.append(text.strip())
    return posts


def load_from_twitter_archive(zip_path: str | Path) -> SocialContent:
    """
    Load tweets from a Twitter archive ZIP.
    Expects data/tweets.js or data/tweets-part0.js, data/tweets-part1.js, etc.
    Extracts full_text from each tweet; created_at and engagement metrics are
    available in the raw tweet object but we only return post text for profile building.
    Returns empty content on invalid or missing ZIP.
    """
    zip_path = Path(zip_path)
    if not zip_path.exists() or zip_path.suffix.lower() != ".zip":
        return SocialContent(posts=[], raw_text="")

    all_posts = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            candidates = [n for n in zf.namelist() if "tweets" in n.lower() and n.endswith(".js")]
            candidates.sort()
            for name in candidates:
                try:
                    raw = zf.read(name).decode("utf-8", errors="replace")
                    all_posts.extend(_extract_tweets_from_js(raw))
                except Exception:
                    continue
    except zipfile.BadZipFile:
        return SocialContent(posts=[], raw_text="")
    return SocialContent(posts=all_posts, raw_text="\n".join(all_posts))
