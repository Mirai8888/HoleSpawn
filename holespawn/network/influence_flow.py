"""
Information flow analysis: narrative seeding, amplification chains,
bridge analysis, and composite influence scoring.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

try:
    from networkx.algorithms.community import greedy_modularity_communities
except ImportError:
    from networkx.algorithms.community.modularity_max import greedy_modularity_communities


@dataclass
class NarrativeSeed:
    """An original content creator whose content gets amplified."""
    user: str
    seed_count: int  # number of original tweets that got RT/QT
    total_amplification: int  # total RTs + QTs received
    top_amplifiers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "user": self.user,
            "seed_count": self.seed_count,
            "total_amplification": self.total_amplification,
            "top_amplifiers": self.top_amplifiers,
        }


@dataclass
class AmplificationChain:
    """A path showing how content propagates from seeder through amplifiers."""
    origin: str
    chain: list[str]  # ordered list of nodes content passed through
    edge_types: list[str]  # retweet, quote_tweet for each hop
    depth: int = 0

    def to_dict(self) -> dict:
        return {
            "origin": self.origin,
            "chain": self.chain,
            "edge_types": self.edge_types,
            "depth": self.depth,
        }


@dataclass
class InfluenceReport:
    """Complete influence flow analysis result."""
    seeds: list[NarrativeSeed] = field(default_factory=list)
    amplification_chains: list[AmplificationChain] = field(default_factory=list)
    bridge_nodes: list[dict[str, Any]] = field(default_factory=list)
    influence_scores: dict[str, float] = field(default_factory=dict)
    influence_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "seeds": [s.to_dict() for s in self.seeds],
            "amplification_chains": [c.to_dict() for c in self.amplification_chains],
            "bridge_nodes": self.bridge_nodes,
            "influence_scores": self.influence_scores,
            "influence_breakdown": self.influence_breakdown,
        }


def detect_narrative_seeds(G: nx.DiGraph) -> list[NarrativeSeed]:
    """
    Identify users who create original content that gets amplified.

    A seed is a node that is the target of retweet/quote_tweet edges.
    Ranked by total amplification volume.
    """
    seed_data: dict[str, dict] = defaultdict(lambda: {"count": 0, "amplification": 0, "amplifiers": []})

    for u, v, data in G.edges(data=True):
        types = data.get("types", set())
        if types & {"retweet", "quote_tweet"}:
            # u amplifies v's content
            sd = seed_data[v]
            sd["count"] += 1
            sd["amplification"] += int(data.get("weight", 1))
            sd["amplifiers"].append(u)

    seeds = []
    for user, info in sorted(seed_data.items(), key=lambda x: x[1]["amplification"], reverse=True):
        # Deduplicate and rank amplifiers by frequency
        amp_counts = defaultdict(int)
        for a in info["amplifiers"]:
            amp_counts[a] += 1
        top_amps = sorted(amp_counts, key=amp_counts.get, reverse=True)[:10]

        seeds.append(NarrativeSeed(
            user=user,
            seed_count=info["count"],
            total_amplification=info["amplification"],
            top_amplifiers=top_amps,
        ))

    return seeds


def trace_amplification_chains(G: nx.DiGraph, max_depth: int = 5) -> list[AmplificationChain]:
    """
    Trace how content propagates through RT/QT edges.

    Builds chains starting from seed nodes (targets of RT/QT edges)
    and following outward amplification paths.
    """
    # Build amplification subgraph (only RT/QT edges)
    amp_graph = nx.DiGraph()
    for u, v, data in G.edges(data=True):
        types = data.get("types", set())
        amp_types = types & {"retweet", "quote_tweet"}
        if amp_types:
            amp_graph.add_edge(u, v, types=amp_types, weight=data.get("weight", 1))

    if amp_graph.number_of_edges() == 0:
        return []

    # Find seed nodes (nodes with incoming amplification edges)
    seeds = {v for _, v in amp_graph.edges()}

    chains: list[AmplificationChain] = []
    for seed in seeds:
        # Find all nodes that amplify this seed (predecessors in amp_graph)
        # Then trace chains of amplification
        _trace_from_seed(amp_graph, seed, [], [], max_depth, chains)

    # Sort by depth descending
    chains.sort(key=lambda c: c.depth, reverse=True)
    return chains[:100]  # cap output


def _trace_from_seed(
    G: nx.DiGraph, node: str, path: list[str],
    edge_types: list[str], max_depth: int,
    results: list[AmplificationChain],
) -> None:
    """Recursively trace amplification from a seed outward."""
    if len(path) >= max_depth:
        if path:
            results.append(AmplificationChain(
                origin=path[0],
                chain=list(reversed(path + [node])),
                edge_types=list(reversed(edge_types)),
                depth=len(path),
            ))
        return

    preds = [p for p in G.predecessors(node) if p not in path]
    if not preds and path:
        results.append(AmplificationChain(
            origin=path[0],
            chain=list(reversed(path + [node])),
            edge_types=list(reversed(edge_types)),
            depth=len(path),
        ))
        return

    for pred in preds:
        data = G[pred][node]
        types = data.get("types", set())
        etype = "quote_tweet" if "quote_tweet" in types else "retweet"
        _trace_from_seed(G, pred, path + [node], edge_types + [etype], max_depth, results)


def analyze_bridges(G: nx.DiGraph) -> list[dict[str, Any]]:
    """
    Identify bridge nodes that transfer narratives between communities.

    A bridge node has high betweenness centrality AND connections to
    multiple detected communities.
    """
    if G.number_of_nodes() < 3:
        return []

    # Detect communities on undirected projection
    U = G.to_undirected()
    try:
        communities = list(greedy_modularity_communities(U))
    except Exception:
        return []

    if len(communities) < 2:
        return []

    # Map nodes to community IDs
    node_community: dict[str, int] = {}
    for cid, members in enumerate(communities):
        for m in members:
            node_community[m] = cid

    # Betweenness centrality
    betweenness = nx.betweenness_centrality(G, weight="weight")

    bridges = []
    for node in G.nodes():
        # Count how many different communities this node connects to
        neighbor_communities = set()
        for nbr in set(G.predecessors(node)) | set(G.successors(node)):
            if nbr in node_community:
                neighbor_communities.add(node_community[nbr])

        if len(neighbor_communities) >= 2:
            bridges.append({
                "node": node,
                "betweenness": betweenness.get(node, 0),
                "communities_connected": sorted(neighbor_communities),
                "num_communities": len(neighbor_communities),
                "own_community": node_community.get(node, -1),
            })

    bridges.sort(key=lambda b: (b["num_communities"], b["betweenness"]), reverse=True)
    return bridges


def compute_influence_scores(G: nx.DiGraph) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """
    Composite influence score incorporating seeding, amplification, and bridging.

    Components:
    - seeding_score: how much original content gets amplified (in-degree on RT/QT edges)
    - amplification_score: how much this node amplifies others (out-degree on RT/QT edges)
    - bridging_score: betweenness centrality (information flow control)
    - reach_score: eigenvector centrality (access to well-connected nodes)

    Returns:
        (scores, breakdown) where scores maps node->float and
        breakdown maps node->{seeding, amplification, bridging, reach}.
    """
    if G.number_of_nodes() == 0:
        return {}, {}

    # Component weights
    W_SEED = 0.35
    W_AMP = 0.15
    W_BRIDGE = 0.25
    W_REACH = 0.25

    # Seeding score: how much incoming RT/QT traffic
    seed_scores: dict[str, float] = defaultdict(float)
    amp_scores: dict[str, float] = defaultdict(float)
    for u, v, data in G.edges(data=True):
        types = data.get("types", set())
        w = data.get("weight", 1)
        if types & {"retweet", "quote_tweet"}:
            seed_scores[v] += w
            amp_scores[u] += w

    # Normalize
    def _normalize(d: dict[str, float]) -> dict[str, float]:
        if not d:
            return d
        mx = max(d.values())
        if mx == 0:
            return d
        return {k: v / mx for k, v in d.items()}

    seed_norm = _normalize(dict(seed_scores))
    amp_norm = _normalize(dict(amp_scores))

    # Bridging: betweenness
    betweenness = nx.betweenness_centrality(G, weight="weight")
    bridge_norm = _normalize(betweenness)

    # Reach: eigenvector centrality
    try:
        eigenvector = nx.eigenvector_centrality_numpy(G, weight="weight")
    except Exception:
        try:
            eigenvector = nx.eigenvector_centrality(G, max_iter=500, weight="weight")
        except Exception:
            eigenvector = dict.fromkeys(G.nodes(), 0.0)
    reach_norm = _normalize(eigenvector)

    # Composite
    scores: dict[str, float] = {}
    breakdown: dict[str, dict[str, float]] = {}
    for node in G.nodes():
        s = seed_norm.get(node, 0)
        a = amp_norm.get(node, 0)
        b = bridge_norm.get(node, 0)
        r = reach_norm.get(node, 0)
        scores[node] = W_SEED * s + W_AMP * a + W_BRIDGE * b + W_REACH * r
        breakdown[node] = {
            "seeding": round(s, 4),
            "amplification": round(a, 4),
            "bridging": round(b, 4),
            "reach": round(r, 4),
        }

    return scores, breakdown


def analyze_influence_flow(G: nx.DiGraph) -> InfluenceReport:
    """
    Run full influence flow analysis on a directed graph.

    Args:
        G: NetworkX DiGraph with typed, weighted edges (from graph_builder).

    Returns:
        InfluenceReport with seeds, chains, bridges, and influence scores.
    """
    seeds = detect_narrative_seeds(G)
    chains = trace_amplification_chains(G)
    bridges = analyze_bridges(G)
    scores, breakdown = compute_influence_scores(G)

    return InfluenceReport(
        seeds=seeds,
        amplification_chains=chains,
        bridge_nodes=bridges,
        influence_scores=scores,
        influence_breakdown=breakdown,
    )
