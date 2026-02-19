#!/usr/bin/env python3
"""Run HoleSpawn network engine against Mirai community data."""

import json
import sys
import os

sys.path.insert(0, os.path.expanduser("~/HoleSpawn"))

from holespawn.network.graph_builder import build_graph
from holespawn.network.influence_flow import analyze_influence_flow
from holespawn.network.vulnerability import analyze_vulnerability

DATA_DIR = os.path.expanduser("~/seithar-research/data")
OUT_DIR = os.path.expanduser("~/HoleSpawn/data/network-intel-2026-02-19")

# Load data
print("[+] Loading data...")
with open(f"{DATA_DIR}/mirai-community-edges.json") as f:
    edge_map = json.load(f)

with open(f"{DATA_DIR}/mirai-community-analysis.json") as f:
    analysis = json.load(f)

print(f"    Edge map: {len(edge_map)} nodes")
print(f"    Analysis: {analysis['graph']}")

# Build graph from edge map
print("[+] Building directed graph...")
spec = build_graph(edge_map=edge_map)
G = spec.graph
print(f"    Graph: {spec.node_count} nodes, {spec.edge_count} edges")
print(f"    Edge types: {spec.edge_type_counts}")

# Enrich with pre-computed metrics as node attributes
for node in G.nodes():
    node_l = node.lower()
    if node_l in analysis.get("pagerank", {}):
        G.nodes[node]["pagerank"] = analysis["pagerank"][node_l]
    elif node in analysis.get("pagerank", {}):
        G.nodes[node]["pagerank"] = analysis["pagerank"][node]
    if node_l in analysis.get("betweenness", {}):
        G.nodes[node]["betweenness"] = analysis["betweenness"][node_l]
    elif node in analysis.get("betweenness", {}):
        G.nodes[node]["betweenness"] = analysis["betweenness"][node]
    if node_l in analysis.get("partition", {}):
        G.nodes[node]["community"] = analysis["partition"][node_l]
    elif node in analysis.get("partition", {}):
        G.nodes[node]["community"] = analysis["partition"][node]

# Run influence analysis
print("[+] Running influence flow analysis...")
influence = analyze_influence_flow(G)
influence_dict = influence.to_dict()
print(f"    Seeds: {len(influence.seeds)}")
print(f"    Bridges: {len(influence.bridge_nodes)}")
print(f"    Chains: {len(influence.amplification_chains)}")

# Run vulnerability analysis
print("[+] Running vulnerability analysis...")
vuln = analyze_vulnerability(G, target_fragmentation=0.5)
vuln_dict = vuln.to_dict()
print(f"    Fragmentation results: {len(vuln.fragmentation)}")
print(f"    SPOFs: {len(vuln.single_points_of_failure)}")
print(f"    Community cohesion: {len(vuln.community_cohesion)}")
print(f"    Attack surface steps: {len(vuln.attack_surfaces)}")

# Save results
print("[+] Saving results...")

# Influence report
with open(f"{OUT_DIR}/influence_report.json", "w") as f:
    json.dump(influence_dict, f, indent=2, default=str)

# Vulnerability report
with open(f"{OUT_DIR}/vulnerability_report.json", "w") as f:
    json.dump(vuln_dict, f, indent=2, default=str)

# Bridge analysis (extracted)
bridge_data = {
    "bridge_nodes": influence.bridge_nodes[:50],
    "community_count": len(set(b.get("own_community", -1) for b in influence.bridge_nodes)),
    "top_bridges_detail": []
}
for b in influence.bridge_nodes[:20]:
    node = b["node"]
    bridge_data["top_bridges_detail"].append({
        **b,
        "influence_score": influence.influence_scores.get(node, 0),
        "influence_breakdown": influence.influence_breakdown.get(node, {}),
        "pagerank": analysis.get("pagerank", {}).get(node, analysis.get("pagerank", {}).get(node.lower(), 0)),
    })
with open(f"{OUT_DIR}/bridge_analysis.json", "w") as f:
    json.dump(bridge_data, f, indent=2, default=str)

# Prepare intel brief data
top_influence = sorted(influence.influence_scores.items(), key=lambda x: x[1], reverse=True)[:10]
top_bridges = sorted(influence.bridge_nodes, key=lambda b: (b["num_communities"], b["betweenness"]), reverse=True)[:5]
top_frag = vuln.fragmentation[:3]
attack = vuln.attack_surfaces[:5]

# Community structure from pre-computed
communities = analysis.get("communities", {})

print("\n[+] TOP 10 INFLUENCE NODES:")
for node, score in top_influence:
    bd = influence.influence_breakdown.get(node, {})
    print(f"    {node}: {score:.4f} (seed={bd.get('seeding',0):.3f} amp={bd.get('amplification',0):.3f} bridge={bd.get('bridging',0):.3f} reach={bd.get('reach',0):.3f})")

print("\n[+] TOP 5 BRIDGES:")
for b in top_bridges:
    print(f"    {b['node']}: communities={b['communities_connected']} betweenness={b['betweenness']:.4f}")

print("\n[+] TOP 3 FRAGMENTATION NODES:")
for fr in top_frag:
    print(f"    {fr.node}: frag_ratio={fr.fragmentation_ratio:.4f} components={fr.components_after}")

print("\n[+] ATTACK SURFACE:")
for a in attack:
    print(f"    Step {a['step']}: remove {a['node_removed']} -> {a['components_after']} components, cumulative_frag={a['cumulative_fragmentation']:.4f}")

# Save summary data for brief generation
summary = {
    "top_influence": [(n, s, influence.influence_breakdown.get(n, {})) for n, s in top_influence],
    "top_bridges": top_bridges,
    "top_fragmentation": [f.to_dict() for f in top_frag],
    "attack_surface": attack,
    "communities": {cid: {"size": c["size"], "members_sample": c["members"][:10]} for cid, c in communities.items()},
    "community_cohesion": [c.to_dict() for c in vuln.community_cohesion],
    "spofs": [s for s in vuln.single_points_of_failure[:10]],
    "graph_stats": {"nodes": spec.node_count, "edges": spec.edge_count},
}
with open(f"{OUT_DIR}/summary_data.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)

print("\n[+] Done. Results saved to", OUT_DIR)
