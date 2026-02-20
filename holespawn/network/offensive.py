"""
Offensive network operations: the cognitive kill chain.

Plan → Target → Inject → Amplify → Fracture → Simulate.

Functions for narrative injection planning, amplification strategy,
community fracture analysis, bridge capture assessment, counter-narrative
mapping, and full operation simulation using cascade models.

Works with NetworkX DiGraphs from graph_builder.py and content data
from content_overlay.py.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Sequence

import networkx as nx

logger = logging.getLogger(__name__)

try:
    from networkx.algorithms.community import greedy_modularity_communities
except ImportError:
    from networkx.algorithms.community.modularity_max import greedy_modularity_communities


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class InjectionCandidate:
    """A node scored for narrative injection potential."""
    node: str
    score: float
    bridge_reach: int  # communities touched
    trust_capital: float  # PageRank in source community
    narrative_alignment: float  # 0-1 similarity to payload
    propagation_paths: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "score": round(self.score, 4),
            "bridge_reach": self.bridge_reach,
            "trust_capital": round(self.trust_capital, 4),
            "narrative_alignment": round(self.narrative_alignment, 4),
            "propagation_paths": self.propagation_paths,
        }


@dataclass
class AmplificationSchedule:
    """Who boosts when, in what order."""
    steps: list[dict[str, Any]] = field(default_factory=list)
    total_amplifiers: int = 0
    estimated_reach_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "steps": self.steps,
            "total_amplifiers": self.total_amplifiers,
            "estimated_reach_pct": round(self.estimated_reach_pct, 4),
        }


@dataclass
class FracturePlan:
    """Plan for widening fault lines within a community."""
    subgroups: list[list[str]] = field(default_factory=list)
    fault_lines: list[dict[str, Any]] = field(default_factory=list)
    wedge_topics: list[dict[str, Any]] = field(default_factory=list)
    estimated_cohesion_impact: float = 0.0  # negative = community weakens

    def to_dict(self) -> dict:
        return {
            "subgroups": self.subgroups,
            "fault_lines": self.fault_lines,
            "wedge_topics": self.wedge_topics,
            "estimated_cohesion_impact": round(self.estimated_cohesion_impact, 4),
        }


@dataclass
class BridgeCaptureReport:
    """Assessment of turning a bridge node."""
    bridge_node: str
    resistance: float  # 0-1, higher = harder to turn
    downstream_communities: list[int] = field(default_factory=list)
    downstream_reach: int = 0
    current_alignment: dict[str, float] = field(default_factory=dict)
    estimated_effort: str = "medium"  # low/medium/high

    def to_dict(self) -> dict:
        return {
            "bridge_node": self.bridge_node,
            "resistance": round(self.resistance, 4),
            "downstream_communities": self.downstream_communities,
            "downstream_reach": self.downstream_reach,
            "current_alignment": {
                k: round(v, 4) for k, v in self.current_alignment.items()
            },
            "estimated_effort": self.estimated_effort,
        }


@dataclass
class CounterNarrativeMap:
    """Map of hostile narrative spread and containment plan."""
    infected_nodes: list[str] = field(default_factory=list)
    spread_pct: float = 0.0
    containment_points: list[dict[str, Any]] = field(default_factory=list)
    minimum_deployment: list[str] = field(default_factory=list)
    estimated_reduction: float = 0.0

    def to_dict(self) -> dict:
        return {
            "infected_nodes": self.infected_nodes,
            "spread_pct": round(self.spread_pct, 4),
            "containment_points": self.containment_points,
            "minimum_deployment": self.minimum_deployment,
            "estimated_reduction": round(self.estimated_reduction, 4),
        }


@dataclass
class SimulationTimeline:
    """Timeline of network state across simulation steps."""
    steps: list[dict[str, Any]] = field(default_factory=list)
    final_reach_pct: float = 0.0
    community_states: dict[int, list[float]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "steps": self.steps,
            "final_reach_pct": round(self.final_reach_pct, 4),
            "community_states": {
                k: [round(v, 4) for v in vs]
                for k, vs in self.community_states.items()
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_communities(G: nx.DiGraph) -> dict[str, int]:
    """Detect communities, return node -> community_id mapping."""
    undirected = G.to_undirected()
    try:
        communities = list(greedy_modularity_communities(undirected))
    except Exception:
        # Fallback: every node is its own community
        return {n: i for i, n in enumerate(G.nodes())}
    mapping = {}
    for cid, members in enumerate(communities):
        for m in members:
            mapping[m] = cid
    return mapping


def _community_members(comm_map: dict[str, int], community_id: int) -> list[str]:
    """Get all members of a community."""
    return [n for n, c in comm_map.items() if c == community_id]


def _node_topic_overlap(G: nx.DiGraph, node: str, narrative_keywords: set[str]) -> float:
    """Compute narrative alignment: overlap between node's content topics and narrative keywords."""
    node_data = G.nodes.get(node, {})
    topics = set()
    for key in ("topics", "top_topics", "hashtags"):
        val = node_data.get(key, [])
        if isinstance(val, list):
            for item in val:
                if isinstance(item, tuple):
                    topics.add(str(item[0]).lower())
                elif isinstance(item, str):
                    topics.add(item.lower())
    content = node_data.get("content", "")
    if isinstance(content, str):
        topics.update(w.lower() for w in content.split() if len(w) > 3)
    if not topics and not narrative_keywords:
        return 0.0
    if not topics or not narrative_keywords:
        return 0.0
    return len(topics & narrative_keywords) / len(topics | narrative_keywords)


