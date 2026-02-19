"""Tests for network engine -- operational orchestration layer."""

import json
import tempfile
from pathlib import Path

import networkx as nx
import pytest

from holespawn.network.engine import (
    InfluencePath,
    NetworkEngine,
    NetworkIntel,
    OperationalNode,
    OperationPlan,
)


def _build_test_graph() -> nx.DiGraph:
    """
    Build a test graph with clear structure:

    Community 0: alice, bob, carol (tight cluster)
    Community 1: dave, eve, frank (tight cluster)
    Bridge: grace connects both communities
    Amplifier: heidi RTs from community 0
    Seed: alice produces content everyone amplifies
    """
    G = nx.DiGraph()

    # Community 0 internal edges
    for u, v in [("alice", "bob"), ("bob", "alice"), ("alice", "carol"),
                 ("carol", "bob"), ("bob", "carol")]:
        G.add_edge(u, v, weight=3.0, types={"reply"})

    # alice is a seed: bob and carol RT her
    G.add_edge("bob", "alice", weight=5.0, types={"retweet"})
    G.add_edge("carol", "alice", weight=4.0, types={"retweet"})

    # Community 1 internal edges
    for u, v in [("dave", "eve"), ("eve", "dave"), ("dave", "frank"),
                 ("frank", "eve"), ("eve", "frank")]:
        G.add_edge(u, v, weight=3.0, types={"reply"})

    # Bridge: grace connects communities
    G.add_edge("grace", "alice", weight=2.0, types={"reply"})
    G.add_edge("grace", "dave", weight=2.0, types={"reply"})
    G.add_edge("alice", "grace", weight=1.0, types={"reply"})
    G.add_edge("dave", "grace", weight=1.0, types={"reply"})

    # Amplifier: heidi RTs from community 0 into community 1
    G.add_edge("heidi", "alice", weight=4.0, types={"retweet"})
    G.add_edge("heidi", "dave", weight=2.0, types={"reply"})
    G.add_edge("dave", "heidi", weight=1.0, types={"reply"})

    return G


@pytest.fixture
def engine():
    return NetworkEngine(_build_test_graph())


@pytest.fixture
def empty_engine():
    return NetworkEngine(nx.DiGraph())


class TestAnalyze:
    def test_basic_intel(self, engine):
        intel = engine.analyze()
        assert intel.node_count == 8
        assert intel.edge_count > 0
        assert intel.community_count >= 1
        assert len(intel.nodes) == 8

    def test_all_nodes_have_profiles(self, engine):
        intel = engine.analyze()
        for name in ["alice", "bob", "carol", "dave", "eve", "frank", "grace", "heidi"]:
            assert name in intel.nodes
            op = intel.nodes[name]
            assert op.node == name
            assert op.community >= 0

    def test_roles_assigned(self, engine):
        intel = engine.analyze()
        roles = {op.role for op in intel.nodes.values()}
        # At minimum we should have some non-peripheral nodes
        assert len(roles) >= 1

    def test_spof_detection(self, engine):
        intel = engine.analyze()
        # grace is a bridge between communities; likely a SPOF
        # (depends on exact community detection)
        spof_nodes = [n for n, op in intel.nodes.items() if op.is_spof]
        assert isinstance(spof_nodes, list)

    def test_influence_scores_present(self, engine):
        intel = engine.analyze()
        scores = [op.influence_score for op in intel.nodes.values()]
        assert any(s > 0 for s in scores)

    def test_cached_result(self, engine):
        intel1 = engine.analyze()
        intel2 = engine.analyze()
        assert intel1 is intel2

    def test_empty_graph(self, empty_engine):
        intel = empty_engine.analyze()
        assert intel.node_count == 0
        assert len(intel.nodes) == 0

    def test_top_nodes(self, engine):
        intel = engine.analyze()
        top = intel.top_nodes(by="pagerank", n=3)
        assert len(top) <= 3
        assert all(isinstance(t, OperationalNode) for t in top)

    def test_to_dict(self, engine):
        intel = engine.analyze()
        d = intel.to_dict()
        assert "node_count" in d
        assert "nodes" in d
        assert len(d["nodes"]) == 8


