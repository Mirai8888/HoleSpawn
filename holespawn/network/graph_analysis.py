"""
Graph analysis from NetworkData: build weighted graph, Louvain communities,
centrality, bridge/amplifier/gatekeeper/vulnerable nodes, influence paths.
v2: Graph built from inner_circle + target only, using data.edges; Louvain resolution fallback; sanity_check.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from holespawn.ingest.network import NetworkData

logger = logging.getLogger(__name__)

try:
    import networkx as nx
except ImportError:
    nx = None

try:
    import community as community_louvain
except ImportError:
    community_louvain = None


@dataclass
class NetworkAnalysis:
    """Result of graph analysis: graph, communities, key node lists, serializable for JSON."""

    graph: Any = None  # nx.DiGraph
    communities: dict[int, list[str]] = field(default_factory=dict)
    community_metrics: dict[int, dict] = field(default_factory=dict)  # community_id -> {size, density, hub_node, bridge_count}
    node_metrics: dict[str, dict] = field(default_factory=dict)  # username -> {degree, betweenness, eigenvector, community, role, ...}
    bridge_nodes: list[dict] = field(default_factory=list)
    amplifiers: list[dict] = field(default_factory=list)
    gatekeepers: list[dict] = field(default_factory=list)
    vulnerable_entry_points: list[dict] = field(default_factory=list)
    community_profiles: dict[int, dict] = field(default_factory=dict)
    influence_paths: list[dict] = field(default_factory=list)
    sanity_check: dict = field(default_factory=dict)  # n_nodes, n_edges, n_communities, density, is_valid
    node_community: dict[str, int] = field(default_factory=dict)
    betweenness: dict[str, float] = field(default_factory=dict)
    eigenvector: dict[str, float] = field(default_factory=dict)
    in_degree: dict[str, int] = field(default_factory=dict)
    out_degree: dict[str, int] = field(default_factory=dict)


def _build_weighted_graph(data: NetworkData) -> nx.DiGraph:
    """Build directed graph from data.edges; include only nodes in inner_circle + target."""
    allowed = set(data.inner_circle) | {data.target_username}
    G = nx.DiGraph()
    for e in data.edges:
        s, t = e.get("source"), e.get("target")
        if not s or not t:
            continue
        if s not in allowed or t not in allowed:
            continue
        w = float(e.get("weight", 1))
        if G.has_edge(s, t):
            G[s][t]["weight"] = G[s][t].get("weight", 0) + w
        else:
            G.add_edge(s, t, weight=w)
    # Ensure target and all inner_circle nodes exist as nodes (even if isolate)
    for n in allowed:
        if n not in G:
            G.add_node(n)
    return G


def _rt_ratio_for_user(username: str, interactions: list[dict]) -> float:
    """Return ratio of rt count to total interactions for this user in target's interactions."""
    for rec in interactions:
        if (rec.get("username") or "").lower() == username.lower():
            tc = rec.get("type_counts") or {}
            total = sum(tc.values()) or 1
            return (tc.get("rt") or 0) / total
    return 0.0


