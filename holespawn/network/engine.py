"""
Network Engine: operational orchestration layer.

Turns individual profiles + graph data into operational intelligence.
Answers: who connects to whom, through what paths, at what cost,
and what breaks if you cut the wire.

This is the bridge between HoleSpawn's individual profiling and
network-level operations. Feed it a graph and an objective,
get back a ranked set of operational options.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import networkx as nx

from .graph_builder import GraphSpec, build_graph, filter_graph_by_time
from .influence_flow import (
    InfluenceReport,
    analyze_influence_flow,
    compute_influence_scores,
    detect_narrative_seeds,
)
from .vulnerability import (
    VulnerabilityReport,
    analyze_vulnerability,
    find_single_points_of_failure,
)

logger = logging.getLogger(__name__)

try:
    from networkx.algorithms.community import greedy_modularity_communities
except ImportError:
    from networkx.algorithms.community.modularity_max import (
        greedy_modularity_communities,
    )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class OperationalNode:
    """A node's complete operational profile within the network."""

    node: str
    # Structural position
    community: int = -1
    degree_in: int = 0
    degree_out: int = 0
    betweenness: float = 0.0
    pagerank: float = 0.0
    eigenvector: float = 0.0
    # Operational role
    role: str = "peripheral"  # hub, bridge, amplifier, seed, gatekeeper, peripheral
    influence_score: float = 0.0
    influence_breakdown: dict[str, float] = field(default_factory=dict)
    # Reach
    downstream_count: int = 0
    downstream_communities: list[int] = field(default_factory=list)
    upstream_count: int = 0
    # Vulnerability
    is_spof: bool = False  # single point of failure
    fragmentation_if_removed: float = 0.0
    isolated_if_removed: int = 0

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "community": self.community,
            "degree_in": self.degree_in,
            "degree_out": self.degree_out,
            "betweenness": round(self.betweenness, 6),
            "pagerank": round(self.pagerank, 6),
            "eigenvector": round(self.eigenvector, 6),
            "role": self.role,
            "influence_score": round(self.influence_score, 4),
            "influence_breakdown": self.influence_breakdown,
            "downstream_count": self.downstream_count,
            "downstream_communities": self.downstream_communities,
            "upstream_count": self.upstream_count,
            "is_spof": self.is_spof,
            "fragmentation_if_removed": round(self.fragmentation_if_removed, 4),
            "isolated_if_removed": self.isolated_if_removed,
        }


@dataclass
class InfluencePath:
    """A scored path of influence between two nodes."""

    source: str
    target: str
    path: list[str]
    hops: int
    # Reliability: product of edge weights along path (normalized)
    reliability: float = 0.0
    # Bottleneck: weakest edge in the path
    bottleneck_edge: tuple[str, str] | None = None
    bottleneck_weight: float = 0.0
    # Communities traversed
    communities_crossed: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "path": self.path,
            "hops": self.hops,
            "reliability": round(self.reliability, 4),
            "bottleneck_edge": list(self.bottleneck_edge)
            if self.bottleneck_edge
            else None,
            "bottleneck_weight": round(self.bottleneck_weight, 4),
            "communities_crossed": self.communities_crossed,
        }


@dataclass
class NetworkIntel:
    """Complete network intelligence package."""

    # Graph metadata
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    community_count: int = 0
    # Node profiles
    nodes: dict[str, OperationalNode] = field(default_factory=dict)
    # Ranked lists
    hubs: list[str] = field(default_factory=list)
    bridges: list[str] = field(default_factory=list)
    amplifiers: list[str] = field(default_factory=list)
    seeds: list[str] = field(default_factory=list)
    gatekeepers: list[str] = field(default_factory=list)
    spofs: list[str] = field(default_factory=list)
    # Community map
    communities: dict[int, list[str]] = field(default_factory=dict)
    # Influence flow
    influence_report: InfluenceReport | None = None
    # Vulnerability
    vulnerability_report: VulnerabilityReport | None = None

    def to_dict(self) -> dict:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "density": round(self.density, 6),
            "community_count": self.community_count,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "hubs": self.hubs,
            "bridges": self.bridges,
            "amplifiers": self.amplifiers,
            "seeds": self.seeds,
            "gatekeepers": self.gatekeepers,
            "spofs": self.spofs,
            "communities": self.communities,
        }

    def top_nodes(self, by: str = "influence_score", n: int = 10) -> list[OperationalNode]:
        """Return top N nodes sorted by a given attribute."""
        nodes = list(self.nodes.values())
        nodes.sort(key=lambda x: getattr(x, by, 0), reverse=True)
        return nodes[:n]