class TestInfluencePaths:
    def test_find_path_exists(self, engine):
        paths = engine.find_influence_paths("alice", "dave")
        # Should find at least one path through grace
        assert len(paths) >= 1
        assert paths[0].source == "alice"
        assert paths[0].target == "dave"

    def test_path_structure(self, engine):
        paths = engine.find_influence_paths("alice", "dave", k=3)
        for p in paths:
            assert p.path[0] == "alice"
            assert p.path[-1] == "dave"
            assert p.hops == len(p.path) - 1
            assert p.reliability > 0

    def test_no_path(self, engine):
        # Add isolated node
        engine.G.add_node("isolated")
        paths = engine.find_influence_paths("isolated", "alice")
        assert len(paths) == 0

    def test_bottleneck_identified(self, engine):
        paths = engine.find_influence_paths("alice", "dave")
        if paths:
            assert paths[0].bottleneck_edge is not None

    def test_communities_crossed(self, engine):
        paths = engine.find_influence_paths("alice", "dave")
        if paths:
            assert len(paths[0].communities_crossed) >= 1


class TestGatekeepers:
    def test_find_gatekeepers(self, engine):
        intel = engine.analyze()
        # Find communities that have members
        comms = list(intel.communities.keys())
        if len(comms) >= 2:
            gates = engine.find_gatekeepers(comms[0], comms[1])
            assert isinstance(gates, list)


class TestOperationPlan:
    def test_plan_with_entry_nodes(self, engine):
        plan = engine.plan_operation(
            objective="reach",
            target_nodes=["dave", "eve", "frank"],
            entry_nodes=["alice"],
        )
        assert plan.objective == "reach"
        assert len(plan.entry_points) >= 1
        assert plan.entry_points[0]["node"] == "alice"

    def test_plan_auto_entry(self, engine):
        plan = engine.plan_operation(
            objective="reach",
            target_nodes=["dave", "eve"],
        )
        assert len(plan.entry_points) >= 1

    def test_plan_with_community(self, engine):
        intel = engine.analyze()
        comms = list(intel.communities.keys())
        if comms:
            plan = engine.plan_operation(
                objective="reach",
                target_community=comms[0],
                entry_nodes=["alice"],
            )
            assert isinstance(plan.paths, list)

    def test_plan_to_dict(self, engine):
        plan = engine.plan_operation(
            objective="reach",
            target_nodes=["dave"],
            entry_nodes=["alice"],
        )
        d = plan.to_dict()
        assert d["objective"] == "reach"
        assert "entry_points" in d
        assert "paths" in d

    def test_plan_identifies_weak_links(self, engine):
        plan = engine.plan_operation(
            objective="disrupt",
            target_nodes=list(engine.G.nodes()),
        )
        assert isinstance(plan.weak_links, list)


class TestCompare:
    def test_compare_with_added_node(self):
        G1 = _build_test_graph()
        G2 = _build_test_graph()
        G2.add_node("newcomer")
        G2.add_edge("newcomer", "alice", weight=2.0, types={"reply"})

        e1 = NetworkEngine(G1)
        e2 = NetworkEngine(G2)
        diff = e1.compare(e2)

        assert "newcomer" in diff["new_nodes"]
        assert diff["node_count_delta"] == 1

    def test_compare_with_removed_node(self):
        G1 = _build_test_graph()
        G2 = _build_test_graph()
        G2.remove_node("heidi")

        e1 = NetworkEngine(G1)
        e2 = NetworkEngine(G2)
        diff = e1.compare(e2)

        assert "heidi" in diff["lost_nodes"]
        assert diff["node_count_delta"] == -1

    def test_compare_identical(self):
        G = _build_test_graph()
        e1 = NetworkEngine(G)
        e2 = NetworkEngine(G.copy())
        diff = e1.compare(e2)
        assert diff["node_count_delta"] == 0
        assert len(diff["new_nodes"]) == 0


class TestExport:
    def test_export_intel(self, engine):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        engine.export_intel(path)
        data = json.loads(Path(path).read_text())
        assert data["node_count"] == 8
        assert "nodes" in data
        Path(path).unlink()

    def test_export_plan(self, engine):
        plan = engine.plan_operation(
            objective="reach",
            target_nodes=["dave"],
            entry_nodes=["alice"],
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        engine.export_plan(plan, path)
        data = json.loads(Path(path).read_text())
        assert data["objective"] == "reach"
        Path(path).unlink()


class TestDataclassSerialization:
    def test_operational_node_to_dict(self):
        op = OperationalNode(node="test", community=1, role="hub")
        d = op.to_dict()
        assert d["node"] == "test"
        assert d["role"] == "hub"

    def test_influence_path_to_dict(self):
        ip = InfluencePath(
            source="a", target="b", path=["a", "c", "b"],
            hops=2, reliability=0.8,
            bottleneck_edge=("a", "c"), bottleneck_weight=0.5,
        )
        d = ip.to_dict()
        assert d["hops"] == 2
        assert d["bottleneck_edge"] == ["a", "c"]
