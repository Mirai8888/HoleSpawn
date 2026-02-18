"""
Graph builder: construct directed, weighted, temporal graphs from scraped data.

Accepts tweets, follower lists, and edge maps as produced by holespawn.scraper.
Returns NetworkX DiGraphs with typed, weighted, timestamped edges.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

# Edge weight defaults by interaction type (higher = stronger signal)
EDGE_WEIGHTS: dict[str, float] = {
    "follow": 1.0,
    "retweet": 3.0,
    "quote_tweet": 4.0,
    "reply": 2.0,
    "mention": 1.5,
}


@dataclass
class GraphSpec:
    """Container for a built graph plus metadata."""

    graph: nx.DiGraph
    node_count: int = 0
    edge_count: int = 0
    edge_type_counts: dict[str, int] = field(default_factory=dict)
    time_range: tuple[datetime | None, datetime | None] = (None, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "edge_type_counts": self.edge_type_counts,
            "time_range": [
                t.isoformat() if t else None for t in self.time_range
            ],
        }


def _parse_twitter_time(s: str) -> datetime | None:
    """Parse Twitter's created_at format, returning None on failure."""
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _add_edge(G: nx.DiGraph, src: str, tgt: str, etype: str,
              weight: float | None = None, timestamp: datetime | None = None,
              meta: dict | None = None) -> None:
    """Add or update a weighted edge. Accumulates weight on repeat edges."""
    w = weight if weight is not None else EDGE_WEIGHTS.get(etype, 1.0)
    if G.has_edge(src, tgt):
        ed = G[src][tgt]
        ed["weight"] = ed.get("weight", 0) + w
        ed.setdefault("types", set()).add(etype)
        if timestamp:
            ed.setdefault("timestamps", []).append(timestamp)
    else:
        attrs: dict[str, Any] = {"weight": w, "types": {etype}}
        if timestamp:
            attrs["timestamps"] = [timestamp]
        if meta:
            attrs["meta"] = meta
        G.add_edge(src, tgt, **attrs)


def build_graph(
    tweets: list[dict] | None = None,
    followers: dict[str, list[str]] | None = None,
    edge_map: dict[str, list[str]] | None = None,
    custom_weights: dict[str, float] | None = None,
) -> GraphSpec:
    """
    Build a directed graph from heterogeneous scraped data.

    Args:
        tweets: List of tweet dicts from parser.parse_tweet_response.
            Fields used: author, is_retweet, is_quote, quoted_user,
            in_reply_to, created_at, text.
        followers: {username: [follower1, follower2, ...]}
            Edge direction: follower -> followed (follows relationship).
        edge_map: {username: [follows1, follows2, ...]} from community_edges.
            Edge direction: username -> follows_target.
        custom_weights: Override default EDGE_WEIGHTS.

    Returns:
        GraphSpec with populated DiGraph.
    """
    weights = {**EDGE_WEIGHTS, **(custom_weights or {})}
    G = nx.DiGraph()
    type_counts: dict[str, int] = {}
    min_t: datetime | None = None
    max_t: datetime | None = None

    def _track(etype: str, ts: datetime | None = None):
        nonlocal min_t, max_t
        type_counts[etype] = type_counts.get(etype, 0) + 1
        if ts:
            if min_t is None or ts < min_t:
                min_t = ts
            if max_t is None or ts > max_t:
                max_t = ts

    # --- Tweets ---
    for tw in (tweets or []):
        author = (tw.get("author") or "").lower()
        if not author:
            continue
        ts = _parse_twitter_time(tw.get("created_at", ""))

        # Retweets: author -> original author
        if tw.get("is_retweet"):
            # RT text usually starts with "RT @user:"
            text = tw.get("full_text") or tw.get("text") or ""
            rt_user = None
            if text.startswith("RT @"):
                rt_user = text.split("RT @")[1].split(":")[0].strip().lower()
            if rt_user:
                _add_edge(G, author, rt_user, "retweet", weights["retweet"], ts)
                _track("retweet", ts)

        # Quote tweets
        if tw.get("is_quote") and tw.get("quoted_user"):
            qt_user = tw["quoted_user"].lower()
            _add_edge(G, author, qt_user, "quote_tweet", weights["quote_tweet"], ts)
            _track("quote_tweet", ts)

        # Replies
        if tw.get("in_reply_to"):
            reply_to = tw["in_reply_to"].lower()
            _add_edge(G, author, reply_to, "reply", weights["reply"], ts)
            _track("reply", ts)

        # Mentions (extract from text)
        text = tw.get("full_text") or tw.get("text") or ""
        for mention in _extract_mentions(text):
            m = mention.lower()
            if m != author:
                _add_edge(G, author, m, "mention", weights["mention"], ts)
                _track("mention", ts)

    # --- Follower lists ---
    for user, flist in (followers or {}).items():
        user_l = user.lower()
        for f in flist:
            f_l = f.lower()
            _add_edge(G, f_l, user_l, "follow", weights["follow"])
            _track("follow")

    # --- Edge map (community_edges output: user -> [who they follow]) ---
    for user, targets in (edge_map or {}).items():
        user_l = user.lower()
        for t in targets:
            t_l = t.lower()
            _add_edge(G, user_l, t_l, "follow", weights["follow"])
            _track("follow")

    return GraphSpec(
        graph=G,
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        edge_type_counts=type_counts,
        time_range=(min_t, max_t),
    )


def _extract_mentions(text: str) -> list[str]:
    """Extract @mentions from tweet text, excluding RT prefix."""
    import re
    # Skip "RT @user:" prefix
    clean = re.sub(r"^RT @\w+:\s*", "", text)
    return re.findall(r"@(\w+)", clean)


def filter_graph_by_time(
    G: nx.DiGraph,
    start: datetime | None = None,
    end: datetime | None = None,
) -> nx.DiGraph:
    """Return subgraph with only edges that have timestamps within [start, end]."""
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, data in G.edges(data=True):
        timestamps = data.get("timestamps", [])
        if not timestamps:
            # No temporal data — include by default
            H.add_edge(u, v, **data)
            continue
        filtered = [
            t for t in timestamps
            if (start is None or t >= start) and (end is None or t <= end)
        ]
        if filtered:
            new_data = {**data, "timestamps": filtered}
            H.add_edge(u, v, **new_data)
    # Remove isolates
    isolates = list(nx.isolates(H))
    H.remove_nodes_from(isolates)
    return H
