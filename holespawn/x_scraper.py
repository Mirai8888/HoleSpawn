"""
Scrape X.com (Twitter) user tweets and (optionally) following list.
Uses ntscraper (Nitter-backed); no X API key. Nitter instances can be unstable.
"""

import os
import re
from typing import Optional

# x.com and twitter.com user URL patterns
X_USER_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/(?:#!)?([a-zA-Z0-9_]+)/?",
    re.IGNORECASE,
)


def parse_x_username(url_or_handle: str) -> Optional[str]:
    """Extract username from x.com/twitter.com URL or return handle as-is if it looks like a username."""
    s = (url_or_handle or "").strip()
    if not s:
        return None
    m = X_USER_PATTERN.match(s)
    if m:
        return m.group(1)
    if re.match(r"^[a-zA-Z0-9_]{1,15}$", s):
        return s
    return None


# Nitter instances to try (public instances can be down; user can set NITTER_INSTANCE env)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
]


def scrape_x_user_tweets(
    username: str,
    max_tweets: int = 100,
) -> list[str]:
    """
    Scrape recent tweets from an X/Twitter user. No API key.
    Uses ntscraper (Nitter). Returns list of tweet text strings.
    Nitter instances can be down; set NITTER_INSTANCE env to a working URL if needed.
    """
    try:
        from ntscraper import Nitter
    except ImportError:
        raise ImportError("Install ntscraper: pip install ntscraper") from None

    username = (username or "").strip().lstrip("@")
    if not username:
        return []

    instances = [os.environ.get("NITTER_INSTANCE")] if os.environ.get("NITTER_INSTANCE") else NITTER_INSTANCES
    instances = [u for u in instances if u]
    if not instances:
        instances = NITTER_INSTANCES

    tweets = []
    for instance in instances:
        try:
            scraper = Nitter(instances=[instance], log_level=0, skip_instance_check=True)
            result = scraper.get_tweets(username, mode="user", number=max_tweets, instance=instance)
            break
        except Exception:
            continue
    else:
        return []

    # ntscraper returns dict with 'tweets' key or list of dicts
    if isinstance(result, dict) and "tweets" in result:
        items = result["tweets"]
    elif isinstance(result, list):
        items = result
    else:
        items = []

    for item in items:
        if isinstance(item, dict):
            text = item.get("text") or item.get("tweet") or item.get("content") or ""
        else:
            text = getattr(item, "text", None) or getattr(item, "tweet", "") or str(item)
        if text and isinstance(text, str) and text.strip():
            tweets.append(text.strip())
    return tweets


def scrape_x_following(
    username: str,
    max_following: int = 200,
) -> list[str]:
    """
    Try to get list of usernames that this X user follows.
    Uses Nitter /username/following page (HTML scrape). May fail if Nitter is down.
    Returns list of @handles (without @).
    """
    username = (username or "").strip().lstrip("@")
    if not username:
        return []

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        raise ImportError("Install requests and beautifulsoup4 for following list") from e

    # Try common Nitter instance URLs (user-provided or default)
    instances = [
        "https://nitter.net",
        "https://nitter.privacydev.net",
    ]
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
    session.headers["Accept"] = "text/html,application/xhtml+xml"
    following = []

    for base in instances:
        url = f"{base.rstrip('/')}/{username}/following"
        try:
            r = session.get(url, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            # Nitter: links to /username in the following list
            for a in soup.select("a.username"):
                href = a.get("href") or ""
                parts = href.strip("/").split("/")
                if parts and parts[-1] and parts[-1] != username:
                    following.append(parts[-1])
                    if len(following) >= max_following:
                        return following[:max_following]
            if following:
                return following[:max_following]
            # Alternative: any link that looks like /user
            for a in soup.find_all("a", href=True):
                m = re.match(r"^/?([a-zA-Z0-9_]+)/?$", a.get("href", "").strip("/").split("?")[0].split("/")[-1])
                if m and m.group(1) != username and m.group(1) not in ("following", "followers", "search"):
                    following.append(m.group(1))
                    if len(following) >= max_following:
                        return list(dict.fromkeys(following))[:max_following]
            if following:
                return list(dict.fromkeys(following))[:max_following]
        except Exception:
            continue
    return list(dict.fromkeys(following))[:max_following]
