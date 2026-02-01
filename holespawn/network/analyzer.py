"""
Network analysis: community detection and structural centrality.
Input: file-based (directory of behavioral_matrix.json or profile.json) + optional edges CSV/JSON;
  or profiles from paid APIs (e.g. fetch_profiles_via_apify). Use only data you are authorized to use.
"""

import json
import re
from pathlib import Path
from typing import Any, Optional

try:
    import networkx as nx
    from networkx.algorithms.centrality import degree_centrality, betweenness_centrality
    try:
        from networkx.algorithms.community import greedy_modularity_communities
    except ImportError:
        from networkx.algorithms.community.modularity_max import greedy_modularity_communities
    try:
        from networkx.algorithms.community import label_propagation_communities
    except ImportError:
        from networkx.algorithms.community.label_propagation import label_propagation_communities
except ImportError:
    nx = None
    degree_centrality = None
    betweenness_centrality = None
    greedy_modularity_communities = None
    label_propagation_communities = None


def load_profiles_from_dir(
    dir_path: str | Path,
    pattern: str = "**/behavioral_matrix.json",
    fallback_pattern: str = "**/profile.json",
) -> dict[str, dict[str, Any]]:
    """
    Load profile-like dicts from a directory. Keys = filename stem (e.g. username).
    Expects behavioral_matrix.json or profile.json per account (from HoleSpawn output).
    """
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        return {}
    profiles = {}
    for path in dir_path.glob(pattern):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            stem = path.stem.replace("behavioral_matrix", "").replace("profile", "").strip("_")
            key = stem or path.parent.name
            if not key:
                key = path.parent.name
            profiles[key] = data
        except (json.JSONDecodeError, OSError):
            continue
    if not profiles and fallback_pattern:
        for path in dir_path.glob(fallback_pattern):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                stem = path.stem.replace("profile", "").strip("_")
                key = stem or path.parent.name
                if not key:
                    key = path.parent.name
                profiles[key] = data
            except (json.JSONDecodeError, OSError):
                continue
    return profiles


def load_edges_file(
    path: str | Path,
    source_col: str = "source",
    target_col: str = "target",
) -> list[tuple[str, str]]:
    """
    Load edges (e.g. follow graph) from CSV or JSON. Returns list of (source_id, target_id).
    CSV: must have header with source_col, target_col (or 'source','target').
    JSON: list of {"source": "...", "target": "..."} or {"from": "...", "to": "..."}.
    """
    path = Path(path)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").strip()
    edges = []
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for row in data:
                    a = row.get(source_col) or row.get("from") or row.get("source")
                    b = row.get(target_col) or row.get("to") or row.get("target")
                    if a and b:
                        edges.append((str(a).strip(), str(b).strip()))
            elif isinstance(data, dict) and "edges" in data:
                for row in data["edges"]:
                    a = row.get(source_col) or row.get("from") or row.get("source")
                    b = row.get(target_col) or row.get("to") or row.get("target")
                    if a and b:
                        edges.append((str(a).strip(), str(b).strip()))
        except json.JSONDecodeError:
            return []
        return edges
    # CSV
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    header = [c.strip().lower() for c in lines[0].split(",")]
    try:
        si = header.index(source_col.lower())
        ti = header.index(target_col.lower())
    except ValueError:
        for i, h in enumerate(header):
            if h in ("source", "from", "src"):
                si = i
                break
        else:
            si = 0
        for i, h in enumerate(header):
            if h in ("target", "to", "dst"):
                ti = i
                break
        else:
            ti = 1 if len(header) > 1 else 0
    for line in lines[1:]:
        parts = [p.strip() for p in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", line) if p.strip()]
        if len(parts) > max(si, ti):
            edges.append((parts[si].strip('"'), parts[ti].strip('"')))
    return edges


def _profile_vector(profile: dict[str, Any]) -> set[str]:
    """Set of tokens for similarity (vocabulary + themes + interests)."""
    tokens = set()
    for key in ("vocabulary_sample", "specific_interests", "obsessions", "cultural_references", "sample_phrases"):
        val = profile.get(key)
        if isinstance(val, list):
            for v in val[:50]:
                if isinstance(v, str):
                    tokens.update(re.findall(r"\b\w+\b", v.lower()))
    for key in ("themes",):
        val = profile.get(key)
        if isinstance(val, list):
            for v in val[:30]:
                if isinstance(v, (list, tuple)) and v:
                    w = v[0] if isinstance(v[0], str) else str(v[0])
                    tokens.update(re.findall(r"\b\w+\b", w.lower()))
                elif isinstance(v, str):
                    tokens.update(re.findall(r"\b\w+\b", v.lower()))
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b) if (a | b) else 0.0


