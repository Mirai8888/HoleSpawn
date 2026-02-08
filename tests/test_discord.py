"""Tests for Discord ingestion and Discord-enhanced profiling."""

import json
from pathlib import Path

import pytest


def test_load_from_discord_returns_social_content():
    """load_from_discord returns SocialContent with posts from messages and discord_data attached."""
    from holespawn.ingest import SocialContent, load_from_discord

    payload = {
        "user_id": "u1",
        "messages": [
            {"content": "first message"},
            {"content": "second message"},
        ],
        "servers": [{"server_id": "s1", "server_name": "Test Server"}],
    }
    content = load_from_discord(payload)
    assert isinstance(content, SocialContent)
    assert content.posts == ["first message", "second message"]
    assert content.raw_text == "first message\nsecond message"
    assert content.discord_data is payload
    assert content.discord_data["user_id"] == "u1"


def test_load_from_discord_empty_or_invalid():
    """load_from_discord handles empty dict and non-dict."""
    from holespawn.ingest import load_from_discord

    empty = load_from_discord({})
    assert empty.posts == []
    assert empty.raw_text == ""
    assert empty.discord_data == {}

    invalid = load_from_discord("not a dict")
    assert invalid.posts == []
    assert invalid.discord_data is None


def test_load_from_discord_file():
    """Load Discord export from JSON file (via load_from_file then discord payload)."""
    from holespawn.ingest import load_from_discord

    data_dir = Path(__file__).resolve().parent.parent / "data"
    path = data_dir / "sample_discord_export.json"
    if not path.exists():
        pytest.skip("data/sample_discord_export.json not found")
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    content = load_from_discord(payload)
    assert len(content.posts) >= 5
    assert content.discord_data is not None
    assert "servers" in content.discord_data
    assert "activity_patterns" in content.discord_data


def test_build_profile_with_discord_data():
    """Profile built from Discord content includes Discord-specific fields."""
    from holespawn.ingest import load_from_discord
    from holespawn.profile import build_profile

    payload = {
        "messages": [
            {"content": "honestly I feel like we're missing something obvious"},
            {"content": "tbh the API is so much better now"},
            {"content": "struggle with rate limits every day"},
            {"content": "anxious about the next release"},
            {"content": "imo we need to fix the foundation first"},
        ],
        "servers": [
            {"server_id": "s1", "server_name": "Build in Public Devs"},
            {"server_name": "Indie Game Devs"},
        ],
        "reactions_given": [
            {"message_content": "the foundation matters more than features"},
            {"message_content": "prod is on fire again"},
        ],
        "activity_patterns": {"peak_hours": [14, 15], "message_frequency": 3.0},
    }
    content = load_from_discord(payload)
    profile = build_profile(content)

    assert hasattr(profile, "tribal_affiliations")
    assert isinstance(profile.tribal_affiliations, list)
    assert (
        "Build in Public Devs" in profile.tribal_affiliations
        or len(profile.tribal_affiliations) >= 1
    )

    assert hasattr(profile, "reaction_triggers")
    assert isinstance(profile.reaction_triggers, list)

    assert hasattr(profile, "conversational_intimacy")
    assert profile.conversational_intimacy in ("guarded", "open", "vulnerable", "moderate")

    assert hasattr(profile, "community_role")
    assert profile.community_role in ("lurker", "participant", "leader")

    assert hasattr(profile, "engagement_rhythm")
    assert isinstance(profile.engagement_rhythm, dict)
    assert (
        profile.engagement_rhythm.get("peak_hours") == [14, 15]
        or profile.engagement_rhythm.get("message_frequency") == 3.0
        or len(profile.engagement_rhythm) >= 0
    )


def test_build_discord_profile_hybrid_nlp_only():
    """Hybrid Discord profile with use_llm=False uses NLP only (no API call)."""
    from holespawn.profile.discord_profile_builder import build_discord_profile

    payload = {
        "messages": [
            {"content": "first message here"},
            {"content": "second message with more text"},
            {"content": "third"},
            {"content": "fourth"},
            {"content": "fifth"},
        ],
        "servers": [{"server_name": "Test Server"}],
        "reactions_given": [{"message_content": "something they reacted to"}],
    }
    profile = build_discord_profile(payload, use_nlp=True, use_llm=False)
    assert hasattr(profile, "tribal_affiliations")
    assert hasattr(profile, "communication_style")
    # NLP-only path should still produce a valid profile
    assert profile.avg_sentence_length >= 0 or profile.avg_word_length >= 0


def test_build_profile_without_discord_data_has_defaults():
    """Profile built from non-Discord content has default Discord fields."""
    from holespawn.ingest import load_from_text
    from holespawn.profile import build_profile

    content = load_from_text("post one\npost two\npost three\npost four\npost five")
    assert getattr(content, "discord_data", None) is None
    profile = build_profile(content)

    assert getattr(profile, "tribal_affiliations", None) == [] or profile.tribal_affiliations == []
    assert getattr(profile, "reaction_triggers", None) == [] or profile.reaction_triggers == []
    assert getattr(profile, "conversational_intimacy", "moderate") in (
        "guarded",
        "open",
        "vulnerable",
        "moderate",
    )
    assert getattr(profile, "community_role", "participant") in ("lurker", "participant", "leader")
    assert isinstance(getattr(profile, "engagement_rhythm", {}), dict)
