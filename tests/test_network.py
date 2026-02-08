"""Tests for file-based network analysis (no live scraping)."""

import json
import tempfile
from pathlib import Path

from holespawn.network import NetworkAnalyzer, load_edges_file, load_profiles_from_dir


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
