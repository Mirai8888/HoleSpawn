"""
Phase 4 — Cohort analysis.

Inner circle from network analysis is the cohort; this module only handles the
temporal aggregation layer over recordings. Given a list of subject_ids with
recordings, it:

- Runs Phase 3 temporal NLP for each member (build_series + compute_signature)
- Aggregates to a cohort-level time series and drift signature

One LLM call to synthesize cohort narrative can be layered on top of the
JSON this module produces; no LLM is invoked here.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .series import build_series, compute_signature


def build_cohort_results(
    recordings_dir: str | Path,
    subject_ids: Iterable[str],
    *,
    source_type: str | None = "twitter",
    limit: int | None = 30,
) -> list[dict[str, Any]]:
    """
    Run temporal NLP (Phase 3) for each subject in subject_ids.

    Returns list of:
      {
        "subject_id": "@handle",
        "series": [...],         # output of build_series
        "signature": {...} | None,
      }

    Subjects without any recordings get series=[] and signature=None.
    """
    root = Path(recordings_dir)
    results: list[dict[str, Any]] = []
    for raw_id in subject_ids:
        sid = raw_id if raw_id.startswith("@") else f"@{raw_id}"
        series = build_series(root, sid, source_type=source_type, limit=limit, order_desc=False)
        if not series:
            results.append({"subject_id": sid, "series": [], "signature": None})
            continue
        sig = compute_signature(series)
        results.append({"subject_id": sid, "series": series, "signature": sig})
    return results


def _aggregate_numeric(series_list: list[list[dict[str, Any]]], key: str) -> list[float]:
    """
    Aggregate numeric key across subjects per index.
    Simple average over subjects that have that index.
    """
    max_len = max((len(s) for s in series_list), default=0)
    agg: list[float] = []
    for idx in range(max_len):
        vals: list[float] = []
        for s in series_list:
            if idx < len(s):
                v = s[idx].get(key)
                if isinstance(v, (int, float)):
                    vals.append(float(v))
        agg.append(sum(vals) / len(vals) if vals else 0.0)
    return agg


def _aggregate_topics(series_list: list[list[dict[str, Any]]]) -> list[list[str]]:
    """
    Aggregate top_topics across subjects per index.
    Returns list of lists: at index i → top tokens across cohort.
    """
    max_len = max((len(s) for s in series_list), default=0)
    out: list[list[str]] = []
    for idx in range(max_len):
        counter: Counter[str] = Counter()
        for s in series_list:
            if idx < len(s):
                topics = s[idx].get("top_topics") or []
                for t in topics:
                    if isinstance(t, str):
                        counter[t] += 1
        out.append([w for w, _ in counter.most_common(10)])
    return out


def aggregate_cohort(
    cohort_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Given per-subject results from build_cohort_results, compute:

    - aggregate_series: cohort-level time series (avg sentiment/vocab per index)
    - aggregate_signature: drift metrics from aggregate_series

    This is a coarse cohort view; more advanced bucketing by calendar time
    can be added later when recordings are dense.
    """
    series_list = [c["series"] for c in cohort_results if c.get("series")]
    if not series_list:
        return {
            "members": [c["subject_id"] for c in cohort_results],
            "aggregate_series": [],
            "aggregate_signature": {
                "sentiment_shift": 0.0,
                "vocabulary_drift": 0.0,
                "topic_drift_score": 0.0,
                "points": 0,
            },
        }

    # Assume all series are in chronological order already.
    avg_sentiments = _aggregate_numeric(series_list, "sentiment_score")
    avg_vocab = _aggregate_numeric(series_list, "vocabulary_richness")
    agg_topics = _aggregate_topics(series_list)

    # Use timestamps from the subject with the longest series as reference.
    longest = max(series_list, key=len)
    timestamps = [p.get("timestamp") for p in longest]

    aggregate_series: list[dict[str, Any]] = []
    for i in range(len(timestamps)):
        aggregate_series.append(
            {
                "timestamp": timestamps[i],
                "sentiment_score": round(avg_sentiments[i], 4),
                "vocabulary_richness": round(avg_vocab[i], 4),
                "top_topics": agg_topics[i],
            }
        )

    aggregate_signature = compute_signature(aggregate_series)
    return {
        "members": [c["subject_id"] for c in cohort_results],
        "aggregate_series": aggregate_series,
        "aggregate_signature": aggregate_signature,
    }