def _narrative_keywords(narrative: str) -> set[str]:
    """Extract keywords from a narrative string."""
    return {w.lower().strip(".,!?;:'\"") for w in narrative.split() if len(w) > 3}


# ---------------------------------------------------------------------------
# 1. Narrative Injection Planner
# ---------------------------------------------------------------------------

def narrative_injection_planner(
    graph: nx.DiGraph,
    target_community: int,
    narrative: str,
    top_k: int = 10,
) -> list[InjectionCandidate]:
    """
    Identify optimal injection points for a narrative into a target community.

    Scores each candidate node by:
    - Bridge reach: how many distinct communities the node connects to
    - Trust capital: PageRank within the source community (authority)
    - Narrative alignment: semantic overlap between node's existing content
      and the injection payload

    Returns ranked list of injection candidates with propagation paths
    into the target community.
    """
    comm_map = _detect_communities(graph)
    target_members = set(_community_members(comm_map, target_community))

    if not target_members:
        logger.warning("Target community %d has no members", target_community)
        return []

    pagerank = nx.pagerank(graph, alpha=0.85)
    keywords = _narrative_keywords(narrative)

    # Candidate nodes: those NOT in target community (injection from outside)
    # or bridge nodes that straddle communities
    candidates = []
    for node in graph.nodes():
        neighbors = set(graph.successors(node)) | set(graph.predecessors(node))
        neighbor_communities = {comm_map.get(n, -1) for n in neighbors}

        # Must have path into target community
        touches_target = target_community in neighbor_communities or node in target_members
        if not touches_target:
            continue

        bridge_reach = len(neighbor_communities - {-1})
        trust_capital = pagerank.get(node, 0.0)
        alignment = _node_topic_overlap(graph, node, keywords)

        # Composite score: weighted sum
        score = (bridge_reach * 0.3) + (trust_capital * 100 * 0.4) + (alignment * 0.3)

        # Compute propagation paths (BFS-like, up to 3 hops into target)
        # Use unweighted BFS which is O(V+E) and faster than Dijkstra
        prop_paths = []
        for target_node in list(target_members)[:5]:  # sample target nodes
            try:
                path = nx.shortest_path(graph, node, target_node, weight=None)
                if len(path) <= 4:
                    prop_paths.append(path)
            except nx.NetworkXNoPath:
                continue

        candidates.append(InjectionCandidate(
            node=node,
            score=score,
            bridge_reach=bridge_reach,
            trust_capital=trust_capital,
            narrative_alignment=alignment,
            propagation_paths=prop_paths,
        ))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:top_k]


