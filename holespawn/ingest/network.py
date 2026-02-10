"""
Fetch social graph data for a Twitter/X user (v2).
Step 1: Target's following, followers, interactions.
Step 2: Rank connections and select inner circle (top N).
Step 3: Crawl each inner-circle node's following list to get INTER-CONNECTION edges.
Without step 3 the graph is a useless star. Outputs NetworkData for analysis.
"""

import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from holespawn.ingest.apify_following import fetch_following_apify
from holespawn.ingest.apify_twitter import _normalize_username
from holespawn.scraper import sync as scraper_sync

logger = logging.getLogger(__name__)

MAX_FOLLOWERS_SAMPLE = 5000
MAX_INTERACTION_TWEETS = 500
CRAWL_DELAY_SEC = 1.5
SAVE_EVERY_N_FETCHES = 10


@dataclass
class NetworkData:
    """Collected social graph (v2): inner circle + edges with inter-connection links."""

    target_username: str
    inner_circle: list[str] = field(default_factory=list)
    all_connections: list[str] = field(default_factory=list)
    interactions: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)  # {source, target, weight, edge_types: list[str]}
    fetch_stats: dict = field(default_factory=dict)  # nodes_attempted, nodes_succeeded, nodes_failed, total_fetch_calls
    # Legacy compat (derived)
    following: list[str] = field(default_factory=list)
    followers: list[str] = field(default_factory=list)
    mutuals: list[str] = field(default_factory=list)
    raw_edges: list[tuple[str, str]] = field(default_factory=list)


def _fetch_followers_scraper(username: str, max_results: int = 2000) -> list[str]:
    """Fetch followers list via self-hosted scraper. Returns [] on failure."""
    username = _normalize_username(username)
    if not username:
        return []
    try:
        return scraper_sync.fetch_followers(username, max_results=min(max_results, 5000))
    except Exception as e:
        logger.warning("Followers fetch failed for @%s: %s", username, e)
        return []


def _fetch_followers_apify(username: str, max_results: int = 2000) -> list[str]:
    """Fetch followers list via Apify. Returns [] if no token or actor fails."""
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    if not token:
        return []
    username = _normalize_username(username)
    if not username:
        return []
    actor = os.getenv("APIFY_FOLLOWERS_ACTOR") or "powerai/twitter-followers-scraper"
    try:
        from apify_client import ApifyClient
    except Exception:
        return []
    try:
        client = ApifyClient(token)
        run_input = {"screenname": username, "maxResults": min(max_results, 5000)}
        run = client.actor(actor).call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as e:
        logger.warning("Followers fetch (Apify) failed for @%s: %s", username, e)
        return []
    handles: list[str] = []
    for item in items:
        if isinstance(item, dict):
            h = item.get("screen_name") or item.get("username") or item.get("handle") or item.get("screenName")
            if h:
                handles.append(str(h).strip().lstrip("@"))
        elif isinstance(item, str):
            handles.append(item.strip().lstrip("@"))
    return handles[:max_results]


def _fetch_tweet_items_apify(username: str, max_tweets: int = 500) -> list[dict[str, Any]]:
    """Fetch raw tweet items for interaction parsing via Apify (if token available)."""
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    if not token:
        return []
    username = _normalize_username(username)
    if not username:
        return []
    try:
        from holespawn.ingest.apify_twitter import APIFY_TWITTER_ACTOR, SCRAPER_FALLBACKS, _run_apify_raw
        from apify_client import ApifyClient
    except Exception:
        return []
    client = ApifyClient(token)
    primary_input = {"handles": [username], "maxTweets": max_tweets}
    try:
        items = _run_apify_raw(client, APIFY_TWITTER_ACTOR, primary_input)
        if items:
            return [i for i in items if isinstance(i, dict)]
    except Exception:
        pass
    for cfg in SCRAPER_FALLBACKS:
        try:
            run_input = cfg["build_input"](username, max_tweets)
            items = _run_apify_raw(client, cfg["name"], run_input)
            if items:
                return [i for i in items if isinstance(i, dict)]
        except Exception:
            continue
    return []


