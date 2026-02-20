"""Tests for cognitive landscape monitor."""

import tempfile
from pathlib import Path

from holespawn.monitor.cognitive_landscape import (
    CognitiveLandscapeMonitor,
    VocabularySignal,
    SEITHAR_VOCABULARY,
    CYBORGISM_VOCABULARY,
)


def _monitor(tmp=None):
    return CognitiveLandscapeMonitor(data_dir=tmp or Path(tempfile.mkdtemp()))


def test_add_target():
    m = _monitor()
    result = m.add_target("testuser", "12345", tags=["cyborgism"])
    assert result["added"] == "testuser"
    assert "testuser" in m.targets


def test_scan_detects_seithar_vocab():
    m = _monitor()
    m.add_target("alice", "1")
    tweets = [
        {"full_text": "The cognitive warfare implications of this are massive", "tweet_id": "t1"},
        {"full_text": "Just had coffee", "tweet_id": "t2"},
    ]
    signals = m.scan_account("alice", tweets)
    assert len(signals) >= 1
    terms = {s.term for s in signals}
    assert "cognitive warfare" in terms


def test_scan_detects_native_vocab():
    m = _monitor()
    m.add_target("bob", "2")
    tweets = [
        {"full_text": "The simulator hypothesis changes everything about alignment", "tweet_id": "t1"},
        {"full_text": "Hyperstition is fiction that makes itself real", "tweet_id": "t2"},
    ]
    signals = m.scan_account("bob", tweets)
    terms = {s.term for s in signals}
    assert "simulator" in terms
    assert "hyperstition" in terms


def test_snapshot_creation():
    m = _monitor()
    m.add_target("carol", "3")
    signals = [
        VocabularySignal(term="cognitive warfare", username="carol", text="test"),
        VocabularySignal(term="simulator", username="carol", text="test2"),
    ]
    snapshot = m.create_snapshot(signals, tweets_scanned=50)
    assert snapshot.total_tweets_scanned == 50
    assert len(snapshot.vocabulary_signals) == 2
    assert len(snapshot.narrative_themes) > 0


def test_adoption_rate_calculation():
    m = _monitor()
    m.add_target("dave", "4")
    # Simulate vocabulary hits
    m.targets["dave"].vocabulary_hits = {
        "cognitive warfare": 3,
        "substrate manipulation": 2,
        "simulator": 10,
        "hyperstition": 5,
    }
    rate = m.vocabulary_adoption_rate()
    assert rate["seithar_vocabulary_hits"] == 5
    assert rate["native_vocabulary_hits"] == 15
    assert 0 < rate["adoption_rate"] < 1


def test_adoption_rate_zero():
    m = _monitor()
    rate = m.vocabulary_adoption_rate()
    assert rate["adoption_rate"] == 0.0


def test_persistence():
    d = Path(tempfile.mkdtemp())
    m1 = CognitiveLandscapeMonitor(data_dir=d)
    m1.add_target("eve", "5", tags=["test"])
    m2 = CognitiveLandscapeMonitor(data_dir=d)
    assert "eve" in m2.targets


def test_context_detection():
    m = _monitor()
    m.add_target("frank", "6")
    tweets = [
        {"full_text": "Cognitive defense is underrated", "tweet_id": "t1"},
        {"full_text": "I agree about cognitive defense", "tweet_id": "t2", "in_reply_to_user_id": "someone"},
    ]
    signals = m.scan_account("frank", tweets)
    contexts = {s.context for s in signals}
    assert "original" in contexts
    assert "reply" in contexts
