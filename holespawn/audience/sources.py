"""
Load or fetch someone's "following" list using free tools:
- File: one handle/URL per line (no API key)
- Bluesky: public API, no auth (free)
- Mastodon: requires user token (free app registration)
"""

import os
import re
from pathlib import Path
from typing import Iterator

try:
    import requests
except ImportError:
    requests = None

BLUESKY_API = "https://public.api.bsky.app"
BLUESKY_GET_FOLLOWS = f"{BLUESKY_API}/xrpc/app.bsky.graph.getFollows"
BLUESKY_GET_AUTHOR_FEED = f"{BLUESKY_API}/xrpc/app.bsky.feed.getAuthorFeed"
DEFAULT_REQUEST_TIMEOUT = 15
USER_AGENT = "HoleSpawn/1.0 (CLI; audience mapping)"


def _session() -> "requests.Session":
    if requests is None:
        raise ImportError("Install requests: pip install requests")
    s = requests.Session()
    s.headers.setdefault("Accept", "application/json")
    s.headers.setdefault("User-Agent", USER_AGENT)
    s.timeout = DEFAULT_REQUEST_TIMEOUT
    return s


def _normalize_bluesky_handle(handle: str) -> str:
    """Ensure handle has .bsky.social or similar."""
    handle = handle.strip().lower()
    if not handle:
        return ""
    if "@" in handle:
        handle = handle.split("@")[0]
    if "." not in handle:
        handle = f"{handle}.bsky.social"
    return handle


def load_following_from_file(path: str | Path) -> list[str]:
    """
    Load a list of handles/URLs from a file (one per line).
    Strips whitespace and empty lines. Use any platform (Bluesky, Mastodon, etc.).
    """
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Optional: extract handle from URL
        if "bsky.app/profile/" in line:
            m = re.search(r"bsky\.app/profile/([^\s/]+)", line)
            if m:
                line = m.group(1)
        elif "mastodon" in line or "/@" in line:
            m = re.search(r"@?([a-zA-Z0-9_.]+@[a-zA-Z0-9.-]+)", line)
            if m:
                line = m.group(1)
        out.append(line)
    return out


def fetch_following_bluesky(
    handle: str,
    limit: int = 200,
    cursor: str | None = None,
) -> tuple[list[str], str | None]:
    """
    Fetch who a Bluesky user follows. No API key required (public API).
    Returns (list of handles, next_cursor or None).
    """
    handle = _normalize_bluesky_handle(handle)
    if not handle:
        return [], None
    sess = _session()
    params = {"actor": handle, "limit": min(limit, 100)}
    if cursor:
        params["cursor"] = cursor
    resp = sess.get(BLUESKY_GET_FOLLOWS, params=params)
    resp.raise_for_status()
    data = resp.json()
    follows = data.get("follows") or []
    handles = []
    for f in follows:
        h = f.get("handle") or f.get("did")
        if h:
            handles.append(h)
    return handles, data.get("cursor")


def fetch_all_following_bluesky(handle: str, max_following: int = 500) -> list[str]:
    """Paginate through Bluesky following until max_following or end."""
    all_handles = []
    cursor = None
    while len(all_handles) < max_following:
        batch, cursor = fetch_following_bluesky(handle, limit=100, cursor=cursor)
        all_handles.extend(batch)
        if not cursor or not batch:
            break
    return all_handles[:max_following]


def fetch_posts_bluesky(handle: str, limit: int = 30) -> list[str]:
    """Fetch recent posts from a Bluesky user (public, no auth). Returns list of post text."""
    handle = _normalize_bluesky_handle(handle)
    if not handle:
        return []
    sess = _session()
    params = {"actor": handle, "limit": min(limit, 100)}
    resp = sess.get(BLUESKY_GET_AUTHOR_FEED, params=params)
    resp.raise_for_status()
    data = resp.json()
    feed = data.get("feed") or []
    texts = []
    for item in feed:
        post = item.get("post") or {}
        record = post.get("record") or {}
        text = record.get("text") or ""
        if text.strip():
            texts.append(text.strip())
    return texts


def fetch_following_mastodon(
    instance_url: str,
    username: str,
    token: str | None = None,
    limit: int = 200,
) -> list[str]:
    """
    Fetch who a Mastodon user follows. Requires OAuth token (user creates app + token on instance).
    instance_url: e.g. https://mastodon.social
    username: account username (no @)
    token: from Preferences → Development → Your application → access token
    """
    if not token:
        token = os.getenv("MASTODON_ACCESS_TOKEN")
    if not token:
        raise ValueError(
            "Mastodon following list requires an access token. "
            "Set MASTODON_ACCESS_TOKEN or pass token= (create app on your instance → get token)."
        )
    instance_url = instance_url.rstrip("/")
    sess = _session()
    sess.headers["Authorization"] = f"Bearer {token}"

    # Resolve account id
    lookup = sess.get(f"{instance_url}/api/v1/accounts/lookup", params={"acct": username})
    lookup.raise_for_status()
    acc = lookup.json()
    acc_id = acc.get("id")
    if not acc_id:
        return []

    # Paginate following
    following = []
    url = f"{instance_url}/api/v1/accounts/{acc_id}/following"
    params = {"limit": min(80, limit)}
    while len(following) < limit:
        resp = sess.get(url, params=params)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for acc in batch:
            acct = acc.get("acct") or acc.get("username") or ""
            if acc.get("url") and "@" not in acct:
                acct = f"{acct}@{instance_url.replace('https://', '').split('/')[0]}"
            if acct:
                following.append(acct)
        if len(batch) < params["limit"]:
            break
        # Mastodon uses Link header or max_id for pagination
        link = resp.headers.get("Link")
        next_url = None
        if link:
            for part in link.split(","):
                if 'rel="next"' in part:
                    m = re.search(r"<([^>]+)>", part)
                    if m:
                        next_url = m.group(1)
                        break
        if not next_url:
            break
        url = next_url
        params = {}
    return following[:limit]


def fetch_posts_mastodon(
    instance_url: str,
    username: str,
    token: str | None = None,
    limit: int = 20,
) -> list[str]:
    """Fetch recent public statuses for a Mastodon account. Token optional for public accounts."""
    instance_url = instance_url.rstrip("/")
    sess = _session()
    if token:
        sess.headers["Authorization"] = f"Bearer {token}"
    lookup = sess.get(f"{instance_url}/api/v1/accounts/lookup", params={"acct": username})
    lookup.raise_for_status()
    acc = lookup.json()
    acc_id = acc.get("id")
    if not acc_id:
        return []
    resp = sess.get(
        f"{instance_url}/api/v1/accounts/{acc_id}/statuses",
        params={"limit": limit, "exclude_replies": True},
    )
    resp.raise_for_status()
    statuses = resp.json()
    return [s.get("content", "") or "" for s in statuses if s.get("content")]