class NetworkAnalyzer:
    """
    Analyze networks from file-based profiles and optional edges.
    No live scraping. Use only data you own or have permission to analyze.
    """

    def __init__(self, similarity_threshold: float = 0.12):
        self.similarity_threshold = similarity_threshold

    def analyze_network(
        self,
        profiles: dict[str, dict[str, Any]],
        edges: Optional[list[tuple[str, str]]] = None,
        use_community_detection: bool = True,
    ) -> dict[str, Any]:
        """
        Run community detection and structural centrality.
        profiles: account_id -> profile dict (from load_profiles_from_dir).
        edges: optional list of (source_id, target_id) for follow/interaction graph.
        Returns report dict: clusters, central_accounts, influence_graph (if edges), stats.
        """
        if not profiles:
            return {"clusters": [], "central_accounts": [], "influence_graph": None, "stats": {"n_profiles": 0}}

        report: dict[str, Any] = {"clusters": [], "central_accounts": [], "influence_graph": None, "stats": {}}
        report["stats"]["n_profiles"] = len(profiles)
        ids = list(profiles.keys())

        if nx is None or greedy_modularity_communities is None:
            report["clusters"] = [ids]
            report["central_accounts"] = ids[:5]
            report["stats"]["warning"] = "networkx not installed; install with: pip install networkx"
            return report

        # Build graph: from edges if provided, else from profile similarity
        G = nx.DiGraph() if edges else nx.Graph()
        G.add_nodes_from(ids)

        if edges:
            for a, b in edges:
                G.add_edge(a, b)
            G.add_nodes_from(ids)
            # For community detection we need undirected
            G_undir = G.to_undirected() if G.is_directed() else G
        else:
            # Similarity graph from profiles
            vecs = {i: _profile_vector(profiles[i]) for i in ids}
            for i in ids:
                for j in ids:
                    if i >= j:
                        continue
                    sim = _jaccard(vecs[i], vecs[j])
                    if sim >= self.similarity_threshold:
                        G.add_edge(i, j)
            G_undir = G

        report["stats"]["n_edges"] = G.number_of_edges()

        # Community detection on undirected graph
        if use_community_detection and G_undir.number_of_edges() > 0:
            try:
                communities = greedy_modularity_communities(G_undir)
                report["clusters"] = [list(c) for c in communities]
            except Exception:
                try:
                    communities = list(label_propagation_communities(G_undir))
                    report["clusters"] = [list(c) for c in communities]
                except Exception:
                    report["clusters"] = [ids]
        else:
            if G_undir.number_of_edges() == 0:
                report["clusters"] = [[i] for i in ids]
            else:
                report["clusters"] = [list(c) for c in nx.connected_components(G_undir)]

        # Centrality (use directed graph if we have edges, else undirected)
        try:
            deg = degree_centrality(G)
            sorted_deg = sorted(deg.items(), key=lambda x: -x[1])
            report["central_accounts"] = [n for n, _ in sorted_deg[: min(20, len(ids))]]
            if edges and G.is_directed() and G.number_of_edges() > 0:
                try:
                    bet = betweenness_centrality(G)
                    report["betweenness_centrality"] = {k: round(v, 4) for k, v in sorted(bet.items(), key=lambda x: -x[1])[:20]}
                except Exception:
                    pass
        except Exception:
            report["central_accounts"] = ids[:10]

        if edges:
            report["influence_graph"] = {
                "nodes": list(G.nodes()),
                "edge_count": G.number_of_edges(),
            }

        return report