def _extract_interactions_from_tweet_items(
    target_username: str, items: list[dict[str, Any]]
) -> list[dict]:
    """Aggregate reply/rt/quote/mention per username from raw tweet items."""
    target_lower = target_username.lower()
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"username": "", "type_counts": defaultdict(int), "recent_texts": []}
    )
    for item in items:
        if not isinstance(item, dict):
            continue
        text = (
            item.get("full_text")
            or item.get("text")
            or item.get("content")
            or item.get("tweet")
            or ""
        )
        reply_to = (
            item.get("in_reply_to_screen_name")
            or item.get("in_reply_to_screenname")
            or item.get("in_reply_to")
        )
        if reply_to:
            u = str(reply_to).strip().lstrip("@").lower()
            if u and u != target_lower:
                agg[u]["username"] = u
                agg[u]["type_counts"]["reply"] += 1
                if len(agg[u]["recent_texts"]) < 5:
                    agg[u]["recent_texts"].append((text or "")[:200])
        ru = item.get("retweeted_status_screen_name")
        if not ru:
            rt_user = item.get("retweeted_status", {}) or item.get("retweetedStatus", {})
            if isinstance(rt_user, dict):
                ru = (
                    rt_user.get("user", {}).get("screen_name")
                    or rt_user.get("user", {}).get("username")
                    or rt_user.get("screenName")
                )
        if ru:
            u = str(ru).strip().lstrip("@").lower()
            if u != target_lower:
                agg[u]["username"] = u
                agg[u]["type_counts"]["rt"] += 1
        qu = item.get("quoted_user")
        if not qu:
            quote_user = item.get("quoted_status", {}) or item.get("quotedStatus", {})
            if isinstance(quote_user, dict):
                qu = quote_user.get("user", {}).get("screen_name") or quote_user.get("user", {}).get("username")
        if qu:
            u = str(qu).strip().lstrip("@").lower()
            if u != target_lower:
                agg[u]["username"] = u
                agg[u]["type_counts"]["quote"] += 1
        entities = item.get("entities", {}) or item.get("user_mentions", [])
        mentions = entities.get("user_mentions", []) or entities.get("mentions", []) if isinstance(entities, dict) else (entities if isinstance(entities, list) else [])
        for m in mentions:
            mu = m.get("screen_name") or m.get("username") if isinstance(m, dict) else None
            if mu:
                u = str(mu).strip().lstrip("@").lower()
                if u != target_lower:
                    agg[u]["username"] = u
                    agg[u]["type_counts"]["mention"] += 1
                    if len(agg[u]["recent_texts"]) < 5 and text:
                        agg[u]["recent_texts"].append(text[:200])
    out = []
    for u, data in agg.items():
        if not data["username"]:
            data["username"] = u
        total = sum(data["type_counts"].values())
        if total == 0:
            continue
        out.append({
            "username": data["username"],
            "type": max(data["type_counts"], key=data["type_counts"].get),
            "count": total,
            "type_counts": dict(data["type_counts"]),
            "recent_texts": data["recent_texts"][:5],
        })
    return sorted(out, key=lambda x: -x["count"])


def _fetch_tweet_items_scraper(username: str, max_tweets: int = 500) -> list[dict[str, Any]]:
    """Fetch raw tweet items for interaction parsing via self-hosted scraper."""
    username = _normalize_username(username)
    if not username:
        return []
    try:
        items = scraper_sync.fetch_tweets(username, max_tweets=max_tweets)
        return [i for i in items if isinstance(i, dict)]
    except Exception as e:
        logger.warning("Tweet fetch failed for @%s: %s", username, e)
        return []


def _rank_connections(
    target: str,
    following: list[str],
    followers: list[str],
    interactions: list[dict],
    inner_circle_size: int,
) -> list[str]:
    """Rank connections by interaction frequency, mutuals, then fill from following/followers. Return top inner_circle_size."""
    mutual_set = set(following) & set(followers)
    interaction_scores: dict[str, float] = defaultdict(float)
    for rec in interactions:
        u = (rec.get("username") or "").strip().lower()
        if not u or u == target.lower():
            continue
        interaction_scores[u] = float(rec.get("count", 0))
    seen: set[str] = set()
    out: list[str] = []
    # 1) High interaction (top by count)
    for rec in interactions:
        u = (rec.get("username") or "").strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    # 2) Mutuals not yet in
    for u in mutual_set:
        u = _normalize_username(u)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    # 3) Rest of following then followers
    for u in following:
        u = _normalize_username(u)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    for u in followers:
        u = _normalize_username(u)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out[:inner_circle_size]


def _fetch_following_apify_quiet(username: str, max_results: int = 500) -> list[str]:
    """Fetch following list; return [] on any error (no raise). For crawl step."""
    username = _normalize_username(username)
    if not username:
        return []
    try:
        following = fetch_following_apify(username, max_results=max_results)
        return following
    except Exception as e:
        logger.warning("Following fetch failed for @%s: %s", username, e)
        return []


