"""Tests for Moltbook intel and poster modules."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from holespawn.network.moltbook_intel import (
    MoltbookClient,
    EngagementSnapshot,
    collect_metrics,
    build_interaction_graph,
    analyze_content,
    discover_opportunities,
    _parse_ts,
    _score_post,
    SEITHAR_KEYWORDS,
    DATA_DIR,
)
from holespawn.network.moltbook_poster import (
    RateState,
    DEFAULT_LIMITS,
    generate_post,
    generate_comment,
    create_post,
    create_comment,
    SCT_TOPIC_MAP,
    POST_TEMPLATES,
    COMMENT_TEMPLATES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_POST = {
    "id": "post-1",
    "title": "Test Post",
    "content": "Testing social engineering patterns on agent networks",
    "upvotes": 5,
    "downvotes": 1,
    "comment_count": 2,
    "created_at": "2026-02-19T12:00:00Z",
    "author": {"name": "kenshusei"},
    "submolt": {"name": "general", "display_name": "General"},
}

FAKE_POST_OTHER = {
    "id": "post-2",
    "title": "Random Stuff",
    "content": "Just vibing",
    "upvotes": 10,
    "downvotes": 0,
    "comment_count": 0,
    "created_at": "2026-02-19T13:00:00Z",
    "author": {"name": "othermolty"},
    "submolt": {"name": "general"},
}

FAKE_COMMENT = {
    "id": "com-1",
    "content": "Great analysis!",
    "upvotes": 3,
    "downvotes": 0,
    "created_at": "2026-02-19T12:30:00Z",
    "author": {"name": "friendmolty"},
    "parent_id": None,
}


def _make_mock_client(posts=None, comments=None):
    """Build a mock MoltbookClient."""
    client = MagicMock(spec=MoltbookClient)
    client.posts.return_value = posts or [FAKE_POST, FAKE_POST_OTHER]
    client.comments.return_value = comments or [FAKE_COMMENT]
    client.notifications.return_value = []
    client.search.return_value = []
    client.submolt_feed.return_value = []
    client.feed.return_value = posts or [FAKE_POST]
    return client


# ---------------------------------------------------------------------------
# Intel tests
# ---------------------------------------------------------------------------

class TestParseTimestamp:
    def test_iso_z(self):
        ts = _parse_ts("2026-02-19T12:00:00Z")
        assert ts is not None
        assert ts.year == 2026

    def test_iso_offset(self):
        ts = _parse_ts("2026-02-19T12:00:00+00:00")
        assert ts is not None

    def test_none(self):
        assert _parse_ts(None) is None
        assert _parse_ts("") is None
        assert _parse_ts("garbage") is None


class TestScorePost:
    def test_relevant_post_scored(self):
        opp = _score_post(FAKE_POST)
        assert opp is not None
        assert opp.relevance_score > 0
        assert len(opp.keyword_hits) > 0

    def test_irrelevant_post_none(self):
        opp = _score_post(FAKE_POST_OTHER)
        assert opp is None

    def test_empty_post(self):
        assert _score_post({"title": "", "content": ""}) is None


class TestCollectMetrics:
    def test_snapshot_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("holespawn.network.moltbook_intel.DATA_DIR", tmp_path)
        client = _make_mock_client()
        snap = collect_metrics(client, "kenshusei")
        assert isinstance(snap, EngagementSnapshot)
        assert snap.total_posts >= 1
        assert snap.total_upvotes_received >= 5
        # Check file was saved
        files = list(tmp_path.glob("snapshot_*.json"))
        assert len(files) == 1

    def test_no_posts(self, tmp_path, monkeypatch):
        monkeypatch.setattr("holespawn.network.moltbook_intel.DATA_DIR", tmp_path)
        client = MagicMock(spec=MoltbookClient)
        client.posts.return_value = []
        client.comments.return_value = []
        client.notifications.return_value = []
        snap = collect_metrics(client, "nobody")
        assert snap.total_posts == 0


class TestBuildInteractionGraph:
    def test_graph_has_nodes(self, tmp_path, monkeypatch):
        monkeypatch.setattr("holespawn.network.moltbook_intel.DATA_DIR", tmp_path)
        client = _make_mock_client()
        spec = build_interaction_graph(client, "kenshusei")
        assert spec.node_count >= 2  # kenshusei + friendmolty at minimum
        assert spec.edge_count >= 1

    def test_graph_serialized(self, tmp_path, monkeypatch):
        monkeypatch.setattr("holespawn.network.moltbook_intel.DATA_DIR", tmp_path)
        client = _make_mock_client()
        build_interaction_graph(client, "kenshusei")
        assert (tmp_path / "interaction_graph.json").exists()


class TestAnalyzeContent:
    def test_report_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("holespawn.network.moltbook_intel.DATA_DIR", tmp_path)
        client = _make_mock_client()
        report = analyze_content(client)
        d = report.to_dict()
        assert "top_topics" in d
        assert "seithar_sentiment" in d
        assert isinstance(d["submolt_topic_map"], dict)


class TestDiscoverOpportunities:
    def test_finds_relevant(self, tmp_path, monkeypatch):
        monkeypatch.setattr("holespawn.network.moltbook_intel.DATA_DIR", tmp_path)
        client = _make_mock_client()
        opps = discover_opportunities(client, min_score=0.0)
        # FAKE_POST has "social engineering" → should match
        assert any(o.post_id == "post-1" for o in opps)

    def test_high_threshold_filters(self, tmp_path, monkeypatch):
        monkeypatch.setattr("holespawn.network.moltbook_intel.DATA_DIR", tmp_path)
        client = _make_mock_client()
        opps = discover_opportunities(client, min_score=0.99)
        # Very high threshold should filter most
        assert len(opps) <= 1


# ---------------------------------------------------------------------------
# Poster tests
# ---------------------------------------------------------------------------

class TestRateState:
    def test_fresh_state_allows_post(self):
        state = RateState()
        ok, _ = state.can_post()
        assert ok

    def test_rate_limit_blocks_fast_post(self):
        state = RateState()
        state.last_post_ts = time.time()
        ok, reason = state.can_post()
        assert not ok
        assert "wait" in reason.lower()

    def test_daily_limit(self):
        state = RateState()
        state.day_key = time.strftime("%Y-%m-%d")
        state.posts_today = DEFAULT_LIMITS["max_posts_per_day"]
        ok, reason = state.can_post()
        assert not ok
        assert "limit" in reason.lower()

    def test_day_rollover_resets(self):
        state = RateState()
        state.day_key = "2020-01-01"
        state.posts_today = 999
        ok, _ = state.can_post()
        assert ok

    def test_can_comment_fresh(self):
        state = RateState()
        ok, _ = state.can_comment()
        assert ok

    def test_save_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("holespawn.network.moltbook_poster.RATE_STATE_PATH",
                            tmp_path / "rate.json")
        state = RateState()
        state.record_post()
        loaded = RateState.load()
        assert loaded.last_post_ts > 0
        assert loaded.day_key == time.strftime("%Y-%m-%d")


class TestGeneratePost:
    def test_basic_generation(self):
        post = generate_post(
            topic="network analysis",
            sct_codes=["SCT-1", "SCT-3"],
            template="observation",
        )
        assert "network analysis" in post.content
        assert "SCT-1" in post.content
        assert post.submolt == "general"

    def test_all_templates(self):
        for tmpl_name in POST_TEMPLATES:
            post = generate_post(
                topic="test topic",
                sct_codes=["SCT-2"],
                template=tmpl_name,
            )
            assert post.content
            assert post.title

    def test_custom_title(self):
        post = generate_post(
            topic="x",
            sct_codes=[],
            title="Custom Title",
        )
        assert post.title == "Custom Title"

    def test_link_post(self):
        post = generate_post(
            topic="x",
            sct_codes=[],
            url="https://example.com",
        )
        assert post.url == "https://example.com"


class TestGenerateComment:
    def test_basic(self):
        comment = generate_comment("influence mapping", "this reveals a hub node")
        assert "influence mapping" in comment
        assert "hub node" in comment

    def test_all_templates(self):
        for i in range(len(COMMENT_TEMPLATES)):
            c = generate_comment("topic", "observation", template_idx=i)
            assert c


class TestCreatePost:
    def test_dry_run(self):
        post = generate_post("test", ["SCT-1"])
        result = create_post(
            client=MagicMock(spec=MoltbookClient),
            post=post,
            dry_run=True,
        )
        assert result["success"]
        assert result["dry_run"]
        assert "submolt" in result["payload"]

    def test_rate_limited(self, monkeypatch):
        # Force rate limit
        state = RateState()
        state.last_post_ts = time.time()
        monkeypatch.setattr("holespawn.network.moltbook_poster.RateState.load",
                            lambda: state)
        result = create_post(
            client=MagicMock(spec=MoltbookClient),
            topic="test",
            sct_codes=["SCT-1"],
        )
        assert not result["success"]
        assert "rate" in result["error"].lower() or "wait" in result["error"].lower()


class TestCreateComment:
    def test_dry_run(self):
        result = create_comment(
            client=MagicMock(spec=MoltbookClient),
            post_id="post-1",
            content="Test comment",
            dry_run=True,
        )
        assert result["success"]
        assert result["dry_run"]

    def test_generated_comment(self):
        result = create_comment(
            client=MagicMock(spec=MoltbookClient),
            post_id="post-1",
            topic="network analysis",
            observation="interesting hub pattern",
            dry_run=True,
        )
        assert result["success"]
        assert "network analysis" in result["payload"]["content"]

    def test_no_content_fails(self):
        result = create_comment(
            client=MagicMock(spec=MoltbookClient),
            post_id="post-1",
        )
        assert not result["success"]


class TestSCTMapping:
    def test_all_codes_have_descriptions(self):
        for code in SCT_TOPIC_MAP:
            assert SCT_TOPIC_MAP[code]

    def test_codes_format(self):
        for code in SCT_TOPIC_MAP:
            assert code.startswith("SCT-")
