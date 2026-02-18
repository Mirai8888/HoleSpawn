"""
Temporal network dynamics: snapshot comparison, community evolution,
narrative lifecycle, and trend detection.
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
class SnapshotDiff:
    """Comparison between two network snapshots at different times."""
    nodes_added: list[str] = field(default_factory=list)
    nodes_removed: list[str] = field(default_factory=list)
    edges_added: list[tuple[str, str]] = field(default_factory=list)
    edges_removed: list[tuple[str, str]] = field(default_factory=list)
    weight_changes: dict[tuple[str, str], float] = field(default_factory=dict)
    density_change: float = 0.0
    node_count_change: int = 0
    edge_count_change: int = 0

    def to_dict(self) -> dict:
        return {
            "nodes_added": self.nodes_added,
            "nodes_removed": self.nodes_removed,
            "edges_added": [list(e) for e in self.edges_added],
            "edges_removed": [list(e) for e in self.edges_removed],
            "weight_changes": {f"{u}->{v}": w for (u, v), w in self.weight_changes.items()},
            "density_change": round(self.density_change, 6),
            "node_count_change": self.node_count_change,
            "edge_count_change": self.edge_count_change,
        }


@dataclass
class CommunityEvolution:
    """How communities change between two snapshots."""
    stable_communities: list[dict[str, Any]] = field(default_factory=list)
    split_communities: list[dict[str, Any]] = field(default_factory=list)
    merged_communities: list[dict[str, Any]] = field(default_factory=list)
    members_joined: dict[int, list[str]] = field(default_factory=dict)
    members_left: dict[int, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stable_communities": self.stable_communities,
            "split_communities": self.split_communities,
            "merged_communities": self.merged_communities,
            "members_joined": self.members_joined,
            "members_left": self.members_left,
        }


@dataclass
class TrendReport:
    """Emerging and dying connections/patterns."""
    emerging_edges: list[dict[str, Any]] = field(default_factory=list)
    dying_edges: list[dict[str, Any]] = field(default_factory=list)
    rising_nodes: list[dict[str, Any]] = field(default_factory=list)
    declining_nodes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "emerging_edges": self.emerging_edges,
            "dying_edges": self.dying_edges,
            "rising_nodes": self.rising_nodes,
            "declining_nodes": self.declining_nodes,
        }


@dataclass
class TemporalReport:
    """Full temporal analysis result."""
    snapshot_diff: SnapshotDiff | None = None
    community_evolution: CommunityEvolution | None = None
    trends: TrendReport | None = None

    def to_dict(self) -> dict:
        return {
            "snapshot_diff": self.snapshot_diff.to_dict() if self.snapshot_diff else None,
            "community_evolution": self.community_evolution.to_dict() if self.community_evolution else None,
            "trends": self.trends.to_dict() if self.trends else None,
        }


def compare_snapshots(G1: nx.DiGraph, G2: nx.DiGraph) -> SnapshotDiff:
    """
    Compare two graph snapshots and identify structural changes.

    Args:
        G1: Earlier snapshot.
        G2: Later snapshot.

    Returns:
        SnapshotDiff with added/removed nodes and edges, weight changes.
    """
    nodes1 = set(G1.nodes())
    nodes2 = set(G2.nodes())
    edges1 = set(G1.edges())
    edges2 = set(G2.edges())

    # Weight changes for edges present in both
    weight_changes = {}
    for e in edges1 & edges2:
        w1 = G1[e[0]][e[1]].get("weight", 1.0)
        w2 = G2[e[0]][e[1]].get("weight", 1.0)
        if abs(w2 - w1) > 0.01:
            weight_changes[e] = round(w2 - w1, 4)

    d1 = nx.density(G1) if G1.number_of_nodes() > 0 else 0
    d2 = nx.density(G2) if G2.number_of_nodes() > 0 else 0

    return SnapshotDiff(
        nodes_added=sorted(nodes2 - nodes1),
        nodes_removed=sorted(nodes1 - nodes2),
        edges_added=sorted(edges2 - edges1),
        edges_removed=sorted(edges1 - edges2),
        weight_changes=weight_changes,
        density_change=d2 - d1,
        node_count_change=len(nodes2) - len(nodes1),
        edge_count_change=len(edges2) - len(edges1),
    )


def track_community_evolution(G1: nx.DiGraph, G2: nx.DiGraph) -> CommunityEvolution:
    """
    Track how communities evolve between two snapshots.

    Uses Jaccard similarity to match communities across snapshots.
    """
    def _detect(G):
        U = G.to_undirected()
        if U.number_of_nodes() < 3:
            return []
        try:
            return [set(c) for c in greedy_modularity_communities(U)]
        except Exception:
            return []

    comms1 = _detect(G1)
    comms2 = _detect(G2)

    if not comms1 or not comms2:
        return CommunityEvolution()

    # Match communities by Jaccard similarity
    def _jaccard(a: set, b: set) -> float:
        if not a and not b:
            return 0
        return len(a & b) / len(a | b)

    # Build matching matrix
    matches: list[tuple[int, int, float]] = []
    for i, c1 in enumerate(comms1):
        for j, c2 in enumerate(comms2):
            jac = _jaccard(c1, c2)
            if jac > 0.1:
                matches.append((i, j, jac))

    matches.sort(key=lambda x: x[2], reverse=True)

    matched_old: set[int] = set()
    matched_new: set[int] = set()
    result = CommunityEvolution()

    for i, j, jac in matches:
        if i in matched_old or j in matched_new:
            continue
        matched_old.add(i)
        matched_new.add(j)

        c1 = comms1[i]
        c2 = comms2[j]

        if jac > 0.5:
            result.stable_communities.append({
                "old_id": i, "new_id": j,
                "jaccard": round(jac, 4),
                "size_old": len(c1), "size_new": len(c2),
            })
        joined = sorted(c2 - c1)
        left = sorted(c1 - c2)
        if joined:
            result.members_joined[j] = joined
        if left:
            result.members_left[i] = left

    # Unmatched old communities = split or dissolved
    for i in range(len(comms1)):
        if i not in matched_old:
            # Check if members scattered into multiple new communities
            c1 = comms1[i]
            destinations = defaultdict(list)
            for m in c1:
                for j, c2 in enumerate(comms2):
                    if m in c2:
                        destinations[j].append(m)
                        break
            if len(destinations) > 1:
                result.split_communities.append({
                    "old_id": i, "size": len(c1),
                    "split_into": list(destinations.keys()),
                })

    # Unmatched new communities formed from multiple old ones
    for j in range(len(comms2)):
        if j not in matched_new:
            c2 = comms2[j]
            sources = defaultdict(list)
            for m in c2:
                for i, c1 in enumerate(comms1):
                    if m in c1:
                        sources[i].append(m)
                        break
            if len(sources) > 1:
                result.merged_communities.append({
                    "new_id": j, "size": len(c2),
                    "merged_from": list(sources.keys()),
                })

    return result


def detect_trends(
    G1: nx.DiGraph,
    G2: nx.DiGraph,
    top_n: int = 20,
) -> TrendReport:
    """
    Detect emerging and dying connections between two snapshots.

    Args:
        G1: Earlier snapshot.
        G2: Later snapshot.
        top_n: Number of top trends to return.
    """
    edges1 = set(G1.edges())
    edges2 = set(G2.edges())

    # Emerging edges (new in G2, weighted by importance)
    new_edges = edges2 - edges1
    emerging = []
    for u, v in new_edges:
        w = G2[u][v].get("weight", 1.0)
        emerging.append({"source": u, "target": v, "weight": w})
    emerging.sort(key=lambda e: e["weight"], reverse=True)

    # Dying edges (in G1 but not G2)
    lost_edges = edges1 - edges2
    dying = []
    for u, v in lost_edges:
        w = G1[u][v].get("weight", 1.0)
        dying.append({"source": u, "target": v, "weight": w})
    dying.sort(key=lambda e: e["weight"], reverse=True)

    # Rising/declining nodes by centrality change
    def _centrality(G):
        if G.number_of_nodes() == 0:
            return {}
        return nx.degree_centrality(G)

    c1 = _centrality(G1)
    c2 = _centrality(G2)
    all_nodes = set(c1) | set(c2)

    deltas = []
    for n in all_nodes:
        d = c2.get(n, 0) - c1.get(n, 0)
        deltas.append({"node": n, "centrality_change": round(d, 4),
                        "centrality_old": round(c1.get(n, 0), 4),
                        "centrality_new": round(c2.get(n, 0), 4)})

    deltas.sort(key=lambda x: x["centrality_change"], reverse=True)
    rising = [d for d in deltas[:top_n] if d["centrality_change"] > 0]
    declining = [d for d in deltas[-top_n:] if d["centrality_change"] < 0]
    declining.sort(key=lambda x: x["centrality_change"])

    return TrendReport(
        emerging_edges=emerging[:top_n],
        dying_edges=dying[:top_n],
        rising_nodes=rising,
        declining_nodes=declining,
    )


def analyze_temporal(
    G1: nx.DiGraph,
    G2: nx.DiGraph,
    top_n: int = 20,
) -> TemporalReport:
    """
    Run full temporal analysis comparing two network snapshots.

    Args:
        G1: Earlier snapshot (DiGraph).
        G2: Later snapshot (DiGraph).
        top_n: Number of top trends to return.

    Returns:
        TemporalReport with diff, community evolution, and trends.
    """
    return TemporalReport(
        snapshot_diff=compare_snapshots(G1, G2),
        community_evolution=track_community_evolution(G1, G2),
        trends=detect_trends(G1, G2, top_n),
    )