def build_network_analysis(data: NetworkData) -> NetworkAnalysis:
    """
    Build weighted graph from NetworkData, run Louvain, compute centrality and roles.
    Returns NetworkAnalysis (graph + lists of bridge/amplifier/gatekeeper/vulnerable nodes).
    """
    result = NetworkAnalysis()
    if nx is None:
        return result
    G = _build_weighted_graph(data)
    result.graph = G
    if G.number_of_nodes() == 0:
        return result

    # Undirected for Louvain
    G_undir = nx.Graph()
    for u, v, d in G.edges(data=True):
        w = d.get("weight", 1)
        if G_undir.has_edge(u, v):
            G_undir[u][v]["weight"] = G_undir[u][v].get("weight", 1) + w
        else:
            G_undir.add_edge(u, v, weight=w)

    # Community detection (Louvain); resolution fallback if only 1 community
    partition: dict[str, int] = {}
    if community_louvain is not None and G_undir.number_of_edges() > 0:
        try:
            partition = community_louvain.best_partition(G_undir, resolution=1.0)
            n_comm = len(set(partition.values()))
            if n_comm <= 1:
                for res in [1.2, 1.5, 2.0]:
                    partition = community_louvain.best_partition(G_undir, resolution=res)
                    if len(set(partition.values())) > 1:
                        break
                if len(set(partition.values())) <= 1:
                    logger.warning(
                        "Only 1 community detected. Inter-connection edges may be missing or too sparse. Check network data collection."
                    )
            result.node_community = partition
            comm_lists: dict[int, list[str]] = defaultdict(list)
            for node, cid in partition.items():
                comm_lists[cid].append(node)
            result.communities = dict(comm_lists)
        except Exception as e:
            logger.warning("Louvain failed: %s", e)
            result.communities = {0: list(G.nodes())}
            result.node_community = {n: 0 for n in G.nodes()}
    else:
        result.communities = {0: list(G.nodes())}
        result.node_community = {n: 0 for n in G.nodes()}

    # Centrality
    try:
        result.betweenness = nx.betweenness_centrality(G, weight="weight")
    except Exception:
        result.betweenness = {n: 0.0 for n in G.nodes()}
    try:
        result.eigenvector = nx.eigenvector_centrality(G, weight="weight", max_iter=500)
    except Exception:
        result.eigenvector = {n: 0.0 for n in G.nodes()}
    result.in_degree = dict(G.in_degree())
    result.out_degree = dict(G.out_degree())

    # Bridge nodes: high betweenness
    sorted_bet = sorted(
        result.betweenness.items(), key=lambda x: -x[1]
    )
    for node, bet in sorted_bet[: max(20, G.number_of_nodes() // 5)]:
        if bet <= 0:
            continue
        cid = result.node_community.get(node, 0)
        connected = list(
            set(result.node_community.get(n, -1) for n in G.neighbors(node))
            | {result.node_community.get(n, -1) for n in G.predecessors(node)}
        )
        connected = [c for c in connected if c >= 0 and c != cid]
        result.bridge_nodes.append(
            {
                "username": node,
                "betweenness": round(bet, 4),
                "communities_connected": list(set(connected)),
            }
        )

    # Amplifiers: high out-degree + high rt ratio
    rt_ratios = {
        (rec.get("username") or "").lower(): _rt_ratio_for_user(
            rec.get("username", ""), data.interactions
        )
        for rec in data.interactions
    }
    out_deg_list = sorted(result.out_degree.items(), key=lambda x: -x[1])
    for node, od in out_deg_list[:30]:
        rt_r = rt_ratios.get(node.lower(), 0)
        result.amplifiers.append(
            {"username": node, "out_degree": od, "rt_ratio": round(rt_r, 3)}
        )

    # Gatekeepers: high in-degree within community, low external
    for cid, members in result.communities.items():
        for node in members[:15]:
            in_d = result.in_degree.get(node, 0)
            out_d = result.out_degree.get(node, 0)
            internal_in = sum(
                1 for p in G.predecessors(node) if result.node_community.get(p) == cid
            )
            external_in = in_d - internal_in
            result.gatekeepers.append(
                {
                    "username": node,
                    "community_id": cid,
                    "internal_degree": internal_in,
                    "external_degree": external_in,
                }
            )

    # Vulnerable entry points: low degree but connected to high-value (high betweenness) nodes
    high_value = set(n for n, _ in sorted_bet[: max(10, G.number_of_nodes() // 10)])
    for node in G.nodes():
        if node in high_value:
            continue
        preds = list(G.predecessors(node))
        succs = list(G.successors(node))
        connected_to = set(preds) | set(succs)
        if not connected_to:
            continue
        if result.in_degree.get(node, 0) + result.out_degree.get(node, 0) > 10:
            continue
        if connected_to & high_value:
            result.vulnerable_entry_points.append(
                {
                    "username": node,
                    "reason": "low_degree_connected_to_high_value",
                    "connected_to": list(connected_to & high_value)[:10],
                }
            )

    # Community profiles (summary stats per community)
    for cid, members in result.communities.items():
        result.community_profiles[cid] = {
            "theme": f"community_{cid}",
            "size": len(members),
            "density": (
                nx.density(G_undir.subgraph(members)) if len(members) > 1 else 0
            ),
            "key_topics": members[:5],
        }

    # Influence paths: shortest paths through target
    target = data.target_username
    if target in G and G.number_of_nodes() > 2:
        try:
            for _ in range(min(5, len(result.bridge_nodes))):
                bridge = result.bridge_nodes[_]["username"]
                if bridge == target:
                    continue
                try:
                    path = nx.shortest_path(G, target, bridge, weight="weight")
                    result.influence_paths.append(
                        {"from": target, "to": bridge, "path": path}
                    )
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass
        except Exception:
            pass

    # Per-node metrics and role classification
    degree = {n: result.in_degree.get(n, 0) + result.out_degree.get(n, 0) for n in G.nodes()}
    bridge_usernames = {b["username"] for b in result.bridge_nodes}
    for node in G.nodes():
        cid = result.node_community.get(node, 0)
        members = result.communities.get(cid, [])
        internal_degree = sum(
            1 for p in G.predecessors(node) if result.node_community.get(p) == cid
        ) + sum(1 for s in G.successors(node) if result.node_community.get(s) == cid)
        external_degree = degree.get(node, 0) - internal_degree
        connected_communities = (
            set(result.node_community.get(n, -1) for n in G.predecessors(node))
            | set(result.node_community.get(n, -1) for n in G.successors(node))
        )
        connected_communities = [c for c in connected_communities if c >= 0 and c != cid]
        role = "isolate"
        if node in bridge_usernames and len(connected_communities) >= 2:
            role = "bridge"
        elif degree.get(node, 0) <= 0:
            role = "isolate"
        elif internal_degree >= 2 and external_degree <= 1 and len(members) > 1:
            role = "gatekeeper"
        elif result.out_degree.get(node, 0) >= 3 and _rt_ratio_for_user(node, data.interactions) > 0.3:
            role = "amplifier"
        elif degree.get(node, 0) >= 2 and len(members) > 1:
            # Hub: highest degree in community (assign to top degree in each community later)
            role = "hub"
        else:
            role = "peripheral"
        result.node_metrics[node] = {
            "degree": degree.get(node, 0),
            "in_degree": result.in_degree.get(node, 0),
            "out_degree": result.out_degree.get(node, 0),
            "betweenness": round(result.betweenness.get(node, 0), 4),
            "eigenvector": round(result.eigenvector.get(node, 0), 4),
            "community": cid,
            "internal_degree": internal_degree,
            "external_degree": external_degree,
            "role": role,
        }
    # Override hub: highest degree in each community
    for cid, members in result.communities.items():
        if not members:
            continue
        hub_node = max(members, key=lambda n: degree.get(n, 0))
        result.node_metrics[hub_node]["role"] = "hub"
    # Gatekeepers: ensure we didn't mark hubs as gatekeepers
    for node in G.nodes():
        if result.node_metrics.get(node, {}).get("role") == "gatekeeper":
            cid = result.node_community.get(node, 0)
            members = result.communities.get(cid, [])
            hub_node = max(members, key=lambda n: degree.get(n, 0))
            if node == hub_node:
                result.node_metrics[node]["role"] = "hub"

    # Community metrics
    for cid, members in result.communities.items():
        sub = G_undir.subgraph(members) if len(members) > 1 else None
        density = float(nx.density(sub)) if sub and sub.number_of_edges() else 0.0
        hub_node = max(members, key=lambda n: degree.get(n, 0)) if members else None
        bridge_count = sum(1 for b in result.bridge_nodes if b["username"] in members)
        result.community_metrics[cid] = {
            "size": len(members),
            "density": round(density, 4),
            "hub_node": hub_node,
            "bridge_count": bridge_count,
        }

    # Sanity check
    density_global = nx.density(G_undir) if G_undir.number_of_nodes() > 1 else 0.0
    result.sanity_check = {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "n_communities": len(result.communities),
        "density": round(density_global, 4),
        "is_valid": len(result.communities) > 1 and density_global >= 0.01,
    }
    if not result.sanity_check["is_valid"]:
        logger.warning(
            "Graph sanity check: is_valid=False (n_communities=%s, density=%s). Results may be unreliable.",
            result.sanity_check["n_communities"],
            result.sanity_check["density"],
        )

    return result


def network_analysis_to_dict(analysis: NetworkAnalysis) -> dict[str, Any]:
    """Serialize NetworkAnalysis to JSON-serializable dict (no nx graph)."""
    nodes = list(analysis.graph.nodes()) if analysis.graph else []
    edges = []
    if analysis.graph:
        for u, v, d in analysis.graph.edges(data=True):
            edges.append(
                {"source": u, "target": v, "weight": d.get("weight", 1)}
            )
    return {
        "nodes": nodes,
        "edges": edges,
        "communities": analysis.communities,
        "community_metrics": analysis.community_metrics,
        "node_metrics": analysis.node_metrics,
        "node_community": analysis.node_community,
        "bridge_nodes": analysis.bridge_nodes,
        "amplifiers": analysis.amplifiers,
        "gatekeepers": analysis.gatekeepers,
        "vulnerable_entry_points": analysis.vulnerable_entry_points,
        "community_profiles": analysis.community_profiles,
        "influence_paths": analysis.influence_paths,
        "sanity_check": analysis.sanity_check,
        "betweenness": {k: round(v, 4) for k, v in analysis.betweenness.items()},
        "eigenvector": {k: round(v, 4) for k, v in analysis.eigenvector.items()},
        "in_degree": analysis.in_degree,
        "out_degree": analysis.out_degree,
    }
