"""
Community Archive connector: pirate epistemic.garden's open Supabase DB
(community-archive.org) as an intelligence source.

17M+ tweets from 332 accounts, openly queryable via PostgREST.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

SUPABASE_URL = "https://fabxmporizzqflnftavs.supabase.co/rest/v1"
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZhYnhtcG9yaXp6cWZsbmZ0YXZzIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3MjIyNDQ5MTIsImV4cCI6MjAzNzgyMDkxMn0."
    "UIEJiUNkLsW28tBHmG-RQDW-I5JNlJLt62CSk9D_qG8"
)

DATA_DIR = Path.home() / "HoleSpawn" / "data" / "community-archive"


class CommunityArchiveClient:
    """Supabase REST (PostgREST) client with pagination for community-archive.org."""

    def __init__(
        self,
        base_url: str = SUPABASE_URL,
        api_key: str = SUPABASE_ANON_KEY,
        page_size: int = 1000,
        rate_limit_delay: float = 0.25,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "count=exact",
        })
        self.page_size = page_size
        self.rate_limit_delay = rate_limit_delay

    # ── low-level ────────────────────────────────────────────────

    def _get(self, table: str, params: dict | None = None) -> list[dict]:
        """Single request to a table."""
        url = f"{self.base_url}/{table}"
        resp = self.session.get(url, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def _get_paginated(self, table: str, params: dict | None = None,
                       limit: int | None = None) -> list[dict]:
        """Paginate through a table using Range headers."""
        params = dict(params or {})
        results: list[dict] = []
        offset = 0
        while True:
            end = offset + self.page_size - 1
            if limit is not None:
                end = min(end, limit - 1)
            headers = {"Range": f"{offset}-{end}"}
            url = f"{self.base_url}/{table}"
            resp = self.session.get(url, params=params, headers=headers)
            if resp.status_code == 416:  # Range not satisfiable = no more data
                break
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            results.extend(batch)
            if limit is not None and len(results) >= limit:
                results = results[:limit]
                break
            if len(batch) < self.page_size:
                break
            offset += self.page_size
            time.sleep(self.rate_limit_delay)
        return results

    # ── high-level queries ───────────────────────────────────────

    def list_accounts(self) -> list[dict]:
        """All archived accounts (username, account_id, etc)."""
        return self._get_paginated("account", {"select": "*"})

    def get_profile(self, username: str) -> dict | None:
        """Profile for a username (bio, avatar, etc)."""
        rows = self._get("profile", {
            "select": "*",
            "account_id": f"eq.{self._account_id_for(username)}",
            "order": "archive_upload_id.desc",
            "limit": "1",
        })
        # If profile table links by account_id, try direct username lookup too
        if not rows:
            rows = self._get("profile", {
                "select": "*,account!inner(username)",
                "account.username": f"eq.{username}",
                "order": "archive_upload_id.desc",
                "limit": "1",
            })
        return rows[0] if rows else None

    def get_account_by_username(self, username: str) -> dict | None:
        """Get account row by username."""
        rows = self._get("account", {
            "select": "*",
            "username": f"eq.{username}",
            "limit": "1",
        })
        return rows[0] if rows else None

    def _account_id_for(self, username: str) -> str:
        """Resolve username to account_id."""
        acct = self.get_account_by_username(username)
        if not acct:
            raise ValueError(f"Account not found: {username}")
        return acct["account_id"]

    def get_tweets(
        self,
        account_id: str,
        since: str | None = None,
        until: str | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Tweets for an account_id, optionally filtered by time range."""
        params: dict[str, str] = {
            "select": "*",
            "account_id": f"eq.{account_id}",
            "order": "created_at.desc",
        }
        if since:
            params["created_at"] = f"gte.{since}"
        if until:
            params["created_at"] = params.get("created_at", "") and \
                f"gte.{since}" if since else ""
            # PostgREST needs separate filters; use `and` syntax
            if since and until:
                params.pop("created_at", None)
                params["and"] = f"(created_at.gte.{since},created_at.lte.{until})"
            elif until:
                params["created_at"] = f"lte.{until}"
        return self._get_paginated("tweets", params, limit=limit)

    def get_followers(self, account_id: str) -> list[dict]:
        """Follower records for an account."""
        return self._get_paginated("followers", {
            "select": "*",
            "account_id": f"eq.{account_id}",
        })

    def get_following(self, account_id: str) -> list[dict]:
        """Following records for an account."""
        return self._get_paginated("following", {
            "select": "*",
            "account_id": f"eq.{account_id}",
        })

    def get_mentions(self, account_id: str) -> list[dict]:
        """User mentions from tweets by this account."""
        return self._get_paginated("user_mentions", {
            "select": "*,tweets!inner(account_id)",
            "tweets.account_id": f"eq.{account_id}",
        })

    def get_conversations(self, conversation_id: str) -> list[dict]:
        """Full reply chain for a conversation."""
        return self._get_paginated("tweets", {
            "select": "*",
            "conversation_id": f"eq.{conversation_id}",
            "order": "created_at.asc",
        })

    def get_quote_tweets(self, account_id: str) -> list[dict]:
        """Quote tweets by this account."""
        return self._get_paginated("quote_tweets", {
            "select": "*",
            "account_id": f"eq.{account_id}",
        })

    def get_retweets(self, account_id: str) -> list[dict]:
        """Retweets by this account."""
        return self._get_paginated("retweets", {
            "select": "*",
            "account_id": f"eq.{account_id}",
        })


