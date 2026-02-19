"""Tests for Community Archive connector — mocked API, real data conversion."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from holespawn.ingest.community_archive import (
    CommunityArchiveClient,
    harvest_account,
    harvest_network_overlap,
    to_holespawn_graph,
    extract_content,
)


# ── Fixtures ─────────────────────────────────────────────────────

MOCK_ACCOUNT = {"account_id": "12345", "username": "testuser", "created_at": "2020-01-01"}
MOCK_PROFILE = {"bio": "test bio", "avatar_url": "https://example.com/av.jpg", "account_id": "12345"}
MOCK_TWEETS = [
    {
        "tweet_id": "t1", "account_id": "12345", "full_text": "hello world #test",
        "created_at": "2024-01-15T10:00:00Z", "in_reply_to_screen_name": None,
        "conversation_id": "c1",
    },
    {
        "tweet_id": "t2", "account_id": "12345", "full_text": "RT @otheruser: great stuff",
        "created_at": "2024-01-16T10:00:00Z", "in_reply_to_screen_name": None,
        "conversation_id": "c2",
    },
    {
        "tweet_id": "t3", "account_id": "12345", "full_text": "@mentioned check this",
        "created_at": "2024-01-17T10:00:00Z", "in_reply_to_screen_name": "replyuser",
        "conversation_id": "c3",
    },
]
MOCK_FOLLOWERS = [{"follower_account_id": "f1"}, {"follower_account_id": "f2"}]
MOCK_FOLLOWING = [{"following_account_id": "g1"}, {"following_account_id": "g2"}]
MOCK_MENTIONS = [{"mentioned_user_screen_name": "bob", "created_at": "2024-01-15"}]
MOCK_QUOTE_TWEETS = [{"quoted_user_screen_name": "quotedguy", "full_text": "interesting take", "created_at": "2024-01-18"}]
MOCK_RETWEETS = [{"retweeted_user_screen_name": "rtguy", "created_at": "2024-01-19"}]


def _make_mock_client():
    client = MagicMock(spec=CommunityArchiveClient)
    client.get_account_by_username.return_value = MOCK_ACCOUNT
    client.get_profile.return_value = MOCK_PROFILE
    client.get_tweets.return_value = MOCK_TWEETS
    client.get_followers.return_value = MOCK_FOLLOWERS
    client.get_following.return_value = MOCK_FOLLOWING
    client.get_mentions.return_value = MOCK_MENTIONS
    client.get_quote_tweets.return_value = MOCK_QUOTE_TWEETS
    client.get_retweets.return_value = MOCK_RETWEETS
    client.list_accounts.return_value = [MOCK_ACCOUNT, {"account_id": "99", "username": "other"}]
    return client


# ── Tests ────────────────────────────────────────────────────────

class TestHarvestAccount:
    def test_harvest_saves_files(self, tmp_path):
        client = _make_mock_client()
        data = harvest_account("testuser", client=client, output_dir=tmp_path)

        assert data["account"] == MOCK_ACCOUNT
        assert data["tweets"] == MOCK_TWEETS
        assert (tmp_path / "profile.json").exists()
        assert (tmp_path / "tweets.json").exists()
        assert (tmp_path / "followers.json").exists()
        assert (tmp_path / "following.json").exists()
        assert (tmp_path / "mentions.json").exists()

    def test_harvest_missing_account(self):
        client = _make_mock_client()
        client.get_account_by_username.return_value = None
        data = harvest_account("nobody", client=client)
        assert data == {}


class TestNetworkOverlap:
    def test_overlap_finds_matching_accounts(self):
        client = _make_mock_client()
        our_partition = ["testuser", "nonexistent", "TESTUSER"]
        harvested = harvest_network_overlap(our_partition, client=client)
        # Should find testuser (case-insensitive)
        assert "testuser" in harvested

    def test_overlap_with_dict_partition(self):
        client = _make_mock_client()
        partition = {"cluster_0": ["testuser", "other"], "cluster_1": ["nobody"]}
        harvested = harvest_network_overlap(partition, client=client)
        assert "testuser" in harvested
        assert "other" in harvested


class TestToHolespawnGraph:
    def test_converts_tweets_to_graph_format(self):
        harvested = {"testuser": {
            "tweets": MOCK_TWEETS,
            "followers": MOCK_FOLLOWERS,
            "following": MOCK_FOLLOWING,
            "mentions": MOCK_MENTIONS,
            "quote_tweets": MOCK_QUOTE_TWEETS,
            "retweets": MOCK_RETWEETS,
        }}
        result = to_holespawn_graph(harvested)

        assert "tweets" in result
        assert "followers" in result
        assert "edge_map" in result

        # Should have original tweets + RT entries + QT entries + mention entries
        assert len(result["tweets"]) > len(MOCK_TWEETS)

        # Check RT detection
        rt_tweets = [t for t in result["tweets"] if t.get("is_retweet")]
        assert len(rt_tweets) >= 1

        # Check QT conversion
        qt_tweets = [t for t in result["tweets"] if t.get("is_quote")]
        assert len(qt_tweets) == 1
        assert qt_tweets[0]["quoted_user"] == "quotedguy"

        # Followers and edge_map
        assert "testuser" in result["followers"]
        assert "testuser" in result["edge_map"]

    def test_builds_with_graph_builder(self):
        """Integration: verify output works with actual graph_builder."""
        from holespawn.network.graph_builder import build_graph

        harvested = {"testuser": {
            "tweets": MOCK_TWEETS, "followers": MOCK_FOLLOWERS,
            "following": MOCK_FOLLOWING, "mentions": MOCK_MENTIONS,
            "quote_tweets": MOCK_QUOTE_TWEETS, "retweets": MOCK_RETWEETS,
        }}
        graph_input = to_holespawn_graph(harvested)
        spec = build_graph(**graph_input)
        assert spec.node_count > 0
        assert spec.edge_count > 0


class TestExtractContent:
    def test_extracts_tweet_corpus(self):
        harvested = {"testuser": {"tweets": MOCK_TWEETS}}
        tweets = extract_content(harvested)

        assert len(tweets) == 3
        assert all(t["author"] == "testuser" for t in tweets)
        assert tweets[0]["full_text"] == "hello world #test"
        assert "test" in tweets[0]["hashtags"]

    def test_works_with_content_overlay(self):
        """Integration: verify output works with content_overlay."""
        from holespawn.network.content_overlay import build_node_topic_profiles

        harvested = {"testuser": {"tweets": MOCK_TWEETS}}
        tweets = extract_content(harvested)
        profiles = build_node_topic_profiles(tweets)
        assert "testuser" in profiles
        assert profiles["testuser"].tweet_count == 3


class TestNetworkAdapter:
    """Tests for the network-layer CommunityArchiveSource."""

    def test_build_social_graph(self):
        from holespawn.network.community_archive import CommunityArchiveSource

        client = _make_mock_client()
        source = CommunityArchiveSource(client=client)

        # Pre-populate cache to avoid real API calls
        source._cache["testuser"] = {
            "tweets": MOCK_TWEETS,
            "followers": MOCK_FOLLOWERS,
            "following": MOCK_FOLLOWING,
            "mentions": MOCK_MENTIONS,
            "quote_tweets": MOCK_QUOTE_TWEETS,
            "retweets": MOCK_RETWEETS,
        }

        graph = source.build_social_graph(["testuser"])
        assert graph.node_count > 0
        assert graph.edge_count > 0

    def test_fetch_follow_graph(self):
        from holespawn.network.community_archive import CommunityArchiveSource

        client = _make_mock_client()
        source = CommunityArchiveSource(client=client)

        source._cache["testuser"] = {
            "tweets": [],
            "followers": MOCK_FOLLOWERS,
            "following": MOCK_FOLLOWING,
            "mentions": [],
            "quote_tweets": [],
            "retweets": [],
        }

        graph = source.fetch_follow_graph(["testuser"])
        # Should have follow edges only
        assert graph.node_count > 0
        for u, v, data in graph.graph.edges(data=True):
            assert "follow" in data.get("types", set())

    def test_fetch_account_tweets(self):
        from holespawn.network.community_archive import CommunityArchiveSource

        client = _make_mock_client()
        source = CommunityArchiveSource(client=client)

        source._cache["testuser"] = {
            "tweets": MOCK_TWEETS,
            "followers": [],
            "following": [],
            "mentions": [],
            "quote_tweets": MOCK_QUOTE_TWEETS,
            "retweets": MOCK_RETWEETS,
        }

        tweets = source.fetch_account_tweets("testuser")
        assert len(tweets) > 0
        assert all(t.get("author") == "testuser" for t in tweets)

    def test_build_content_corpus(self):
        from holespawn.network.community_archive import CommunityArchiveSource

        client = _make_mock_client()
        source = CommunityArchiveSource(client=client)

        source._cache["testuser"] = {"tweets": MOCK_TWEETS}

        corpus = source.build_content_corpus(["testuser"])
        assert len(corpus) == 3
        assert all(t["author"] == "testuser" for t in corpus)


class TestConversationTree:
    """Tests for conversation tree reconstruction (memetic-lineage technique)."""

    def test_build_tree(self):
        from holespawn.network.community_archive import _build_conversation_tree

        tweets = [
            {"tweet_id": "100", "account_id": "a1", "username": "alice",
             "reply_to_tweet_id": None, "created_at": "2024-01-01T10:00:00Z"},
            {"tweet_id": "101", "account_id": "a2", "username": "bob",
             "reply_to_tweet_id": "100", "created_at": "2024-01-01T11:00:00Z"},
            {"tweet_id": "102", "account_id": "a3", "username": "charlie",
             "reply_to_tweet_id": "101", "created_at": "2024-01-01T12:00:00Z"},
            {"tweet_id": "103", "account_id": "a1", "username": "alice",
             "reply_to_tweet_id": "100", "created_at": "2024-01-01T12:30:00Z"},
        ]
        tree = _build_conversation_tree(tweets, "100")
        assert tree.root_tweet_id == "100"
        assert tree.root_author == "alice"
        assert tree.depth == 2  # 100 -> 101 -> 102
        assert tree.participant_count == 3
        assert "100" in tree.children_map
        assert len(tree.children_map["100"]) == 2  # 101 and 103

    def test_empty_tree(self):
        from holespawn.network.community_archive import _build_conversation_tree

        tree = _build_conversation_tree([], "999")
        assert tree.depth == 0
        assert tree.participant_count == 0


class TestSelfQuoteFiltering:
    """Tests for self-amplification filtering in influence_flow (memetic-lineage adoption)."""

    def test_self_rt_excluded_from_seeds(self):
        import networkx as nx
        from holespawn.network.influence_flow import detect_narrative_seeds

        G = nx.DiGraph()
        # Self-retweet edge (should be excluded)
        G.add_edge("alice", "alice", weight=4.0, types={"retweet"})
        # Real amplification
        G.add_edge("bob", "alice", weight=4.0, types={"quote_tweet"})

        seeds = detect_narrative_seeds(G)
        alice_seed = next((s for s in seeds if s.user == "alice"), None)
        assert alice_seed is not None
        # Only bob's amplification should count, not alice's self-RT
        assert alice_seed.total_amplification == 4
        assert "bob" in alice_seed.top_amplifiers
        assert "alice" not in alice_seed.top_amplifiers

    def test_self_qt_excluded_from_scores(self):
        import networkx as nx
        from holespawn.network.influence_flow import compute_influence_scores

        G = nx.DiGraph()
        G.add_edge("alice", "alice", weight=4.0, types={"quote_tweet"})
        G.add_edge("bob", "alice", weight=3.0, types={"retweet"})
        G.add_edge("charlie", "bob", weight=2.0, types={"quote_tweet"})

        scores, breakdown = compute_influence_scores(G)
        # alice's self-QT should not inflate her seeding score
        assert breakdown["alice"]["seeding"] > 0  # bob's RT counted
        # bob should have seeding from charlie
        assert breakdown["bob"]["seeding"] > 0


class TestPagination:
    def test_pagination_stops_on_empty(self):
        client = CommunityArchiveClient.__new__(CommunityArchiveClient)
        client.base_url = "http://fake"
        client.page_size = 2
        client.rate_limit_delay = 0
        client.session = MagicMock()

        # First call returns 2 items, second returns empty
        resp1 = MagicMock()
        resp1.json.return_value = [{"id": 1}, {"id": 2}]
        resp1.status_code = 200
        resp2 = MagicMock()
        resp2.json.return_value = []
        resp2.status_code = 200
        client.session.get.side_effect = [resp1, resp2]

        results = client._get_paginated("test", {})
        assert len(results) == 2

    def test_pagination_respects_limit(self):
        client = CommunityArchiveClient.__new__(CommunityArchiveClient)
        client.base_url = "http://fake"
        client.page_size = 10
        client.rate_limit_delay = 0
        client.session = MagicMock()

        resp = MagicMock()
        resp.json.return_value = [{"id": i} for i in range(10)]
        resp.status_code = 200
        client.session.get.return_value = resp

        results = client._get_paginated("test", {}, limit=3)
        assert len(results) == 3
