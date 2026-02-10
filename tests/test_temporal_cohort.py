"""Tests for Phase 4 cohort aggregation over temporal series."""

import tempfile
from pathlib import Path

import sqlite3

from holespawn.temporal import (
    aggregate_cohort,
    build_cohort_results,
    build_series,
)


def _make_recording(root: Path, subject_id: str, ts: str, texts: list[str]) -> None:
    db = root / "recordings.db"
    if not db.exists():
        conn = sqlite3.connect(str(db))
        conn.execute(
            """
            CREATE TABLE recordings (
                subject_id TEXT, timestamp TEXT, file_path TEXT,
                source_type TEXT, record_count INTEGER
            )
            """
        )
        conn.commit()
        conn.close()
    conn = sqlite3.connect(str(db))
    rel = f"twitter/{subject_id}/{ts}.json"
    conn.execute(
        "INSERT INTO recordings VALUES (?, ?, ?, ?, ?)",
        (subject_id, ts, rel, "twitter", len(texts)),
    )
    conn.commit()
    conn.close()
    json_path = root / rel
    json_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    json_path.write_text(
        json.dumps([{"full_text": t} for t in texts]),
        encoding="utf-8",
    )


def test_build_cohort_results_and_aggregate_cohort_smoke():
    """Smoke test: two subjects, one snapshot each, aggregate without error."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_recording(root, "@alice", "20260201_120000", ["I love this."])
        _make_recording(root, "@bob", "20260201_120000", ["This is fine."])

        # Ensure per-subject series builds
        s_alice = build_series(root, "@alice", limit=5, order_desc=False)
        s_bob = build_series(root, "@bob", limit=5, order_desc=False)
        assert len(s_alice) == 1
        assert len(s_bob) == 1

        cohort = build_cohort_results(root, ["@alice", "@bob"], limit=5)
        assert len(cohort) == 2
        for entry in cohort:
            assert "subject_id" in entry and "series" in entry and "signature" in entry

        agg = aggregate_cohort(cohort)
        assert set(agg["members"]) == {"@alice", "@bob"}
        assert agg["aggregate_series"]
        sig = agg["aggregate_signature"]
        assert "sentiment_shift" in sig and "vocabulary_drift" in sig and "topic_drift_score" in sig

