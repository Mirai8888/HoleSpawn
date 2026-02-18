"""
Tests for holespawn.network analytical engine modules:
graph_builder, influence_flow, vulnerability, temporal, content_overlay.
"""

from datetime import datetime, timezone

import networkx as nx
import pytest

from holespawn.network.content_overlay import (
    analyze_content_overlay,
    analyze_sentiment_flow,
    build_node_topic_profiles,
    cluster_by_beliefs,
)
from holespawn.network.graph_builder import GraphSpec, build_graph, filter_graph_by_time
from holespawn.network.influence_flow import (
    InfluenceReport,
    analyze_bridges,
    analyze_influence_flow,
    compute_influence_scores,
    detect_narrative_seeds,
)
from holespawn.network.temporal import (
    analyze_temporal,
    compare_snapshots,
    detect_trends,
    track_community_evolution,
)
from holespawn.network.vulnerability import (
    analyze_fragmentation,
    analyze_vulnerability,
    compute_community_cohesion,
    find_single_points_of_failure,
    map_attack_surface,
)

# --- Fixtures ---

def _make_tweets():
    """Sample tweets mimicking scraper parser output."""
    return [
        {"author": "alice", "text": "Breaking: new policy announced #policy",
         "full_text": "Breaking: new policy announced #policy",
         "created_at": "Mon Feb 10 12:00:00 +0000 2025",
         "is_retweet": False, "is_quote": False, "in_reply_to": None,
         "hashtags": ["policy"], "quoted_user": None},
        {"author": "bob", "text": "RT @alice: Breaking: new policy announced #policy",
         "full_text": "RT @alice: Breaking: new policy announced #policy",
         "created_at": "Mon Feb 10 13:00:00 +0000 2025",
         "is_retweet": True, "is_quote": False, "in_reply_to": None,
         "hashtags": ["policy"], "quoted_user": None},
        {"author": "carol", "text": "Interesting take from alice",
         "full_text": "Interesting take from alice",
         "created_at": "Mon Feb 10 14:00:00 +0000 2025",
         "is_retweet": False, "is_quote": True, "in_reply_to": None,
         "hashtags": [], "quoted_user": "alice"},
        {"author": "dave", "text": "@bob I disagree with this",
         "full_text": "@bob I disagree with this",
         "created_at": "Mon Feb 10 15:00:00 +0000 2025",
         "is_retweet": False, "is_quote": False, "in_reply_to": "bob",
         "hashtags": [], "quoted_user": None},
        {"author": "eve", "text": "RT @alice: Breaking: new policy announced #policy",
         "full_text": "RT @alice: Breaking: new policy announced #policy",
         "created_at": "Mon Feb 10 16:00:00 +0000 2025",
         "is_retweet": True, "is_quote": False, "in_reply_to": None,
         "hashtags": ["policy"], "quoted_user": None},
        {"author": "frank", "text": "Crypto is the future #crypto #bitcoin",
         "full_text": "Crypto is the future #crypto #bitcoin",
         "created_at": "Mon Feb 10 17:00:00 +0000 2025",
         "is_retweet": False, "is_quote": False, "in_reply_to": None,
         "hashtags": ["crypto", "bitcoin"], "quoted_user": None},
    ]


def _make_edge_map():
    """Community edges: who follows whom."""
    return {
        "alice": ["bob", "carol"],
        "bob": ["alice", "dave"],
        "carol": ["alice", "eve"],
        "dave": ["bob", "frank"],
        "eve": ["carol", "frank"],
        "frank": ["dave", "eve"],
    }


def _build_test_graph():
    """Build graph from test data."""
    spec = build_graph(tweets=_make_tweets(), edge_map=_make_edge_map())
    return spec.graph


# --- graph_builder tests ---

class TestGraphBuilder:
    def test_build_from_tweets(self):
        spec = build_graph(tweets=_make_tweets())
        assert isinstance(spec, GraphSpec)
        assert spec.node_count > 0
        assert spec.edge_count > 0
        assert "retweet" in spec.edge_type_counts

    def test_build_from_edge_map(self):
        spec = build_graph(edge_map=_make_edge_map())
        assert spec.node_count == 6
        assert "follow" in spec.edge_type_counts

    def test_combined_build(self):
        spec = build_graph(tweets=_make_tweets(), edge_map=_make_edge_map())
        assert spec.node_count >= 6
        # Should have both follow and interaction edges
        assert spec.edge_type_counts.get("follow", 0) > 0

    def test_temporal_edges(self):
        spec = build_graph(tweets=_make_tweets())
        G = spec.graph
        # Check that at least some edges have timestamps
        has_ts = any("timestamps" in d for _, _, d in G.edges(data=True))
        assert has_ts

    def test_filter_by_time(self):
        spec = build_graph(tweets=_make_tweets())
        G = spec.graph
        cutoff = datetime(2025, 2, 10, 14, 0, 0, tzinfo=timezone.utc)
        H = filter_graph_by_time(G, end=cutoff)
        # Should have fewer or equal edges
        assert H.number_of_edges() <= G.number_of_edges()

    def test_to_dict(self):
        spec = build_graph(tweets=_make_tweets())
        d = spec.to_dict()
        assert "node_count" in d
        assert "edge_type_counts" in d

    def test_custom_weights(self):
        spec = build_graph(tweets=_make_tweets(), custom_weights={"retweet": 10.0})
        G = spec.graph
        # RT edges should have weight 10
        for _u, _v, data in G.edges(data=True):
            if "retweet" in data.get("types", set()):
                assert data["weight"] >= 10.0