# ---------------------------------------------------------------------------
# 2. Amplification Strategy
# ---------------------------------------------------------------------------

def amplification_strategy(
    graph: nx.DiGraph,
    seed_nodes: list[str],
    target_reach_pct: float = 0.5,
    target_community: int | None = None,
) -> AmplificationSchedule:
    """
    Calculate the minimum amplification network to reach N% of a target community.

    Given seed nodes that will post content, finds the cheapest path through
    RT/QT chains to achieve target reach percentage. Returns an amplification
    schedule: who boosts when, in what order.
    """
    comm_map = _detect_communities(graph)

    if target_community is not None:
        target_members = set(_community_members(comm_map, target_community))
    else:
        target_members = set(graph.nodes())

    if not target_members:
        return AmplificationSchedule()

    target_size = len(target_members)
    target_count = int(target_size * target_reach_pct)

    # Greedy expansion: start from seeds, greedily add amplifiers
    reached = set(seed_nodes) & target_members
    frontier = set(seed_nodes)
    schedule_steps = []
    step = 0
    used_amplifiers = set(seed_nodes)

    while len(reached) < target_count and frontier:
        step += 1
        next_frontier = set()
        step_amplifiers = []

        # Score all reachable-but-not-yet-used nodes by how many new target
        # members they'd reach
        candidates = []
        for node in frontier:
            for neighbor in graph.successors(node):
                if neighbor in used_amplifiers:
                    continue
                new_reach = set(graph.successors(neighbor)) & target_members - reached
                # Weight by edge weight (RT/QT = higher)
                edge_data = graph.get_edge_data(node, neighbor, default={})
                weight = edge_data.get("weight", 1.0)
                candidates.append((neighbor, new_reach, weight, node))

        # Sort by reach * weight (most efficient amplifiers first)
        candidates.sort(key=lambda x: len(x[1]) * x[2], reverse=True)

        for amp_node, new_reach, weight, source in candidates:
            if len(reached) >= target_count:
                break
            if amp_node in used_amplifiers:
                continue
            used_amplifiers.add(amp_node)
            reached.update(new_reach)
            reached.add(amp_node) if amp_node in target_members else None
            next_frontier.add(amp_node)
            step_amplifiers.append({
                "node": amp_node,
                "source": source,
                "new_reach": len(new_reach),
                "edge_weight": weight,
            })

        if step_amplifiers:
            schedule_steps.append({
                "step": step,
                "amplifiers": step_amplifiers,
                "cumulative_reach": len(reached),
                "reach_pct": len(reached) / target_size if target_size else 0,
            })

        frontier = next_frontier
        if not next_frontier:
            break

    return AmplificationSchedule(
        steps=schedule_steps,
        total_amplifiers=len(used_amplifiers) - len(seed_nodes),
        estimated_reach_pct=len(reached) / target_size if target_size else 0,
    )


# ---------------------------------------------------------------------------
# 3. Community Fracture Planner
# ---------------------------------------------------------------------------

