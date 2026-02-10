"""Tests for temporal NLP (Phase 3): VADER + theme extraction per recording snapshot."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from holespawn.temporal import (
    build_series,
    compute_signature,
    list_recordings,
    list_subjects,
)


def test_list_recordings_empty_db():
    """list_recordings returns [] when db does not exist or has no rows."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "recordings.db"
        assert list_recordings(db, "@nobody") == []
        # Create empty db with schema
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE recordings (subject_id, timestamp, file_path, source_type, record_count)"
        )
        conn.commit()
        conn.close()
        assert list_recordings(db, "@nobody") == []


def test_list_recordings_and_list_subjects():
    """list_recordings returns rows; list_subjects returns distinct subject_ids."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "recordings.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            """
            CREATE TABLE recordings (
                subject_id TEXT, timestamp TEXT, file_path TEXT,
                source_type TEXT, record_count INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO recordings VALUES (?, ?, ?, ?, ?)",
            ("@alice", "20260201_120000", "twitter/@alice/20260201_120000.json", "twitter", 10),
        )
        conn.execute(
            "INSERT INTO recordings VALUES (?, ?, ?, ?, ?)",
            ("@alice", "20260202_120000", "twitter/@alice/20260202_120000.json", "twitter", 5),
        )
        conn.execute(
            "INSERT INTO recordings VALUES (?, ?, ?, ?, ?)",
            ("@bob", "20260201_120000", "twitter/@bob/20260201_120000.json", "twitter", 3),
        )
        conn.commit()
        conn.close()

        rows = list_recordings(db, "@alice", limit=5, order_desc=False)
        assert len(rows) == 2
        assert rows[0]["timestamp"] == "20260201_120000"
        assert rows[1]["timestamp"] == "20260202_120000"

        subjects = list_subjects(db)
        assert set(subjects) == {"@alice", "@bob"}
        assert list_subjects(db, source_type="twitter") == sorted(["@alice", "@bob"])


def test_build_series_empty_and_with_mock_json():
    """build_series returns [] when no recordings; returns series when JSON exists."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db = root / "recordings.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            """
            CREATE TABLE recordings (
                subject_id TEXT, timestamp TEXT, file_path TEXT,
                source_type TEXT, record_count INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO recordings VALUES (?, ?, ?, ?, ?)",
            ("@test", "20260201_120000", "twitter/@test/20260201_120000.json", "twitter", 2),
        )
        conn.commit()
        conn.close()

        # No JSON file yet -> build_series still runs but point has zero metrics
        series = build_series(root, "@test", limit=5, order_desc=False)
        assert len(series) == 1
        assert series[0]["timestamp"] == "20260201_120000"
        assert "sentiment_score" in series[0]
        assert "vocabulary_richness" in series[0]
        assert "top_topics" in series[0]
        assert series[0]["record_count"] == 2

        # Add JSON with tweet-like items
        (root / "twitter" / "@test").mkdir(parents=True)
        (root / "twitter" / "@test" / "20260201_120000.json").write_text(
            json.dumps([
                {"full_text": "I love this project. So excited!"},
                {"text": "Feeling neutral today."},
            ]),
            encoding="utf-8",
        )
        series2 = build_series(root, "@test", limit=5, order_desc=False)
        assert len(series2) == 1
        assert isinstance(series2[0]["sentiment_score"], (int, float))
        assert isinstance(series2[0]["top_topics"], list)
        assert series2[0]["record_count"] == 2


def test_compute_signature():
    """compute_signature returns drift metrics from series."""
    # Too few points
    sig = compute_signature([{"sentiment_score": 0.5, "vocabulary_richness": 0.3, "top_topics": []}])
    assert sig["points"] == 1
    assert sig["sentiment_shift"] == 0.0

    # Two points
    series = [
        {"sentiment_score": 0.2, "vocabulary_richness": 0.4, "top_topics": ["a", "b"]},
        {"sentiment_score": -0.1, "vocabulary_richness": 0.5, "top_topics": ["b", "c"]},
    ]
    sig2 = compute_signature(series)
    assert sig2["points"] == 2
    assert sig2["sentiment_shift"] == pytest.approx(-0.3)
    assert sig2["vocabulary_drift"] == pytest.approx(0.1)
    assert 0 <= sig2["topic_drift_score"] <= 1.0