# --- influence_flow tests ---

class TestInfluenceFlow:
    def test_detect_seeds(self):
        G = _build_test_graph()
        seeds = detect_narrative_seeds(G)
        assert len(seeds) > 0
        # Alice should be top seed (gets RT'd by bob and eve, QT'd by carol)
        seed_users = [s.user for s in seeds]
        assert "alice" in seed_users

    def test_bridges(self):
        G = _build_test_graph()
        bridges = analyze_bridges(G)
        assert isinstance(bridges, list)
        # All entries have required fields
        for b in bridges:
            assert "node" in b
            assert "betweenness" in b

    def test_influence_scores(self):
        G = _build_test_graph()
        scores, breakdown = compute_influence_scores(G)
        assert len(scores) > 0
        assert all(0 <= v <= 1 for v in scores.values())
        # Alice should have high score (top seeder)
        assert scores.get("alice", 0) > 0

    def test_full_analysis(self):
        G = _build_test_graph()
        report = analyze_influence_flow(G)
        assert isinstance(report, InfluenceReport)
        d = report.to_dict()
        assert "seeds" in d
        assert "influence_scores" in d

    def test_empty_graph(self):
        G = nx.DiGraph()
        report = analyze_influence_flow(G)
        assert report.seeds == []
        assert report.influence_scores == {}


# --- vulnerability tests ---

class TestVulnerability:
    def test_fragmentation(self):
        G = _build_test_graph()
        results = analyze_fragmentation(G)
        assert isinstance(results, list)
        for r in results:
            assert 0 <= r.fragmentation_ratio <= 1

    def test_single_points_of_failure(self):
        G = _build_test_graph()
        spofs = find_single_points_of_failure(G)
        assert isinstance(spofs, list)
        for s in spofs:
            assert "node" in s
            assert s["type"] == "articulation_point"

    def test_community_cohesion(self):
        G = _build_test_graph()
        scores = compute_community_cohesion(G)
        assert isinstance(scores, list)
        for s in scores:
            assert 0 <= s.cohesion <= 1

    def test_attack_surface(self):
        G = _build_test_graph()
        surface = map_attack_surface(G, target_fragmentation=0.5)
        assert isinstance(surface, list)
        if surface:
            assert surface[0]["step"] == 1

    def test_full_vulnerability(self):
        G = _build_test_graph()
        report = analyze_vulnerability(G)
        d = report.to_dict()
        assert "fragmentation" in d
        assert "attack_surfaces" in d

    def test_small_graph(self):
        G = nx.DiGraph()
        G.add_edge("a", "b")
        report = analyze_vulnerability(G)
        assert report.fragmentation == []


# --- temporal tests ---

class TestTemporal:
    def _two_snapshots(self):
        G1 = nx.DiGraph()
        G1.add_weighted_edges_from([("a", "b", 1), ("b", "c", 2), ("c", "a", 1)])

        G2 = nx.DiGraph()
        G2.add_weighted_edges_from([("a", "b", 3), ("b", "c", 2), ("c", "d", 1), ("d", "a", 1)])
        return G1, G2

    def test_snapshot_diff(self):
        G1, G2 = self._two_snapshots()
        diff = compare_snapshots(G1, G2)
        assert "d" in diff.nodes_added
        assert ("c", "a") in diff.edges_removed
        assert ("c", "d") in diff.edges_added
        assert diff.node_count_change == 1

    def test_community_evolution(self):
        G1, G2 = self._two_snapshots()
        evo = track_community_evolution(G1, G2)
        assert isinstance(evo.to_dict(), dict)

    def test_trends(self):
        G1, G2 = self._two_snapshots()
        trends = detect_trends(G1, G2)
        assert len(trends.emerging_edges) > 0
        assert any(e["target"] == "d" for e in trends.emerging_edges)

    def test_full_temporal(self):
        G1, G2 = self._two_snapshots()
        report = analyze_temporal(G1, G2)
        d = report.to_dict()
        assert d["snapshot_diff"] is not None
        assert d["trends"] is not None


# --- content_overlay tests ---

class TestContentOverlay:
    def test_node_topic_profiles(self):
        tweets = _make_tweets()
        profiles = build_node_topic_profiles(tweets)
        assert "alice" in profiles
        assert profiles["alice"].tweet_count == 1
        assert len(profiles["alice"].hashtags) > 0

    def test_belief_clustering(self):
        # Need more tweets with shared topics for clustering
        tweets = _make_tweets()
        profiles = build_node_topic_profiles(tweets)
        clusters = cluster_by_beliefs(profiles, min_shared_topics=1)
        assert isinstance(clusters, list)

    def test_sentiment_flow(self):
        G = _build_test_graph()
        tweets = _make_tweets()
        profiles = build_node_topic_profiles(tweets, set(G.nodes()))
        result = analyze_sentiment_flow(G, profiles)
        assert "edges_analyzed" in result

    def test_full_content_overlay(self):
        G = _build_test_graph()
        tweets = _make_tweets()
        report = analyze_content_overlay(G, tweets)
        d = report.to_dict()
        assert "node_profiles" in d
        assert "sentiment_flow" in d

    def test_empty_tweets(self):
        G = _build_test_graph()
        report = analyze_content_overlay(G, [])
        assert report.node_profiles == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
