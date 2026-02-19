"""
CommunityArchiveSource: network-layer adapter that connects the Community Archive
Supabase API to HoleSpawn's graph_builder and influence_flow modules.

Wraps the low-level ingest client (holespawn.ingest.community_archive) and provides
direct methods for building social graphs, quote-tweet propagation chains, reply
trees, and conversation-aware influence analysis.

Techniques adopted from TheExGenesis/memetic-lineage:
- Self-quote filtering in propagation counting (their count_quotes() excludes
  self-QTs, which our influence_flow did not do -- now patched)
- Conversation tree reconstruction with pre-built adjacency maps for O(1) child
  lookup (their ConversationExplorer pattern)
- Non-self-quote count as a distinct per-tweet metric for ranking "idea seeds"

No external deps beyond requests (used by ingest layer).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from holespawn.ingest.community_archive import (
    CommunityArchiveClient,
    extract_content,
    harvest_account,
    to_holespawn_graph,
)
from holespawn.network.graph_builder import GraphSpec, build_graph

logger = logging.getLogger(__name__)


@dataclass
class ConversationTree:
    """A reconstructed conversation tree from reply chains."""

    root_tweet_id: str
    root_author: str
    tweets: list[dict] = field(default_factory=list)
    children_map: dict[str, list[str]] = field(default_factory=dict)
    depth: int = 0
    participant_count: int = 0
    time_span: tuple[datetime | None, datetime | None] = (None, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_tweet_id": self.root_tweet_id,
            "root_author": self.root_author,
            "tweet_count": len(self.tweets),
            "depth": self.depth,
            "participant_count": self.participant_count,
            "time_span": [
                t.isoformat() if t else None for t in self.time_span
            ],
        }


@dataclass
class QuoteChain:
    """A chain of quote-tweets showing idea propagation."""

    original_tweet_id: str
    original_author: str
    quotes: list[dict] = field(default_factory=list)
    unique_quoters: int = 0
    non_self_quote_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_tweet_id": self.original_tweet_id,
            "original_author": self.original_author,
            "total_quotes": len(self.quotes),
            "unique_quoters": self.unique_quoters,
            "non_self_quote_count": self.non_self_quote_count,
        }


class CommunityArchiveSource:
    """
    High-level adapter bridging Community Archive data into HoleSpawn's
    network analysis engine.

    Usage:
        source = CommunityArchiveSource()
        graph = source.build_social_graph(["user1", "user2"])
        # graph is a GraphSpec ready for influence_flow, vulnerability, etc.
    """

    def __init__(
        self,
        client: CommunityArchiveClient | None = None,
        page_size: int = 1000,
        rate_limit_delay: float = 0.25,
    ):
        self.client = client or CommunityArchiveClient(
            page_size=page_size,
            rate_limit_delay=rate_limit_delay,
        )
        # Cache of harvested account data keyed by username
        self._cache: dict[str, dict] = {}

    # -- Core data fetching -----------------------------------------------

    def _ensure_harvested(self, username: str) -> dict:
        """Harvest an account if not already cached. Returns harvested data."""
        username_l = username.lower()
        if username_l not in self._cache:
            data = harvest_account(username_l, client=self.client)
            if data:
                self._cache[username_l] = data
            else:
                logger.warning("No data found for %s", username)
                self._cache[username_l] = {}
        return self._cache[username_l]

    def fetch_follow_graph(self, account_ids: list[str]) -> GraphSpec:
        """
        Build a follow-edge-only graph for the given usernames.

        Returns a GraphSpec with follow edges (follower -> followed)
        suitable for community detection and centrality analysis.
        """
        harvested: dict[str, dict] = {}
        for username in account_ids:
            data = self._ensure_harvested(username)
            if data:
                harvested[username.lower()] = data

        if not harvested:
            return GraphSpec(graph=__import__("networkx").DiGraph())

        graph_input = to_holespawn_graph(harvested)
        # Build with only follower/following edges (no tweets)
        return build_graph(
            followers=graph_input.get("followers"),
            edge_map=graph_input.get("edge_map"),
        )

    def fetch_account_tweets(self, account_id: str) -> list[dict]:
        """
        Fetch tweets for a single account in graph_builder-compatible format.

        Returns list of tweet dicts with 'author', 'text', 'created_at',
        'is_retweet', 'is_quote', 'quoted_user', 'in_reply_to' fields.
        """
        data = self._ensure_harvested(account_id)
        if not data:
            return []
        harvested = {account_id.lower(): data}
        graph_input = to_holespawn_graph(harvested)
        return graph_input.get("tweets", [])

    def fetch_quote_chains(self, tweet_ids: list[str]) -> list[QuoteChain]:
        """
        Build quote-tweet propagation chains for the given tweet IDs.

        Uses the quote_tweets view from Community Archive to trace how
        ideas propagate through quote-tweeting. Filters self-quotes
        (adopted from memetic-lineage's count_quotes technique).

        Args:
            tweet_ids: List of tweet IDs to trace quotes for.

        Returns:
            List of QuoteChain objects showing propagation per tweet.
        """
        chains: list[QuoteChain] = []

        for tweet_id in tweet_ids:
            try:
                # Query the quote_tweets view for this tweet
                rows = self.client._get_paginated("tweet_urls", {
                    "select": "*",
                    "expanded_url": f"like.*status/{tweet_id}*",
                })
            except Exception as e:
                logger.error("Failed to fetch quotes for tweet %s: %s", tweet_id, e)
                continue

            if not rows:
                chains.append(QuoteChain(
                    original_tweet_id=str(tweet_id),
                    original_author="unknown",
                ))
                continue

            # Get original tweet author
            try:
                orig_rows = self.client._get("tweets", {
                    "select": "account_id,account!inner(username)",
                    "tweet_id": f"eq.{tweet_id}",
                    "limit": "1",
                })
                orig_author = ""
                if orig_rows:
                    acct = orig_rows[0].get("account", {})
                    orig_author = acct.get("username", "") if isinstance(acct, dict) else ""
                    orig_account_id = str(orig_rows[0].get("account_id", ""))
            except Exception:
                orig_author = "unknown"
                orig_account_id = ""

            # Build quote list, filtering self-quotes
            # (memetic-lineage technique: exclude quotes where quoter == original author)
            quotes: list[dict] = []
            quoter_ids: set[str] = set()
            non_self_count = 0

            for row in rows:
                qt_tweet_id = row.get("tweet_id")
                if not qt_tweet_id:
                    continue
                # Get the quoting tweet's author
                try:
                    qt_rows = self.client._get("tweets", {
                        "select": "account_id,full_text,created_at",
                        "tweet_id": f"eq.{qt_tweet_id}",
                        "limit": "1",
                    })
                except Exception:
                    continue

                if not qt_rows:
                    continue

                qt_data = qt_rows[0]
                qt_account_id = str(qt_data.get("account_id", ""))

                quote_entry = {
                    "tweet_id": str(qt_tweet_id),
                    "account_id": qt_account_id,
                    "full_text": qt_data.get("full_text", ""),
                    "created_at": qt_data.get("created_at", ""),
                    "is_self_quote": qt_account_id == orig_account_id,
                }
                quotes.append(quote_entry)
                quoter_ids.add(qt_account_id)

                if qt_account_id != orig_account_id:
                    non_self_count += 1

            chains.append(QuoteChain(
                original_tweet_id=str(tweet_id),
                original_author=orig_author,
                quotes=quotes,
                unique_quoters=len(quoter_ids),
                non_self_quote_count=non_self_count,
            ))

        return chains

    def fetch_reply_trees(self, tweet_ids: list[str]) -> list[ConversationTree]:
        """
        Reconstruct conversation trees rooted at the given tweet IDs.

        Uses pre-built adjacency maps for O(1) child lookup, adopted from
        memetic-lineage's ConversationExplorer pattern.

        Args:
            tweet_ids: Root tweet IDs to build trees from.

        Returns:
            List of ConversationTree objects.
        """
        trees: list[ConversationTree] = []

        for tweet_id in tweet_ids:
            try:
                # Fetch all tweets in this conversation
                conv_tweets = self.client.get_conversations(str(tweet_id))
            except Exception as e:
                logger.error("Failed to fetch conversation for %s: %s", tweet_id, e)
                continue

            if not conv_tweets:
                # Try fetching the tweet itself to get conversation_id
                try:
                    root_rows = self.client._get("tweets", {
                        "select": "*",
                        "tweet_id": f"eq.{tweet_id}",
                        "limit": "1",
                    })
                    if root_rows:
                        conv_id = root_rows[0].get("conversation_id")
                        if conv_id:
                            conv_tweets = self.client.get_conversations(str(conv_id))
                except Exception:
                    pass

            if not conv_tweets:
                continue

            tree = _build_conversation_tree(conv_tweets, str(tweet_id))
            trees.append(tree)

        return trees

    # -- High-level graph building ----------------------------------------

    def build_social_graph(self, usernames: list[str]) -> GraphSpec:
        """
        Build a complete social graph (follows + tweets + quotes + replies)
        for the given usernames.

        This is the primary entry point for network analysis. The returned
        GraphSpec is directly compatible with influence_flow.analyze_influence_flow(),
        vulnerability.analyze_vulnerability(), temporal.analyze_temporal(), etc.
        """
        harvested: dict[str, dict] = {}
        for username in usernames:
            data = self._ensure_harvested(username)
            if data:
                harvested[username.lower()] = data

        if not harvested:
            return GraphSpec(graph=__import__("networkx").DiGraph())

        graph_input = to_holespawn_graph(harvested)
        return build_graph(**graph_input)

    def build_content_corpus(self, usernames: list[str]) -> list[dict]:
        """
        Extract tweet text corpus for content_overlay analysis.

        Returns list of tweet dicts compatible with
        content_overlay.build_node_topic_profiles().
        """
        harvested: dict[str, dict] = {}
        for username in usernames:
            data = self._ensure_harvested(username)
            if data:
                harvested[username.lower()] = data

        return extract_content(harvested)


# -- Conversation tree reconstruction ------------------------------------
# Adopted from memetic-lineage's ConversationExplorer: builds an adjacency
# map (parent -> [children]) for O(1) child lookup instead of scanning the
# full tweet list each time.

def _build_conversation_tree(
    tweets: list[dict],
    root_tweet_id: str,
) -> ConversationTree:
    """Build a ConversationTree from a list of conversation tweets."""

    # Index tweets by ID
    by_id: dict[str, dict] = {}
    for tw in tweets:
        tid = str(tw.get("tweet_id", ""))
        if tid:
            by_id[tid] = tw

    # Build adjacency map: parent_id -> [child_ids]
    # (memetic-lineage ConversationExplorer pattern)
    children_map: dict[str, list[str]] = defaultdict(list)
    for tw in tweets:
        tid = str(tw.get("tweet_id", ""))
        parent = tw.get("reply_to_tweet_id")
        if parent and not _is_null(parent):
            children_map[str(parent)].append(tid)

    # Find root author
    root_tw = by_id.get(root_tweet_id, {})
    root_author = root_tw.get("username", root_tw.get("account_id", "unknown"))

    # Compute depth via BFS
    max_depth = 0
    participants: set[str] = set()
    min_t: datetime | None = None
    max_t: datetime | None = None

    queue = [(root_tweet_id, 0)]
    visited: set[str] = set()

    while queue:
        tid, depth = queue.pop(0)
        if tid in visited:
            continue
        visited.add(tid)

        tw = by_id.get(tid)
        if tw:
            acct = tw.get("username") or tw.get("account_id") or ""
            if acct:
                participants.add(str(acct))

            ts_str = tw.get("created_at", "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(
                        ts_str.replace("Z", "+00:00") if isinstance(ts_str, str) else ""
                    )
                    if min_t is None or ts < min_t:
                        min_t = ts
                    if max_t is None or ts > max_t:
                        max_t = ts
                except (ValueError, TypeError):
                    pass

        if depth > max_depth:
            max_depth = depth

        for child_id in children_map.get(tid, []):
            queue.append((child_id, depth + 1))

    return ConversationTree(
        root_tweet_id=root_tweet_id,
        root_author=str(root_author),
        tweets=tweets,
        children_map=dict(children_map),
        depth=max_depth,
        participant_count=len(participants),
        time_span=(min_t, max_t),
    )


def _is_null(val: Any) -> bool:
    """Check if a value is null/NaN/None."""
    if val is None:
        return True
    if isinstance(val, float):
        import math
        return math.isnan(val)
    if isinstance(val, str):
        return val.lower() in ("", "none", "null", "nan")
    return False