def community_fracture_planner(
    graph: nx.DiGraph,
    target_community: int,
) -> FracturePlan:
    """
    Identify internal fault lines within a community and plan fracture operations.

    Finds subgroups with weaker internal connections, wedge topics that
    differentiate subgroups, and narratives that would widen existing fractures.
    Returns a fracture plan with estimated community cohesion impact.
    """
    comm_map = _detect_communities(graph)
    members = _community_members(comm_map, target_community)

    if len(members) < 4:
        return FracturePlan(estimated_cohesion_impact=0.0)

    # Build subgraph for this community
    subgraph = graph.subgraph(members).copy()
    undirected_sub = subgraph.to_undirected()

    # Find subgroups using bisection or sub-community detection
    try:
        sub_communities = list(greedy_modularity_communities(undirected_sub))
        if len(sub_communities) < 2:
            # Force bisection via edge betweenness
            sub_communities = _bisect_community(undirected_sub)
    except Exception:
        sub_communities = _bisect_community(undirected_sub)

    subgroups = [list(sg) for sg in sub_communities]

    # Compute fault lines: edges between subgroups with low weight
    fault_lines = []
    for i, sg_a in enumerate(subgroups):
        for j, sg_b in enumerate(subgroups):
            if i >= j:
                continue
            cross_edges = []
            for u in sg_a:
                for v in sg_b:
                    if subgraph.has_edge(u, v):
                        w = subgraph[u][v].get("weight", 1.0)
                        cross_edges.append({"from": u, "to": v, "weight": w})
            if cross_edges:
                avg_weight = sum(e["weight"] for e in cross_edges) / len(cross_edges)
                fault_lines.append({
                    "subgroup_a": i,
                    "subgroup_b": j,
                    "cross_edges": len(cross_edges),
                    "avg_weight": round(avg_weight, 4),
                    "weakest_links": sorted(cross_edges, key=lambda e: e["weight"])[:3],
                })

    # Find wedge topics: topics unique to each subgroup
    wedge_topics = []
    subgroup_topics = []
    for sg in subgroups:
        topics: defaultdict[str, int] = defaultdict(int)
        for node in sg:
            node_data = graph.nodes.get(node, {})
            for key in ("topics", "top_topics"):
                for item in node_data.get(key, []):
                    topic = item[0] if isinstance(item, tuple) else str(item)
                    topics[topic.lower()] += 1
        subgroup_topics.append(topics)

    for i, topics_a in enumerate(subgroup_topics):
        for j, topics_b in enumerate(subgroup_topics):
            if i >= j:
                continue
            only_a = {t for t in topics_a if t not in topics_b}
            only_b = {t for t in topics_b if t not in topics_a}
            if only_a or only_b:
                wedge_topics.append({
                    "subgroup_a": i,
                    "subgroup_b": j,
                    "unique_to_a": list(only_a)[:10],
                    "unique_to_b": list(only_b)[:10],
                })

    # Estimate cohesion impact
    original_modularity = _compute_modularity(undirected_sub, [set(members)])
    fractured_modularity = _compute_modularity(undirected_sub, [set(sg) for sg in subgroups])
    cohesion_impact = fractured_modularity - original_modularity  # negative = weaker

    return FracturePlan(
        subgroups=subgroups,
        fault_lines=fault_lines,
        wedge_topics=wedge_topics,
        estimated_cohesion_impact=cohesion_impact,
    )


def _bisect_community(G: nx.Graph) -> list[set[str]]:
    """Bisect a graph using Kernighan-Lin or simple spectral approach."""
    try:
        from networkx.algorithms.community import kernighan_lin_bisection
        return list(kernighan_lin_bisection(G))
    except Exception:
        nodes = list(G.nodes())
        mid = len(nodes) // 2
        return [set(nodes[:mid]), set(nodes[mid:])]


def _compute_modularity(G: nx.Graph, communities: list[set]) -> float:
    """Compute modularity of a partition."""
    try:
        return nx.algorithms.community.modularity(G, communities)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# 4. Bridge Capture Assessment
# ---------------------------------------------------------------------------

