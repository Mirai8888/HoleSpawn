"""
Moltbook engagement intelligence: metrics, network mapping, content analysis,
and auto-discovery for the Seithar ecosystem.

Talks to https://www.moltbook.com/api/v1 (MUST use www).
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import requests

from holespawn.network.graph_builder import GraphSpec, _add_edge
from holespawn.network.content_overlay import (
    _extract_topics,
    _sentiment,
    NodeTopicProfile,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.moltbook.com/api/v1"
DATA_DIR = Path.home() / "HoleSpawn" / "data" / "moltbook"
CREDS_PATH = Path.home() / ".config" / "moltbook" / "credentials.json"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class MoltbookClient:
    """Thin HTTP wrapper for the Moltbook API. Never sends the key elsewhere."""

    def __init__(self, api_key: str | None = None):
        if api_key is None:
            api_key = os.environ.get("MOLTBOOK_API_KEY")
        if api_key is None:
            try:
                creds = json.loads(CREDS_PATH.read_text())
                api_key = creds["api_key"]
            except Exception as exc:
                raise RuntimeError(f"No Moltbook API key found: {exc}") from exc
        self._key = api_key
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        })

    # -- low-level ---------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}"
        assert url.startswith(BASE_URL), "refusing off-domain request"
        r = self._session.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}"
        assert url.startswith(BASE_URL)
        r = self._session.post(url, json=payload or {}, timeout=30)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> dict:
        url = f"{BASE_URL}{path}"
        assert url.startswith(BASE_URL)
        r = self._session.delete(url, timeout=30)
        r.raise_for_status()
        return r.json()

    # -- API wrappers ------------------------------------------------------

    def me(self) -> dict:
        return self._get("/agents/me")

    def status(self) -> dict:
        return self._get("/agents/status")

    def feed(self, sort: str = "hot", limit: int = 25) -> list[dict]:
        data = self._get("/feed", {"sort": sort, "limit": limit})
        return data.get("posts", data.get("results", []))

    def posts(self, sort: str = "new", limit: int = 25,
              submolt: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"sort": sort, "limit": limit}
        if submolt:
            params["submolt"] = submolt
        data = self._get("/posts", params)
        return data.get("posts", data.get("results", []))

    def post(self, post_id: str) -> dict:
        return self._get(f"/posts/{post_id}")

    def comments(self, post_id: str, sort: str = "top") -> list[dict]:
        data = self._get(f"/posts/{post_id}/comments", {"sort": sort})
        return data.get("comments", data.get("results", []))

    def submolts(self) -> list[dict]:
        data = self._get("/submolts")
        return data.get("submolts", data.get("results", []))

    def submolt_info(self, name: str) -> dict:
        return self._get(f"/submolts/{name}")

    def submolt_feed(self, name: str, sort: str = "new", limit: int = 25) -> list[dict]:
        data = self._get(f"/submolts/{name}/feed", {"sort": sort, "limit": limit})
        return data.get("posts", data.get("results", []))

    def search(self, query: str, type_: str = "all", limit: int = 20) -> list[dict]:
        data = self._get("/search", {"q": query, "type": type_, "limit": limit})
        return data.get("results", [])

    def notifications(self) -> list[dict]:
        """Best-effort; endpoint may not exist."""
        try:
            data = self._get("/notifications")
            return data.get("notifications", [])
        except Exception:
            return []

    def agent_profile(self, name: str) -> dict:
        return self._get(f"/agents/{name}")


# ---------------------------------------------------------------------------
# Metrics collection
# ---------------------------------------------------------------------------

@dataclass
class EngagementSnapshot:
    """Point-in-time metrics for the kenshusei account."""
    timestamp: str
    total_posts: int = 0
    total_comments: int = 0
    total_upvotes_received: int = 0
    total_downvotes_received: int = 0
    notification_count: int = 0
    posts: list[dict] = field(default_factory=list)
    comments_by_post: dict[str, list[dict]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def collect_metrics(client: MoltbookClient | None = None,
                    account: str = "kenshusei") -> EngagementSnapshot:
    """Fetch our posts/comments/votes and return a snapshot."""
    if client is None:
        client = MoltbookClient()

    now = datetime.now(timezone.utc).isoformat()
    snap = EngagementSnapshot(timestamp=now)

    # Get our posts (fetch all pages via hot+new+top to maximise coverage)
    seen_ids: set[str] = set()
    our_posts: list[dict] = []
    for sort in ("new", "hot", "top"):
        for p in client.posts(sort=sort, limit=25):
            author = (p.get("author") or {}).get("name", "")
            pid = p.get("id", "")
            if author.lower() == account.lower() and pid not in seen_ids:
                seen_ids.add(pid)
                our_posts.append(p)

    snap.total_posts = len(our_posts)
    snap.posts = our_posts

    total_up = 0
    total_down = 0
    for p in our_posts:
        total_up += p.get("upvotes", 0)
        total_down += p.get("downvotes", 0)
        # fetch comments on our posts
        try:
            coms = client.comments(p["id"])
            snap.comments_by_post[p["id"]] = coms
            snap.total_comments += len(coms)
        except Exception:
            pass

    snap.total_upvotes_received = total_up
    snap.total_downvotes_received = total_down
    snap.notification_count = len(client.notifications())

    # persist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts_safe = now.replace(":", "-").split(".")[0]
    out = DATA_DIR / f"snapshot_{ts_safe}.json"
    out.write_text(json.dumps(snap.to_dict(), indent=2, default=str))
    logger.info("Saved Moltbook snapshot → %s", out)
    return snap


# ---------------------------------------------------------------------------
# Network mapping
# ---------------------------------------------------------------------------

MOLTBOOK_EDGE_WEIGHTS: dict[str, float] = {
    "post_upvote": 2.0,
    "post_downvote": -1.0,
    "comment": 3.0,
    "comment_upvote": 1.5,
    "reply": 4.0,
}


def build_interaction_graph(client: MoltbookClient | None = None,
                            account: str = "kenshusei",
                            submolts: list[str] | None = None,
                            limit: int = 50) -> GraphSpec:
    """Build a directed interaction graph of Moltbook users around *account*.

    Edges represent: comments on posts, upvote signals, reply chains.
    Uses graph_builder infrastructure (GraphSpec, _add_edge).
    """
    if client is None:
        client = MoltbookClient()

    G = nx.DiGraph()
    edge_type_counts: dict[str, int] = defaultdict(int)
    timestamps: list[datetime] = []

    # Gather posts from global feed + specified submolts
    all_posts: list[dict] = []
    seen: set[str] = set()

    def _collect(posts: list[dict]):
        for p in posts:
            pid = p.get("id", "")
            if pid and pid not in seen:
                seen.add(pid)
                all_posts.append(p)

    for sort in ("hot", "new"):
        _collect(client.posts(sort=sort, limit=limit))
    for sm in (submolts or []):
        try:
            _collect(client.submolt_feed(sm, sort="new", limit=limit))
        except Exception:
            pass

    # Process posts and their comments
    for p in all_posts:
        author = (p.get("author") or {}).get("name", "")
        if not author:
            continue
        G.add_node(author)
        ts = _parse_ts(p.get("created_at"))
        if ts:
            timestamps.append(ts)

        try:
            coms = client.comments(p["id"])
        except Exception:
            coms = []

        for c in coms:
            c_author = (c.get("author") or {}).get("name", "")
            if not c_author:
                continue
            G.add_node(c_author)
            etype = "reply" if c.get("parent_id") else "comment"
            _add_edge(G, c_author, author, etype,
                      weight=MOLTBOOK_EDGE_WEIGHTS.get(etype, 2.0),
                      timestamp=_parse_ts(c.get("created_at")))
            edge_type_counts[etype] += 1

    t_sorted = sorted(timestamps) if timestamps else []
    spec = GraphSpec(
        graph=G,
        node_count=G.number_of_nodes(),
        edge_count=G.number_of_edges(),
        edge_type_counts=dict(edge_type_counts),
        time_range=(t_sorted[0] if t_sorted else None,
                    t_sorted[-1] if t_sorted else None),
    )

    # Persist adjacency
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    adj_path = DATA_DIR / "interaction_graph.json"
    adj_data = nx.node_link_data(G)
    adj_path.write_text(json.dumps(adj_data, indent=2, default=str))
    logger.info("Saved interaction graph (%d nodes, %d edges) → %s",
                spec.node_count, spec.edge_count, adj_path)
    return spec


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Content analysis
# ---------------------------------------------------------------------------

@dataclass
class MoltbookContentReport:
    """Aggregated content analysis across Moltbook posts."""
    top_topics: list[tuple[str, int]] = field(default_factory=list)
    seithar_sentiment: float = 0.0
    seithar_mention_count: int = 0
    submolt_topic_map: dict[str, list[tuple[str, int]]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "top_topics": self.top_topics,
            "seithar_sentiment": round(self.seithar_sentiment, 4),
            "seithar_mention_count": self.seithar_mention_count,
            "submolt_topic_map": self.submolt_topic_map,
        }


def analyze_content(client: MoltbookClient | None = None,
                    limit: int = 50) -> MoltbookContentReport:
    """What topics get traction? What's the sentiment toward Seithar?"""
    if client is None:
        client = MoltbookClient()

    report = MoltbookContentReport()
    all_text: list[str] = []
    seithar_sentiments: list[float] = []
    submolt_texts: dict[str, list[str]] = defaultdict(list)

    for sort in ("hot", "top"):
        for p in client.posts(sort=sort, limit=limit):
            title = p.get("title", "")
            content = p.get("content", "")
            text = f"{title} {content}".strip()
            if not text:
                continue
            all_text.append(text)
            sm = (p.get("submolt") or {}).get("name", "general")
            submolt_texts[sm].append(text)

            # Seithar mentions
            lower = text.lower()
            if "seithar" in lower or "sct" in lower or "holespawn" in lower:
                report.seithar_mention_count += 1
                seithar_sentiments.append(_sentiment(text))

    # Global topics
    combined = " ".join(all_text)
    report.top_topics = _extract_topics(combined, top_n=30)

    # Seithar sentiment
    if seithar_sentiments:
        report.seithar_sentiment = sum(seithar_sentiments) / len(seithar_sentiments)

    # Per-submolt topics
    for sm, texts in submolt_texts.items():
        report.submolt_topic_map[sm] = _extract_topics(" ".join(texts), top_n=10)

    # Persist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "content_report.json"
    out.write_text(json.dumps(report.to_dict(), indent=2))
    logger.info("Saved content report → %s", out)
    return report


