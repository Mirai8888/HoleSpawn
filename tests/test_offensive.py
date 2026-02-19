"""Tests for holespawn.network.offensive — cognitive kill chain operations."""

import pytest
import networkx as nx

from holespawn.network.offensive import (
    narrative_injection_planner,
    amplification_strategy,
    community_fracture_planner,
    bridge_capture_assessment,
    counter_narrative_mapper,
    operation_simulator,
    InjectionCandidate,
    AmplificationSchedule,
    FracturePlan,
    BridgeCaptureReport,
    CounterNarrativeMap,
    SimulationTimeline,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _build_test_graph() -> nx.DiGraph:
    """
    Build a test graph with two clear communities and a bridge node.

    Community 0: a, b, c, d (dense)
    Community 1: e, f, g, h (dense)
    Bridge: x connects both
    """
    G = nx.DiGraph()

    # Community 0
    for u, v in [("a", "b"), ("b", "a"), ("a", "c"), ("c", "a"),
                 ("b", "c"), ("c", "b"), ("a", "d"), ("d", "a"),
                 ("b", "d"), ("d", "b"), ("c", "d"), ("d", "c")]:
        G.add_edge(u, v, weight=3.0, edge_type="reply")

    # Community 1
    for u, v in [("e", "f"), ("f", "e"), ("e", "g"), ("g", "e"),
                 ("f", "g"), ("g", "f"), ("e", "h"), ("h", "e"),
                 ("f", "h"), ("h", "f"), ("g", "h"), ("h", "g")]:
        G.add_edge(u, v, weight=3.0, edge_type="reply")

    # Bridge node x
    G.add_edge("x", "a", weight=2.0, edge_type="retweet")
    G.add_edge("a", "x", weight=2.0, edge_type="retweet")
    G.add_edge("x", "e", weight=2.0, edge_type="retweet")
    G.add_edge("e", "x", weight=2.0, edge_type="retweet")
    G.add_edge("x", "b", weight=1.0, edge_type="follow")

    # Add some topic data
    G.nodes["a"]["topics"] = [("crypto", 5), ("defi", 3)]
    G.nodes["b"]["topics"] = [("crypto", 4), ("nft", 2)]
    G.nodes["e"]["topics"] = [("politics", 5), ("media", 3)]
    G.nodes["f"]["topics"] = [("politics", 4), ("censorship", 2)]
    G.nodes["x"]["topics"] = [("crypto", 2), ("politics", 2)]

    return G


@pytest.fixture
def test_graph():
    return _build_test_graph()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNarrativeInjectionPlanner:
    def test_returns_candidates(self, test_graph):
        results = narrative_injection_planner(test_graph, 0, "crypto defi blockchain")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, InjectionCandidate) for r in results)

    def test_candidates_are_ranked(self, test_graph):
        results = narrative_injection_planner(test_graph, 0, "crypto defi")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_to_dict(self, test_graph):
        results = narrative_injection_planner(test_graph, 0, "crypto defi")
        if results:
            d = results[0].to_dict()
            assert "node" in d
            assert "score" in d
            assert "bridge_reach" in d

    def test_empty_community(self, test_graph):
        results = narrative_injection_planner(test_graph, 999, "anything")
        assert results == []


class TestAmplificationStrategy:
    def test_returns_schedule(self, test_graph):
        result = amplification_strategy(test_graph, ["a"], target_reach_pct=0.3)
        assert isinstance(result, AmplificationSchedule)
        assert isinstance(result.to_dict(), dict)

    def test_reach_increases(self, test_graph):
        result = amplification_strategy(test_graph, ["a"], target_reach_pct=0.5)
        if result.steps:
            reaches = [s["cumulative_reach"] for s in result.steps]
            assert reaches == sorted(reaches)  # monotonically increasing

    def test_with_target_community(self, test_graph):
        result = amplification_strategy(test_graph, ["a"], target_reach_pct=0.5, target_community=0)
        assert isinstance(result, AmplificationSchedule)