# ── Harvesting ───────────────────────────────────────────────────

def harvest_account(
    username: str,
    client: CommunityArchiveClient | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Pull everything for one account, save to disk.

    Returns dict with all harvested data keyed by type.
    """
    client = client or CommunityArchiveClient()
    acct = client.get_account_by_username(username)
    if not acct:
        logger.warning("Account not found in archive: %s", username)
        return {}

    account_id = acct["account_id"]
    out = output_dir or DATA_DIR / username
    out.mkdir(parents=True, exist_ok=True)

    logger.info("Harvesting %s (account_id=%s)", username, account_id)

    data: dict[str, Any] = {"account": acct}

    # Profile
    profile = client.get_profile(username)
    data["profile"] = profile
    _save_json(out / "profile.json", profile)

    # Tweets
    tweets = client.get_tweets(account_id, limit=50000)
    data["tweets"] = tweets
    _save_json(out / "tweets.json", tweets)

    # Followers
    followers = client.get_followers(account_id)
    data["followers"] = followers
    _save_json(out / "followers.json", followers)

    # Following
    following = client.get_following(account_id)
    data["following"] = following
    _save_json(out / "following.json", following)

    # Mentions
    mentions = client.get_mentions(account_id)
    data["mentions"] = mentions
    _save_json(out / "mentions.json", mentions)

    # Quote tweets
    quote_tweets = client.get_quote_tweets(account_id)
    data["quote_tweets"] = quote_tweets
    _save_json(out / "quote_tweets.json", quote_tweets)

    # Retweets
    retweets = client.get_retweets(account_id)
    data["retweets"] = retweets
    _save_json(out / "retweets.json", retweets)

    logger.info(
        "Harvested %s: %d tweets, %d followers, %d following, %d mentions, %d QTs, %d RTs",
        username, len(tweets), len(followers), len(following),
        len(mentions), len(quote_tweets), len(retweets),
    )
    return data


def _save_json(path: Path, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Network overlap ─────────────────────────────────────────────

def harvest_network_overlap(
    our_partition: dict[str, list[str]] | list[str],
    client: CommunityArchiveClient | None = None,
) -> dict[str, dict]:
    """
    Find accounts in the archive that overlap with our network partition,
    then harvest all of them.

    Args:
        our_partition: Either a list of usernames or a dict with
            community -> [usernames] from our graph analysis.
        client: Optional pre-built client.

    Returns:
        Dict mapping username -> harvested data.
    """
    client = client or CommunityArchiveClient()

    # Flatten partition to username set
    if isinstance(our_partition, dict):
        our_users = set()
        for members in our_partition.values():
            our_users.update(u.lower() for u in members)
    else:
        our_users = {u.lower() for u in our_partition}

    # Get all archived accounts
    archived = client.list_accounts()
    archived_usernames = {
        a.get("username", "").lower(): a for a in archived if a.get("username")
    }

    overlap = our_users & set(archived_usernames.keys())
    logger.info(
        "Network overlap: %d of our %d accounts found in archive (%d total archived)",
        len(overlap), len(our_users), len(archived_usernames),
    )

    harvested = {}
    for username in sorted(overlap):
        try:
            data = harvest_account(username, client=client)
            if data:
                harvested[username] = data
        except Exception as e:
            logger.error("Failed to harvest %s: %s", username, e)

    return harvested


# ── Graph conversion ─────────────────────────────────────────────

def to_holespawn_graph(harvested_data: dict[str, dict]) -> dict:
    """
    Convert harvested data into graph_builder.build_graph() input format.

    Returns dict with keys: tweets, followers, edge_map
    suitable for graph_builder.build_graph(**result).
    """
    tweets: list[dict] = []
    followers: dict[str, list[str]] = {}
    edge_map: dict[str, list[str]] = {}

    for username, data in harvested_data.items():
        username_l = username.lower()

        # Convert tweets to graph_builder format
        for tw in data.get("tweets", []):
            tweet_dict: dict[str, Any] = {
                "author": username_l,
                "text": tw.get("full_text") or tw.get("text") or "",
                "full_text": tw.get("full_text") or tw.get("text") or "",
                "created_at": tw.get("created_at", ""),
            }

            # Detect retweets from text
            text = tweet_dict["text"]
            if text.startswith("RT @"):
                tweet_dict["is_retweet"] = True

            # Reply detection
            reply_to = tw.get("in_reply_to_user_id") or tw.get("in_reply_to_screen_name")
            if reply_to:
                tweet_dict["in_reply_to"] = str(reply_to).lower()

            tweets.append(tweet_dict)

        # Convert retweets to tweet format for graph edges
        for rt in data.get("retweets", []):
            rt_user = rt.get("retweeted_user_screen_name") or rt.get("rt_screen_name")
            if rt_user:
                tweets.append({
                    "author": username_l,
                    "text": f"RT @{rt_user}: ...",
                    "full_text": f"RT @{rt_user}: ...",
                    "is_retweet": True,
                    "created_at": rt.get("created_at", ""),
                })

        # Convert quote tweets
        for qt in data.get("quote_tweets", []):
            qt_user = qt.get("quoted_user_screen_name") or qt.get("qt_screen_name")
            if qt_user:
                tweets.append({
                    "author": username_l,
                    "text": qt.get("full_text", ""),
                    "full_text": qt.get("full_text", ""),
                    "is_quote": True,
                    "quoted_user": qt_user.lower(),
                    "created_at": qt.get("created_at", ""),
                })

        # Convert mentions to tweet format
        for m in data.get("mentions", []):
            mentioned = m.get("mentioned_user_screen_name") or m.get("screen_name")
            if mentioned:
                tweets.append({
                    "author": username_l,
                    "text": f"@{mentioned} ...",
                    "full_text": f"@{mentioned} ...",
                    "created_at": m.get("created_at", ""),
                })

        # Follower lists: username -> [who follows them]
        follower_list = []
        for f in data.get("followers", []):
            fn = f.get("follower_account_id") or f.get("follower_username")
            if fn:
                follower_list.append(str(fn).lower())
        if follower_list:
            followers[username_l] = follower_list

        # Following -> edge_map: username -> [who they follow]
        following_list = []
        for f in data.get("following", []):
            fn = f.get("following_account_id") or f.get("following_username")
            if fn:
                following_list.append(str(fn).lower())
        if following_list:
            edge_map[username_l] = following_list

    return {
        "tweets": tweets,
        "followers": followers,
        "edge_map": edge_map,
    }


# ── Content extraction ───────────────────────────────────────────

def extract_content(harvested_data: dict[str, dict]) -> list[dict]:
    """
    Extract tweet text corpus in content_overlay.py input format.

    Returns list of tweet dicts with 'author', 'text'/'full_text',
    'created_at', 'hashtags' fields — matching what
    content_overlay.build_node_topic_profiles() expects.
    """
    tweets: list[dict] = []
    for username, data in harvested_data.items():
        username_l = username.lower()
        for tw in data.get("tweets", []):
            text = tw.get("full_text") or tw.get("text") or ""
            if not text:
                continue
            # Extract hashtags from entities or text
            hashtags = tw.get("hashtags", [])
            if not hashtags and "#" in text:
                import re
                hashtags = re.findall(r"#(\w+)", text)

            tweets.append({
                "author": username_l,
                "text": text,
                "full_text": text,
                "created_at": tw.get("created_at", ""),
                "hashtags": hashtags,
            })
    return tweets