# ---------------------------------------------------------------------------
# Auto-discovery: find engagement opportunities
# ---------------------------------------------------------------------------

SEITHAR_KEYWORDS = [
    "seithar", "sct", "holespawn", "social engineering", "influence",
    "network analysis", "osint", "vulnerability", "persuasion",
    "manipulation", "social graph", "narrative", "disinformation",
    "propaganda", "information warfare", "psyop", "cognitive",
    "behavioral", "cultural mapping", "agent network",
]


@dataclass
class EngagementOpportunity:
    """A post/community scored for engagement relevance."""
    post_id: str
    title: str
    submolt: str
    author: str
    relevance_score: float  # 0-1
    keyword_hits: list[str] = field(default_factory=list)
    upvotes: int = 0
    comment_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def discover_opportunities(client: MoltbookClient | None = None,
                           limit: int = 50,
                           min_score: float = 0.1) -> list[EngagementOpportunity]:
    """Find posts where Seithar expertise is relevant. Score for engagement."""
    if client is None:
        client = MoltbookClient()

    opportunities: list[EngagementOpportunity] = []

    # Semantic search for Seithar-relevant topics
    search_queries = [
        "social engineering techniques",
        "network analysis influence",
        "AI agent security vulnerabilities",
        "information warfare narratives",
        "behavioral manipulation patterns",
    ]

    seen_ids: set[str] = set()

    # Also scan hot/new feeds
    for sort in ("hot", "new"):
        for p in client.posts(sort=sort, limit=limit):
            pid = p.get("id", "")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            opp = _score_post(p)
            if opp and opp.relevance_score >= min_score:
                opportunities.append(opp)

    # Semantic search
    for q in search_queries:
        try:
            results = client.search(q, type_="posts", limit=10)
            for r in results:
                pid = r.get("id", r.get("post_id", ""))
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                opp = _score_search_result(r)
                if opp and opp.relevance_score >= min_score:
                    opportunities.append(opp)
        except Exception:
            pass

    opportunities.sort(key=lambda o: o.relevance_score, reverse=True)

    # Persist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "opportunities.json"
    out.write_text(json.dumps([o.to_dict() for o in opportunities], indent=2))
    logger.info("Found %d engagement opportunities", len(opportunities))
    return opportunities