def bridge_capture_assessment(
    graph: nx.DiGraph,
    bridge_node: str,
) -> BridgeCaptureReport:
    """
    Assess what it takes to "turn" a bridge node—shift its content alignment.

    Maps downstream impact: if this bridge starts carrying different narratives,
    which communities are affected. Estimates resistance based on how deeply
    embedded the node is in its current narrative position.
    """
    if bridge_node not in graph:
        raise ValueError(f"Node {bridge_node!r} not in graph")

    comm_map = _detect_communities(graph)
    pagerank = nx.pagerank(graph, alpha=0.85)

    node_community = comm_map.get(bridge_node, -1)
    neighbors = set(graph.successors(bridge_node)) | set(graph.predecessors(bridge_node))
    neighbor_communities = {comm_map.get(n, -1) for n in neighbors} - {-1}

    # Downstream: communities reachable through this bridge
    downstream = set()
    downstream_nodes = set()
    for successor in nx.descendants(graph, bridge_node):
        c = comm_map.get(successor, -1)
        if c != node_community and c != -1:
            downstream.add(c)
            downstream_nodes.add(successor)

    # Resistance: based on clustering coefficient, in-degree ratio within
    # own community, and PageRank
    community_members = set(_community_members(comm_map, node_community))
    in_community_edges = sum(
        1 for pred in graph.predecessors(bridge_node) if pred in community_members
    )
    total_in = graph.in_degree(bridge_node)
    embeddedness = in_community_edges / total_in if total_in > 0 else 0.0

    try:
        clustering = nx.clustering(graph.to_undirected(), bridge_node)
    except Exception:
        clustering = 0.0

    resistance = (embeddedness * 0.5) + (clustering * 0.3) + (min(pagerank.get(bridge_node, 0) * 100, 1.0) * 0.2)

    # Current alignment from node data
    node_data = graph.nodes.get(bridge_node, {})
    current_alignment = {}
    for key in ("topics", "top_topics"):
        for item in node_data.get(key, []):
            if isinstance(item, tuple):
                current_alignment[str(item[0])] = float(item[1])

    effort = "low" if resistance < 0.3 else ("high" if resistance > 0.7 else "medium")

    return BridgeCaptureReport(
        bridge_node=bridge_node,
        resistance=resistance,
        downstream_communities=sorted(downstream),
        downstream_reach=len(downstream_nodes),
        current_alignment=current_alignment,
        estimated_effort=effort,
    )


# ---------------------------------------------------------------------------
# 5. Counter-Narrative Mapper
# ---------------------------------------------------------------------------

def counter_narrative_mapper(
    graph: nx.DiGraph,
    hostile_narrative: str,
    infected_nodes: list[str] | None = None,
) -> CounterNarrativeMap:
    """
    Map the spread of a hostile narrative and plan containment.

    If infected_nodes not provided, infers them from content overlap with
    the hostile narrative keywords. Identifies containment points where
    counter-messaging would be most effective, and calculates the minimum
    deployment to reduce hostile reach by 50%.
    """
    keywords = _narrative_keywords(hostile_narrative)

    # Identify infected nodes
    if infected_nodes is None:
        infected_nodes = []
        for node in graph.nodes():
            overlap = _node_topic_overlap(graph, node, keywords)
            if overlap > 0.1:
                infected_nodes.append(node)

    infected_set = set(infected_nodes)
    total_nodes = len(graph.nodes())

    if not infected_set:
        return CounterNarrativeMap(spread_pct=0.0)

    spread_pct = len(infected_set) / total_nodes if total_nodes else 0

    # Containment points: non-infected nodes with high betweenness that
    # sit between infected and clean zones
    betweenness = nx.betweenness_centrality(graph)
    containment_candidates = []

    for node in graph.nodes():
        if node in infected_set:
            continue
        # Check if node has infected predecessors and clean successors
        infected_preds = sum(1 for p in graph.predecessors(node) if p in infected_set)
        clean_succs = sum(1 for s in graph.successors(node) if s not in infected_set)
        if infected_preds > 0 and clean_succs > 0:
            score = betweenness.get(node, 0) * infected_preds * clean_succs
            containment_candidates.append({
                "node": node,
                "score": round(score, 4),
                "infected_predecessors": infected_preds,
                "clean_successors": clean_succs,
                "betweenness": round(betweenness.get(node, 0), 4),
            })

    containment_candidates.sort(key=lambda x: x["score"], reverse=True)

    # Minimum deployment: greedily select containment nodes until we'd
    # block 50% of infection spread paths
    target_block = len(infected_set) * 0.5
    deployment = []
    blocked = 0
    for candidate in containment_candidates:
        deployment.append(candidate["node"])
        blocked += candidate["clean_successors"]
        if blocked >= target_block:
            break

    return CounterNarrativeMap(
        infected_nodes=infected_nodes,
        spread_pct=spread_pct,
        containment_points=containment_candidates[:20],
        minimum_deployment=deployment,
        estimated_reduction=min(blocked / len(infected_set), 1.0) if infected_set else 0,
    )


