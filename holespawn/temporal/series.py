"""
Build time series from recordings: run NLP per snapshot, aggregate metrics. No LLM.
"""

import json
from pathlib import Path
from typing import Any

from holespawn.ingest.apify_twitter import _item_to_text
from holespawn.nlp import DiscordNLPAnalyzer

from .query import list_recordings


def _load_recording_json(recordings_root: Path, file_path: str) -> list[dict]:
    """Load one recording JSON; return list of raw items (e.g. tweet dicts)."""
    full = recordings_root / file_path
    if not full.is_file():
        return []
    try:
        with open(full, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return [data]


def _items_to_messages(items: list[dict]) -> list[dict]:
    """Convert raw recording items (Twitter/Discord) to message-like dicts with 'content'."""
    messages = []
    for item in items:
        text = _item_to_text(item) if isinstance(item, dict) else (str(item) if item else "")
        if isinstance(text, str) and text.strip():
            messages.append({"content": text.strip()})
    return messages


def build_series(
    recordings_dir: str | Path,
    subject_id: str,
    *,
    source_type: str | None = "twitter",
    limit: int | None = 30,
    order_desc: bool = False,
) -> list[dict[str, Any]]:
    """
    For each recording of subject_id, load JSON, run NLP (VADER + topics), return time series.
    Each point: { timestamp, sentiment_score, vocabulary_richness, top_topics, record_count }.
    order_desc=False => chronological (oldest first) for trend computation.
    """
    root = Path(recordings_dir)
    db_path = root / "recordings.db"
    sid = subject_id if subject_id.startswith("@") else f"@{subject_id}"
    rows = list_recordings(db_path, sid, source_type=source_type, limit=limit, order_desc=order_desc)
    if not rows:
        return []

    analyzer = DiscordNLPAnalyzer()
    series = []
    for row in rows:
        items = _load_recording_json(root, row["file_path"])
        messages = _items_to_messages(items)
        if not messages:
            series.append({
                "timestamp": row["timestamp"],
                "sentiment_score": 0.0,
                "vocabulary_richness": 0.0,
                "top_topics": [],
                "record_count": row["record_count"],
            })
            continue
        analysis = analyzer.analyze_messages(messages)
        topics = analyzer.extract_topics(messages)
        sent = analysis.get("sentiment_distribution") or {}
        pos = float(sent.get("positive", 0))
        neg = float(sent.get("negative", 0))
        sentiment_score = pos - neg
        series.append({
            "timestamp": row["timestamp"],
            "sentiment_score": round(sentiment_score, 4),
            "vocabulary_richness": round(float(analysis.get("vocabulary_richness", 0)), 4),
            "top_topics": [t[0] for t in (topics.get("primary_topics") or [])[:5]],
            "record_count": row["record_count"],
        })
    return series


def compute_signature(series: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute influence-signature metrics from time series: sentiment shift, topic drift, vocabulary change.
    No LLM. Simple diffs and variance.
    """
    if len(series) < 2:
        return {
            "sentiment_shift": 0.0,
            "vocabulary_drift": 0.0,
            "topic_drift_score": 0.0,
            "points": len(series),
        }

    sentiments = [p["sentiment_score"] for p in series]
    vocabs = [p["vocabulary_richness"] for p in series]
    sentiment_shift = float(sentiments[-1] - sentiments[0]) if sentiments else 0.0
    vocabulary_drift = float(vocabs[-1] - vocabs[0]) if vocabs else 0.0

    # Topic drift: Jaccard distance of topic sets over first vs last half
    def _topic_set(pts: list[dict]) -> set[str]:
        s: set[str] = set()
        for p in pts:
            for t in p.get("top_topics") or []:
                if isinstance(t, str):
                    s.add(t)
                elif isinstance(t, (list, tuple)) and t:
                    s.add(str(t[0]))
        return s

    mid = len(series) // 2
    first_half = _topic_set(series[: mid + 1])
    second_half = _topic_set(series[mid + 1 :])
    if first_half or second_half:
        union = first_half | second_half
        inter = first_half & second_half
        topic_drift_score = 1.0 - (len(inter) / len(union)) if union else 0.0
    else:
        topic_drift_score = 0.0

    return {
        "sentiment_shift": round(sentiment_shift, 4),
        "vocabulary_drift": round(vocabulary_drift, 4),
        "topic_drift_score": round(topic_drift_score, 4),
        "points": len(series),
    }