@dataclass
class OperationPlan:
    """An actionable plan for a network operation."""

    objective: str
    # Entry points: where to start
    entry_points: list[dict[str, Any]] = field(default_factory=list)
    # Paths: ranked routes through the network
    paths: list[InfluencePath] = field(default_factory=list)
    # Amplification chain: who boosts in what order
    amplification_chain: list[dict[str, Any]] = field(default_factory=list)
    # Weak links: what to avoid or exploit
    weak_links: list[dict[str, Any]] = field(default_factory=list)
    # Estimated reach
    estimated_reach_pct: float = 0.0
    # Risk: what could go wrong
    risk_nodes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "objective": self.objective,
            "entry_points": self.entry_points,
            "paths": [p.to_dict() for p in self.paths],
            "amplification_chain": self.amplification_chain,
            "weak_links": self.weak_links,
            "estimated_reach_pct": round(self.estimated_reach_pct, 4),
            "risk_nodes": self.risk_nodes,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class NetworkEngine:
    """
    Operational network intelligence engine.

    Usage:
        engine = NetworkEngine(graph)
        intel = engine.analyze()

        # Find influence paths between two nodes
        paths = engine.find_influence_paths("alice", "bob")

        # Plan an operation targeting a community
        plan = engine.plan_operation(
            objective="reach",
            target_community=2,
            entry_nodes=["alice"],
        )

        # Find who controls information flow between communities
        gates = engine.find_gatekeepers(community_a=0, community_b=1)
    """

    def __init__(self, graph: nx.DiGraph) -> None:
        self.G = graph
        self._intel: NetworkIntel | None = None
        self._comm_map: dict[str, int] | None = None
        self._pagerank: dict[str, float] | None = None
        self._betweenness: dict[str, float] | None = None
        self._eigenvector: dict[str, float] | None = None

    # -- Lazy computed properties --

    @property
    def comm_map(self) -> dict[str, int]:
        if self._comm_map is None:
            self._comm_map = self._detect_communities()
        return self._comm_map

    @property
    def pagerank(self) -> dict[str, float]:
        if self._pagerank is None:
            self._pagerank = nx.pagerank(self.G, alpha=0.85)
        return self._pagerank

    @property
    def betweenness(self) -> dict[str, float]:
        if self._betweenness is None:
            self._betweenness = nx.betweenness_centrality(self.G, weight="weight")
        return self._betweenness

    @property
    def eigenvector(self) -> dict[str, float]:
        if self._eigenvector is None:
            try:
                self._eigenvector = nx.eigenvector_centrality_numpy(
                    self.G, weight="weight"
                )
            except Exception:
                try:
                    self._eigenvector = nx.eigenvector_centrality(
                        self.G, max_iter=500, weight="weight"
                    )
                except Exception:
                    self._eigenvector = dict.fromkeys(self.G.nodes(), 0.0)
        return self._eigenvector

    # -- Core analysis --

    def analyze(self) -> NetworkIntel:
        """Run full network analysis. Returns cached result on repeat calls."""
        if self._intel is not None:
            return self._intel

        intel = NetworkIntel()
        G = self.G

        # Metadata
        intel.node_count = G.number_of_nodes()
        intel.edge_count = G.number_of_edges()
        intel.density = nx.density(G)

        if intel.node_count == 0:
            self._intel = intel
            return intel

        # Communities
        comm_map = self.comm_map
        communities: dict[int, list[str]] = defaultdict(list)
        for node, cid in comm_map.items():
            communities[cid].append(node)
        intel.communities = dict(communities)
        intel.community_count = len(communities)

        # Influence scores
        influence_scores, influence_breakdown = compute_influence_scores(G)

        # SPOF detection
        spofs = set()
        try:
            U = G.to_undirected()
            for node in nx.articulation_points(U):
                spofs.add(node)
        except Exception:
            pass

        # Fragmentation (sample top betweenness nodes only for performance)
        frag_map: dict[str, tuple[float, int]] = {}
        top_betweenness = sorted(
            self.betweenness, key=self.betweenness.get, reverse=True
        )[:50]
        U_copy = G.to_undirected()
        n_total = U_copy.number_of_nodes()
        for node in top_betweenness:
            H = U_copy.copy()
            H.remove_node(node)
            comps = list(nx.connected_components(H))
            n_rem = n_total - 1
            largest = max(len(c) for c in comps) if comps else 0
            isolated = sum(1 for c in comps if len(c) == 1)
            frag = 1.0 - (largest / n_rem) if n_rem > 0 else 0.0
            frag_map[node] = (frag, isolated)

        # Build node profiles
        for node in G.nodes():
            op = OperationalNode(node=node)
            op.community = comm_map.get(node, -1)
            op.degree_in = G.in_degree(node)
            op.degree_out = G.out_degree(node)
            op.betweenness = self.betweenness.get(node, 0.0)
            op.pagerank = self.pagerank.get(node, 0.0)
            op.eigenvector = self.eigenvector.get(node, 0.0)
            op.influence_score = influence_scores.get(node, 0.0)
            op.influence_breakdown = influence_breakdown.get(node, {})

            # Downstream reach
            try:
                desc = nx.descendants(G, node)
                op.downstream_count = len(desc)
                op.downstream_communities = sorted(
                    {comm_map.get(d, -1) for d in desc} - {-1}
                )
            except Exception:
                pass

            # Upstream reach
            try:
                op.upstream_count = len(nx.ancestors(G, node))
            except Exception:
                pass

            # Vulnerability
            op.is_spof = node in spofs
            if node in frag_map:
                op.fragmentation_if_removed, op.isolated_if_removed = frag_map[node]

            # Role classification
            op.role = self._classify_role(op)

            intel.nodes[node] = op

        # Ranked lists
        intel.hubs = [
            n.node
            for n in sorted(
                intel.nodes.values(), key=lambda x: x.pagerank, reverse=True
            )[:20]
            if n.role == "hub" or n.pagerank > 0
        ][:20]

        intel.bridges = [
            n.node
            for n in intel.nodes.values()
            if n.role == "bridge"
        ]

        intel.amplifiers = [
            n.node
            for n in intel.nodes.values()
            if n.role == "amplifier"
        ]

        intel.seeds = [
            n.node
            for n in intel.nodes.values()
            if n.role == "seed"
        ]

        intel.gatekeepers = [
            n.node
            for n in intel.nodes.values()
            if n.role == "gatekeeper"
        ]

        intel.spofs = sorted(spofs)

        # Full reports
        intel.influence_report = analyze_influence_flow(G)
        intel.vulnerability_report = analyze_vulnerability(G)

        self._intel = intel
        return intel

    def _classify_role(self, op: OperationalNode) -> str:
        """Classify a node's operational role based on its metrics."""
        bd = op.influence_breakdown

        # Bridge: high betweenness, connects multiple communities
        if op.betweenness > 0.05 and len(op.downstream_communities) >= 2:
            return "bridge"

        # Gatekeeper: SPOF with high betweenness
        if op.is_spof and op.betweenness > 0.02:
            return "gatekeeper"

        # Hub: high pagerank and eigenvector
        if op.pagerank > 0.02 and op.eigenvector > 0.1:
            return "hub"

        # Seed: high seeding score (creates content that gets amplified)
        if bd.get("seeding", 0) > 0.3 and bd.get("amplification", 0) < 0.2:
            return "seed"

        # Amplifier: high amplification score
        if bd.get("amplification", 0) > 0.3:
            return "amplifier"

        return "peripheral"

    def _detect_communities(self) -> dict[str, int]:
        """Detect communities, return node -> community_id mapping."""
        U = self.G.to_undirected()
        try:
            communities = list(greedy_modularity_communities(U))
        except Exception:
            return {n: 0 for n in self.G.nodes()}
        mapping = {}
        for cid, members in enumerate(communities):
            for m in members:
                mapping[m] = cid
        return mapping

    # -- Influence paths --

    def find_influence_paths(
        self,
        source: str,
        target: str,
        k: int = 5,
        max_hops: int = 6,
    ) -> list[InfluencePath]:
        """
        Find the top-k influence paths between two nodes.

        Paths are scored by reliability (product of normalized edge weights)
        and annotated with bottleneck edges and communities crossed.
        """
        if source not in self.G or target not in self.G:
            return []

        # Use edge weight as capacity; invert for shortest path (lower = better)
        max_weight = max(
            (d.get("weight", 1.0) for _, _, d in self.G.edges(data=True)),
            default=1.0,
        )

        # Find k shortest simple paths by hop count, then score
        paths: list[InfluencePath] = []
        try:
            raw_paths = list(
                nx.shortest_simple_paths(
                    self.G, source, target, weight=None
                )
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

        comm_map = self.comm_map

        for raw_path in raw_paths:
            if len(raw_path) - 1 > max_hops:
                break
            if len(paths) >= k:
                break

            # Score: product of normalized edge weights
            reliability = 1.0
            min_weight = float("inf")
            min_edge = None
            for i in range(len(raw_path) - 1):
                u, v = raw_path[i], raw_path[i + 1]
                w = self.G[u][v].get("weight", 1.0) / max_weight
                reliability *= w
                if w < min_weight:
                    min_weight = w
                    min_edge = (u, v)

            # Communities crossed
            comms = []
            seen = set()
            for node in raw_path:
                c = comm_map.get(node, -1)
                if c not in seen and c != -1:
                    comms.append(c)
                    seen.add(c)

            paths.append(
                InfluencePath(
                    source=source,
                    target=target,
                    path=raw_path,
                    hops=len(raw_path) - 1,
                    reliability=reliability,
                    bottleneck_edge=min_edge,
                    bottleneck_weight=min_weight,
                    communities_crossed=comms,
                )
            )

        paths.sort(key=lambda p: p.reliability, reverse=True)
        return paths

    # -- Gatekeepers between communities --

    def find_gatekeepers(
        self,
        community_a: int,
        community_b: int,
    ) -> list[OperationalNode]:
        """
        Find nodes that control information flow between two communities.

        These are nodes that sit on paths between community_a and community_b
        with high betweenness relative to inter-community edges.
        """
        intel = self.analyze()
        members_a = set(intel.communities.get(community_a, []))
        members_b = set(intel.communities.get(community_b, []))

        if not members_a or not members_b:
            return []

        # Find nodes connected to both communities
        candidates = []
        for node, op in intel.nodes.items():
            neighbors = set(self.G.successors(node)) | set(self.G.predecessors(node))
            touches_a = bool(neighbors & members_a)
            touches_b = bool(neighbors & members_b)
            if touches_a and touches_b:
                candidates.append(op)

        candidates.sort(key=lambda x: x.betweenness, reverse=True)
        return candidates

    # -- Operation planning --

    def plan_operation(
        self,
        objective: str,
        target_nodes: list[str] | None = None,
        target_community: int | None = None,
        entry_nodes: list[str] | None = None,
        reach_target: float = 0.5,
    ) -> OperationPlan:
        """
        Generate an operation plan for reaching target nodes or a target community.

        Objective types:
        - "reach": maximize narrative reach into target
        - "disrupt": fragment the target community
        - "monitor": identify observation points for the target

        Returns an OperationPlan with entry points, paths, amplification
        chain, weak links, and risk assessment.
        """
        intel = self.analyze()
        plan = OperationPlan(objective=objective)

        # Resolve targets
        if target_community is not None:
            target_set = set(intel.communities.get(target_community, []))
        elif target_nodes:
            target_set = set(target_nodes)
        else:
            target_set = set(self.G.nodes())

        if not target_set:
            return plan

        # -- Entry points --
        if entry_nodes:
            for en in entry_nodes:
                if en in intel.nodes:
                    op = intel.nodes[en]
                    plan.entry_points.append({
                        "node": en,
                        "role": op.role,
                        "influence_score": op.influence_score,
                        "downstream_into_target": len(
                            set(nx.descendants(self.G, en)) & target_set
                        )
                        if en in self.G
                        else 0,
                    })
        else:
            # Auto-select: nodes with highest reach into target
            scored = []
            for node, op in intel.nodes.items():
                if node in target_set:
                    continue
                try:
                    desc = set(nx.descendants(self.G, node))
                except Exception:
                    desc = set()
                overlap = len(desc & target_set)
                if overlap > 0:
                    scored.append((node, overlap, op))
            scored.sort(key=lambda x: x[1], reverse=True)
            for node, overlap, op in scored[:5]:
                plan.entry_points.append({
                    "node": node,
                    "role": op.role,
                    "influence_score": op.influence_score,
                    "downstream_into_target": overlap,
                })

        # -- Paths --
        if plan.entry_points and target_nodes:
            for ep in plan.entry_points[:3]:
                for tn in target_nodes[:3]:
                    paths = self.find_influence_paths(ep["node"], tn, k=2)
                    plan.paths.extend(paths)
        elif plan.entry_points and target_community is not None:
            # Find paths to highest-influence nodes in target community
            target_hubs = sorted(
                [
                    intel.nodes[n]
                    for n in target_set
                    if n in intel.nodes
                ],
                key=lambda x: x.influence_score,
                reverse=True,
            )[:3]
            for ep in plan.entry_points[:3]:
                for th in target_hubs:
                    paths = self.find_influence_paths(ep["node"], th.node, k=2)
                    plan.paths.extend(paths)

        # -- Amplification chain --
        # Identify amplifier nodes reachable from entry points that feed into target
        amp_candidates = []
        entry_set = {ep["node"] for ep in plan.entry_points}
        for node, op in intel.nodes.items():
            if node in entry_set or node in target_set:
                continue
            if op.role in ("amplifier", "hub"):
                # Check if reachable from any entry AND reaches target
                reaches_target = bool(
                    set(self.G.successors(node)) & target_set
                )
                reachable_from_entry = any(
                    self.G.has_edge(ep["node"], node) or node in nx.descendants(self.G, ep["node"])
                    for ep in plan.entry_points[:3]
                    if ep["node"] in self.G
                )
                if reaches_target or reachable_from_entry:
                    amp_candidates.append({
                        "node": node,
                        "role": op.role,
                        "influence_score": op.influence_score,
                        "reaches_target": reaches_target,
                    })
        amp_candidates.sort(key=lambda x: x["influence_score"], reverse=True)
        plan.amplification_chain = amp_candidates[:10]

        # -- Weak links --
        # Nodes in or adjacent to target with high fragmentation impact
        for node in target_set:
            if node in intel.nodes:
                op = intel.nodes[node]
                if op.is_spof or op.fragmentation_if_removed > 0.1:
                    plan.weak_links.append({
                        "node": node,
                        "fragmentation_if_removed": op.fragmentation_if_removed,
                        "is_spof": op.is_spof,
                        "role": op.role,
                    })
        plan.weak_links.sort(
            key=lambda x: x["fragmentation_if_removed"], reverse=True
        )

        # -- Estimated reach --
        reachable = set()
        for ep in plan.entry_points:
            if ep["node"] in self.G:
                reachable.update(nx.descendants(self.G, ep["node"]))
        plan.estimated_reach_pct = (
            len(reachable & target_set) / len(target_set) if target_set else 0
        )

        # -- Risk nodes --
        # SPOFs along our paths that could break the operation
        path_nodes = set()
        for p in plan.paths:
            path_nodes.update(p.path)
        for node in path_nodes:
            if node in intel.nodes and intel.nodes[node].is_spof:
                plan.risk_nodes.append({
                    "node": node,
                    "reason": "single point of failure on operation path",
                    "betweenness": intel.nodes[node].betweenness,
                })

        return plan

    # -- Comparison: two snapshots --

    def compare(self, other: "NetworkEngine") -> dict[str, Any]:
        """
        Compare this network state against another (e.g., earlier snapshot).

        Returns structural changes: new/lost nodes, role shifts,
        influence score changes, community realignment.
        """
        intel_a = self.analyze()
        intel_b = other.analyze()

        nodes_a = set(intel_a.nodes.keys())
        nodes_b = set(intel_b.nodes.keys())

        new_nodes = nodes_b - nodes_a
        lost_nodes = nodes_a - nodes_b
        shared = nodes_a & nodes_b

        role_changes = []
        influence_shifts = []
        for node in shared:
            a = intel_a.nodes[node]
            b = intel_b.nodes[node]
            if a.role != b.role:
                role_changes.append({
                    "node": node,
                    "from": a.role,
                    "to": b.role,
                })
            delta = b.influence_score - a.influence_score
            if abs(delta) > 0.05:
                influence_shifts.append({
                    "node": node,
                    "delta": round(delta, 4),
                    "from": round(a.influence_score, 4),
                    "to": round(b.influence_score, 4),
                })

        influence_shifts.sort(key=lambda x: abs(x["delta"]), reverse=True)

        # Community changes
        comm_changes = []
        for node in shared:
            a_comm = intel_a.nodes[node].community
            b_comm = intel_b.nodes[node].community
            if a_comm != b_comm:
                comm_changes.append({
                    "node": node,
                    "from_community": a_comm,
                    "to_community": b_comm,
                })

        return {
            "new_nodes": sorted(new_nodes),
            "lost_nodes": sorted(lost_nodes),
            "role_changes": role_changes,
            "influence_shifts": influence_shifts[:20],
            "community_changes": comm_changes,
            "node_count_delta": intel_b.node_count - intel_a.node_count,
            "edge_count_delta": intel_b.edge_count - intel_a.edge_count,
            "density_delta": round(intel_b.density - intel_a.density, 6),
        }

    # -- Export --

    def export_intel(self, path: str | Path) -> None:
        """Export full network intelligence to JSON."""
        intel = self.analyze()
        data = intel.to_dict()
        Path(path).write_text(json.dumps(data, indent=2, default=str))
        logger.info("Exported network intel to %s", path)

    def export_plan(self, plan: OperationPlan, path: str | Path) -> None:
        """Export an operation plan to JSON."""
        Path(path).write_text(
            json.dumps(plan.to_dict(), indent=2, default=str)
        )
        logger.info("Exported operation plan to %s", path)