# ---------------------------------------------------------------------------
# 6. Operation Simulator
# ---------------------------------------------------------------------------

def operation_simulator(
    graph: nx.DiGraph,
    plan: dict[str, Any],
    steps: int = 10,
    model: str = "independent_cascade",
    seed: int | None = None,
) -> SimulationTimeline:
    """
    Simulate an operation over N time steps using a cascade model.

    Supports:
    - independent_cascade: each infected node independently activates
      neighbors with probability = edge weight / max_weight
    - linear_threshold: nodes activate when fraction of infected neighbors
      exceeds a threshold

    Plan should contain:
    - seed_nodes: list of initially activated nodes
    - type: "injection" | "amplification" | "fracture" (for logging)

    Tracks community-level belief state changes across the timeline.
    """
    rng = random.Random(seed)
    comm_map = _detect_communities(graph)
    all_communities = set(comm_map.values())

    seed_nodes = set(plan.get("seed_nodes", []))
    activated = set(seed_nodes)
    timeline_steps = []

    # Precompute max weight for normalization
    max_weight = max(
        (d.get("weight", 1.0) for _, _, d in graph.edges(data=True)),
        default=1.0,
    )

    # Node thresholds for LT model
    if model == "linear_threshold":
        thresholds = {n: rng.uniform(0.1, 0.5) for n in graph.nodes()}

    for step_i in range(steps):
        new_activated = set()

        if model == "independent_cascade":
            for node in list(activated):
                for neighbor in graph.successors(node):
                    if neighbor in activated or neighbor in new_activated:
                        continue
                    edge_w = graph[node][neighbor].get("weight", 1.0)
                    prob = edge_w / max_weight
                    if rng.random() < prob:
                        new_activated.add(neighbor)

        elif model == "linear_threshold":
            for node in graph.nodes():
                if node in activated:
                    continue
                preds = list(graph.predecessors(node))
                if not preds:
                    continue
                active_weight = sum(
                    graph[p][node].get("weight", 1.0)
                    for p in preds if p in activated
                )
                total_weight = sum(
                    graph[p][node].get("weight", 1.0) for p in preds
                )
                if total_weight > 0 and (active_weight / total_weight) >= thresholds[node]:
                    new_activated.add(node)

        activated.update(new_activated)

        # Community-level states
        comm_counts: defaultdict[int, int] = defaultdict(int)
        comm_sizes: defaultdict[int, int] = defaultdict(int)
        for node, cid in comm_map.items():
            comm_sizes[cid] += 1
            if node in activated:
                comm_counts[cid] += 1

        comm_state = {
            cid: comm_counts[cid] / comm_sizes[cid] if comm_sizes[cid] else 0
            for cid in all_communities
        }

        timeline_steps.append({
            "step": step_i + 1,
            "newly_activated": len(new_activated),
            "total_activated": len(activated),
            "reach_pct": len(activated) / len(graph.nodes()) if graph.nodes() else 0,
            "community_states": {k: round(v, 4) for k, v in comm_state.items()},
        })

        if not new_activated:
            # Cascade died
            break

    # Build community state timelines
    community_timelines: dict[int, list[float]] = defaultdict(list)
    for s in timeline_steps:
        for cid, val in s["community_states"].items():
            community_timelines[cid].append(val)

    return SimulationTimeline(
        steps=timeline_steps,
        final_reach_pct=len(activated) / len(graph.nodes()) if graph.nodes() else 0,
        community_states=dict(community_timelines),
    )