class TestCommunityFracturePlanner:
    def test_returns_plan(self, test_graph):
        result = community_fracture_planner(test_graph, 0)
        assert isinstance(result, FracturePlan)
        assert isinstance(result.to_dict(), dict)

    def test_finds_subgroups(self, test_graph):
        result = community_fracture_planner(test_graph, 0)
        assert len(result.subgroups) >= 1

    def test_small_community(self):
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=1.0)
        result = community_fracture_planner(G, 0)
        assert result.estimated_cohesion_impact == 0.0


class TestBridgeCaptureAssessment:
    def test_returns_report(self, test_graph):
        result = bridge_capture_assessment(test_graph, "x")
        assert isinstance(result, BridgeCaptureReport)
        assert result.bridge_node == "x"
        assert result.resistance >= 0
        assert result.estimated_effort in ("low", "medium", "high")

    def test_to_dict(self, test_graph):
        result = bridge_capture_assessment(test_graph, "x")
        d = result.to_dict()
        assert "resistance" in d
        assert "downstream_communities" in d

    def test_invalid_node(self, test_graph):
        with pytest.raises(ValueError):
            bridge_capture_assessment(test_graph, "nonexistent")


class TestCounterNarrativeMapper:
    def test_with_explicit_infected(self, test_graph):
        result = counter_narrative_mapper(test_graph, "crypto defi", infected_nodes=["a", "b"])
        assert isinstance(result, CounterNarrativeMap)
        assert len(result.infected_nodes) == 2

    def test_auto_detect_infected(self, test_graph):
        result = counter_narrative_mapper(test_graph, "crypto defi")
        assert isinstance(result, CounterNarrativeMap)
        assert result.spread_pct >= 0

    def test_to_dict(self, test_graph):
        result = counter_narrative_mapper(test_graph, "crypto", infected_nodes=["a"])
        d = result.to_dict()
        assert "containment_points" in d
        assert "minimum_deployment" in d

    def test_no_infection(self, test_graph):
        result = counter_narrative_mapper(test_graph, "xyznonexistent123456")
        assert result.spread_pct == 0.0


class TestOperationSimulator:
    def test_independent_cascade(self, test_graph):
        plan = {"seed_nodes": ["a"], "type": "injection"}
        result = operation_simulator(test_graph, plan, steps=5, seed=42)
        assert isinstance(result, SimulationTimeline)
        assert len(result.steps) > 0
        assert result.final_reach_pct > 0

    def test_linear_threshold(self, test_graph):
        plan = {"seed_nodes": ["a", "b"], "type": "injection"}
        result = operation_simulator(test_graph, plan, steps=5, model="linear_threshold", seed=42)
        assert isinstance(result, SimulationTimeline)

    def test_deterministic_with_seed(self, test_graph):
        plan = {"seed_nodes": ["a"], "type": "injection"}
        r1 = operation_simulator(test_graph, plan, steps=5, seed=123)
        r2 = operation_simulator(test_graph, plan, steps=5, seed=123)
        assert r1.final_reach_pct == r2.final_reach_pct

    def test_community_states_tracked(self, test_graph):
        plan = {"seed_nodes": ["a"], "type": "injection"}
        result = operation_simulator(test_graph, plan, steps=10, seed=42)
        assert len(result.community_states) > 0

    def test_to_dict(self, test_graph):
        plan = {"seed_nodes": ["a"], "type": "injection"}
        result = operation_simulator(test_graph, plan, steps=3, seed=42)
        d = result.to_dict()
        assert "steps" in d
        assert "final_reach_pct" in d
        assert "community_states" in d

    def test_empty_seeds(self, test_graph):
        plan = {"seed_nodes": [], "type": "injection"}
        result = operation_simulator(test_graph, plan, steps=3, seed=42)
        assert result.final_reach_pct == 0.0