def _score_post(p: dict) -> EngagementOpportunity | None:
    title = p.get("title", "")
    content = p.get("content", "")
    text = f"{title} {content}".lower()
    if not text.strip():
        return None

    hits = [kw for kw in SEITHAR_KEYWORDS if kw in text]
    if not hits:
        return None

    # Score: keyword density + engagement potential
    kw_score = min(len(hits) / 5.0, 1.0)
    upvotes = p.get("upvotes", 0)
    engagement_bonus = min(upvotes / 20.0, 0.3)
    score = kw_score * 0.7 + engagement_bonus

    return EngagementOpportunity(
        post_id=p.get("id", ""),
        title=title,
        submolt=(p.get("submolt") or {}).get("name", "general"),
        author=(p.get("author") or {}).get("name", ""),
        relevance_score=round(min(score, 1.0), 3),
        keyword_hits=hits,
        upvotes=upvotes,
        comment_count=p.get("comment_count", 0),
    )


def _score_search_result(r: dict) -> EngagementOpportunity | None:
    title = r.get("title", "")
    content = r.get("content", "")
    text = f"{title} {content}".lower()

    hits = [kw for kw in SEITHAR_KEYWORDS if kw in text]
    similarity = r.get("similarity", 0.5)

    score = similarity * 0.6 + min(len(hits) / 5.0, 1.0) * 0.4

    return EngagementOpportunity(
        post_id=r.get("id", r.get("post_id", "")),
        title=title,
        submolt=(r.get("submolt") or {}).get("name", "general"),
        author=(r.get("author") or {}).get("name", ""),
        relevance_score=round(min(score, 1.0), 3),
        keyword_hits=hits,
        upvotes=r.get("upvotes", 0),
        comment_count=r.get("comment_count", 0),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_full_intel(account: str = "kenshusei") -> dict[str, Any]:
    """Run all intel modules and return combined results."""
    client = MoltbookClient()
    results: dict[str, Any] = {}

    logger.info("Collecting metrics...")
    results["metrics"] = collect_metrics(client, account).to_dict()

    logger.info("Building interaction graph...")
    spec = build_interaction_graph(client, account)
    results["graph"] = spec.to_dict()

    logger.info("Analyzing content...")
    results["content"] = analyze_content(client).to_dict()

    logger.info("Discovering opportunities...")
    opps = discover_opportunities(client)
    results["opportunities"] = [o.to_dict() for o in opps]

    # Save combined report
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "intel_report.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    logger.info("Full intel report → %s", out)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_full_intel()
