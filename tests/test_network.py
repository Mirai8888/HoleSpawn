"""Tests for file-based network analysis (no live scraping) and graph-profiling pipeline."""

import json
import tempfile
from pathlib import Path

from holespawn.ingest.network import NetworkData, validate_network_data
from holespawn.network import (
    NetworkAnalyzer,
    build_network_analysis,
    load_edges_file,
    load_profiles_from_dir,
)


def test_load_profiles_from_dir_empty():
    """Empty or missing dir returns empty dict."""
    with tempfile.TemporaryDirectory() as d:
        assert load_profiles_from_dir(d) == {}
        assert load_profiles_from_dir(Path("/nonexistent")) == {}


def test_load_profiles_from_dir():
    """Loads behavioral_matrix.json (or profile.json) from dir; key from parent or stem."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "behavioral_matrix.json").write_text(
            json.dumps({"themes": [], "vocabulary_sample": ["test"], "specific_interests": ["x"]}),
            encoding="utf-8",
        )
        profiles = load_profiles_from_dir(d)
        assert len(profiles) == 1
        assert any("behavioral_matrix" in k or k == Path(d).name for k in profiles)
        assert profiles[list(profiles.keys())[0]]["vocabulary_sample"] == ["test"]


def test_load_edges_csv():
    """Loads edges from CSV with source,target."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("source,target\n")
        f.write("a,b\n")
        f.write("b,c\n")
        f.flush()
        edges = load_edges_file(f.name)
    Path(f.name).unlink(missing_ok=True)
    assert edges == [("a", "b"), ("b", "c")]


def test_load_edges_json():
    """Loads edges from JSON list."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([{"source": "x", "target": "y"}, {"source": "y", "target": "z"}], f)
        f.flush()
        edges = load_edges_file(f.name)
    Path(f.name).unlink(missing_ok=True)
    assert edges == [("x", "y"), ("y", "z")]


def test_analyze_network_no_profiles():
    """Empty profiles returns minimal report."""
    a = NetworkAnalyzer()
    r = a.analyze_network({})
    assert r["stats"]["n_profiles"] == 0
    assert r["clusters"] == []
    assert r["central_accounts"] == []


def test_analyze_network_single_profile():
    """Single profile yields one cluster and one central account."""
    a = NetworkAnalyzer()
    profiles = {"alice": {"vocabulary_sample": ["ai"], "specific_interests": ["ml"], "themes": []}}
    r = a.analyze_network(profiles)
    assert r["stats"]["n_profiles"] == 1
    assert len(r["clusters"]) == 1
    assert r["central_accounts"] == ["alice"] or "alice" in r["central_accounts"]


# ---- Graph profiling (synthetic network, no API calls) ----


def make_synthetic_network() -> NetworkData:
    """
    Build a small synthetic network with 3 clear communities.
    Community A: a1-a5, densely connected
    Community B: b1-b5, densely connected
    Community C: c1-c5, densely connected
    Bridge: a1-b1, b3-c1 (cross-community edges)
    Target: connected to a1, b1, c1
    """
    target = "target_user"
    inner_circle = [f"{c}{i}" for c in "abc" for i in range(1, 6)]
    edges = []
    # Intra-community edges (path + back so each community is a tight cluster, not fully connected)
    for prefix in ("a", "b", "c"):
        members = [f"{prefix}{i}" for i in range(1, 6)]
        for i in range(len(members) - 1):
            m1, m2 = members[i], members[i + 1]
            edges.append({"source": m1, "target": m2, "weight": 2, "edge_types": ["mutual_follow"]})
            edges.append({"source": m2, "target": m1, "weight": 2, "edge_types": ["mutual_follow"]})
    # Bridge edges
    edges.append({"source": "a1", "target": "b1", "weight": 1, "edge_types": ["follow"]})
    edges.append({"source": "b3", "target": "c1", "weight": 1, "edge_types": ["follow"]})
    # Target edges
    for node in ("a1", "b1", "c1"):
        edges.append({"source": target, "target": node, "weight": 1, "edge_types": ["follow"]})
    return NetworkData(
        target_username=target,
        inner_circle=inner_circle,
        all_connections=inner_circle,
        interactions=[],
        edges=edges,
        fetch_stats={"nodes_attempted": 15, "nodes_succeeded": 15, "nodes_failed": 0, "total_fetch_calls": 17},
        following=[],
        followers=[],
        mutuals=[],
        raw_edges=[(e["source"], e["target"]) for e in edges],
    )


def test_validate_real_graph():
    """A network with inter-connection edges should pass validation."""
    data = make_synthetic_network()
    checks = validate_network_data(data)
    assert checks["has_real_graph"] is True
    assert checks["inter_connection_edges"] > 10


def test_validate_star_graph():
    """A star graph (no inter-connection edges) should fail validation."""
    data = NetworkData(
        target_username="target",
        inner_circle=["a", "b", "c", "d", "e"],
        all_connections=["a", "b", "c", "d", "e"],
        interactions=[],
        edges=[
            {"source": "target", "target": n, "weight": 1, "edge_types": ["follow"]}
            for n in ["a", "b", "c", "d", "e"]
        ],
        fetch_stats={"nodes_attempted": 5, "nodes_succeeded": 5, "nodes_failed": 0, "total_fetch_calls": 7},
        following=[],
        followers=[],
        mutuals=[],
        raw_edges=[("target", n) for n in ["a", "b", "c", "d", "e"]],
    )
    checks = validate_network_data(data)
    assert checks["has_real_graph"] is False


def test_community_detection():
    """Graph analysis runs; Louvain finds communities (synthetic graph may yield 1–3)."""
    data = make_synthetic_network()
    analysis = build_network_analysis(data)
    assert analysis.sanity_check["n_nodes"] == 16  # target + 15 inner_circle
    assert analysis.sanity_check["n_communities"] >= 1
    assert len(analysis.communities) == analysis.sanity_check["n_communities"]
    assert len(analysis.bridge_nodes) >= 1  # a1 or b3 should be detected as bridges


def test_bridge_detection():
    """Nodes connecting communities should have high betweenness."""
    data = make_synthetic_network()
    analysis = build_network_analysis(data)
    bridge_usernames = [b["username"] for b in analysis.bridge_nodes]
    # a1 connects A-B, b3 connects B-C — at least one should be flagged
    assert any(u in bridge_usernames for u in ["a1", "b1", "b3", "c1"])