def fetch_network_data(
    target_username: str,
    *,
    inner_circle_size: int = 150,
    max_following: int = 500,
    max_followers: int = 5000,
    max_interaction_tweets: int = 500,
    crawl_delay_sec: float = CRAWL_DELAY_SEC,
    save_every_n: int = SAVE_EVERY_N_FETCHES,
    raw_data_path: Path | str | None = None,
    resume_from_path: Path | str | None = None,
    log_progress: Any = None,
) -> NetworkData | None:
    """
    v2: Fetch target connections, select inner circle, crawl each node's following for inter-edges.
    Saves to raw_data_path every save_every_n fetches. If resume_from_path exists, load and continue.
    Returns None if no token or target invalid.
    """
    target = _normalize_username(target_username)
    if not target:
        return None

    def _log(msg: str, *args: Any) -> None:
        if callable(log_progress):
            log_progress(msg, *args)
        else:
            logger.info(msg % args if args else msg)
    edges_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    fetch_stats = {"nodes_attempted": 0, "nodes_succeeded": 0, "nodes_failed": 0, "total_fetch_calls": 0}
    inner_circle: list[str] = []
    all_connections: list[str] = []
    interactions: list[dict] = []
    following: list[str] = []
    followers: list[str] = []

    def _add_edge(source: str, target: str, weight_delta: float, edge_type: str) -> None:
        key = (source, target)
        if key not in edges_by_pair:
            edges_by_pair[key] = {"source": source, "target": target, "weight": 0.0, "edge_types": []}
        edges_by_pair[key]["weight"] += weight_delta
        if edge_type not in edges_by_pair[key]["edge_types"]:
            edges_by_pair[key]["edge_types"].append(edge_type)

    # Resume from file if requested
    if resume_from_path:
        path = Path(resume_from_path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                inner_circle = data.get("inner_circle", [])
                all_connections = data.get("all_connections", [])
                interactions = data.get("interactions", [])
                following = data.get("following", [])
                followers = data.get("followers", [])
                for e in data.get("edges", []):
                    s, t = e.get("source"), e.get("target")
                    if s and t:
                        key = (s, t)
                        edges_by_pair[key] = {"source": s, "target": t, "weight": float(e.get("weight", 0)), "edge_types": e.get("edge_types", [])}
                fetch_stats = data.get("fetch_stats", fetch_stats)
                _log("Resumed from %s: %d inner circle, %d edges so far", path, len(inner_circle), len(edges_by_pair))
            except Exception as e:
                logger.warning("Resume failed: %s", e)

    if not inner_circle:
        # Step 1: target's direct connections
        _log("Fetching target following and followers...")
        following = fetch_following_apify(target, max_results=max_following)
        fetch_stats["total_fetch_calls"] += 1
        followers = (
            _fetch_followers_apify(target, max_results=min(max_followers, MAX_FOLLOWERS_SAMPLE))
            or _fetch_followers_scraper(target, max_results=min(max_followers, MAX_FOLLOWERS_SAMPLE))
        )
        fetch_stats["total_fetch_calls"] += 1
        all_connections = list(dict.fromkeys(following + followers))
        tweet_items = (
            _fetch_tweet_items_apify(target, max_tweets=max_interaction_tweets)
            or _fetch_tweet_items_scraper(target, max_tweets=max_interaction_tweets)
        )
        fetch_stats["total_fetch_calls"] += 1
        interactions = _extract_interactions_from_tweet_items(target, tweet_items)
        inner_circle = _rank_connections(target, following, followers, interactions, inner_circle_size)
        mutuals = list(set(following) & set(followers))
        # Edge weights: follow=1 each direction, mutual adds 1, interaction adds count (target only)
        for u in following:
            _add_edge(target, u, 1.0, "follow")
        for u in followers:
            _add_edge(u, target, 1.0, "follow")
        for rec in interactions:
            u = rec.get("username", "")
            if u:
                _add_edge(target, u, min(5.0, float(rec.get("count", 1))), "interaction")
        for u in mutuals:
            _add_edge(target, u, 1.0, "mutual")
        if raw_data_path:
            _save_raw(target, inner_circle, all_connections, interactions, following, followers, edges_by_pair, fetch_stats, raw_data_path)

    # Step 3: Crawl each inner-circle node's following
    inner_set = set(inner_circle) | {target}
    try:
        from tqdm import tqdm
        crawl_iter = tqdm(inner_circle, desc="Crawling inter-connections", unit="node")
    except ImportError:
        crawl_iter = inner_circle

    for i, node in enumerate(crawl_iter):
        fetch_stats["nodes_attempted"] += 1
        time.sleep(crawl_delay_sec)
        node_following = _fetch_following_apify_quiet(node, max_results=800)
        fetch_stats["total_fetch_calls"] += 1
        node_following_set = {_normalize_username(u) for u in node_following if u}
        if not node_following_set:
            fetch_stats["nodes_failed"] += 1
        else:
            fetch_stats["nodes_succeeded"] += 1
        for other in inner_set:
            if other == node:
                continue
            if other in node_following_set:
                _add_edge(node, other, 1.0, "follow")
        if raw_data_path and (i + 1) % save_every_n == 0:
            _save_raw(target, inner_circle, all_connections, interactions, following, followers, edges_by_pair, fetch_stats, raw_data_path)
            _log("Saved progress: %d edges", len(edges_by_pair))

    edges_list = [{"source": e["source"], "target": e["target"], "weight": e["weight"], "edge_types": e["edge_types"]} for e in edges_by_pair.values()]
    mutuals = list(set(following) & set(followers))
    raw_edges = [(e["source"], e["target"]) for e in edges_list]
    if raw_data_path:
        _save_raw(target, inner_circle, all_connections, interactions, following, followers, edges_by_pair, fetch_stats, raw_data_path)
    return NetworkData(
        target_username=target,
        inner_circle=inner_circle,
        all_connections=all_connections,
        interactions=interactions,
        edges=edges_list,
        fetch_stats=fetch_stats,
        following=following,
        followers=followers,
        mutuals=mutuals,
        raw_edges=raw_edges,
    )


def _save_raw(
    target: str,
    inner_circle: list[str],
    all_connections: list[str],
    interactions: list[dict],
    following: list[str],
    followers: list[str],
    edges_by_pair: dict,
    fetch_stats: dict,
    path: Path | str,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    edges_list = list(edges_by_pair.values())
    data = {
        "target_username": target,
        "inner_circle": inner_circle,
        "all_connections": all_connections,
        "interactions": interactions,
        "following": following,
        "followers": followers,
        "edges": edges_list,
        "fetch_stats": fetch_stats,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_network_data_from_raw(path: Path | str) -> NetworkData | None:
    """Load NetworkData from a saved network_raw_data.json (e.g. for resume or re-run analysis)."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        target = data.get("target_username", "")
        edges_list = data.get("edges", [])
        raw_edges = [(e["source"], e["target"]) for e in edges_list]
        following = data.get("following", [])
        followers = data.get("followers", [])
        return NetworkData(
            target_username=target,
            inner_circle=data.get("inner_circle", []),
            all_connections=data.get("all_connections", []),
            interactions=data.get("interactions", []),
            edges=edges_list,
            fetch_stats=data.get("fetch_stats", {}),
            following=following,
            followers=followers,
            mutuals=list(set(following) & set(followers)),
            raw_edges=raw_edges,
        )
    except Exception as e:
        logger.warning("Load raw network data failed: %s", e)
        return None


def validate_network_data(data: NetworkData) -> dict[str, Any]:
    """Sanity checks. If has_real_graph is False, do not proceed to analysis."""
    checks: dict[str, Any] = {}
    target = data.target_username
    non_target_edges = [
        e for e in data.edges
        if e.get("source") != target and e.get("target") != target
    ]
    checks["inter_connection_edges"] = len(non_target_edges)
    checks["has_real_graph"] = len(non_target_edges) > 10
    attempted = data.fetch_stats.get("nodes_attempted") or 0
    succeeded = data.fetch_stats.get("nodes_succeeded") or 0
    checks["nodes_crawled"] = succeeded
    checks["crawl_success_rate"] = (succeeded / attempted) if attempted else 0
    n = len(data.inner_circle) + 1
    max_edges = n * (n - 1)
    checks["inner_circle_density"] = (len(non_target_edges) / max_edges) if max_edges > 0 else 0
    if not checks.get("has_real_graph"):
        logger.error(
            "CRITICAL: No inter-connection edges found. The graph is a star topology and analysis will be meaningless. Check that the crawl step (Step 3) actually ran."
        )
    return checks
