"""
Stage 2: Scan — Cognitive threat scanning against target content.

Wraps seithar-cogdef scanner logic to detect SCT techniques
present in a target's content or being used against them.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import logging
import re

from seithar.taxonomy import SCT_TAXONOMY

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result of cognitive threat scan."""
    target: str
    detections: list[dict[str, Any]] = field(default_factory=list)
    severity: float = 0.0
    threat_classification: str = "Benign"
    raw: dict[str, Any] = field(default_factory=dict)


# --- Local pattern matching (adapted from seithar-cogdef/scanner.py) ---

PATTERN_BANK: dict[str, list[str]] = {
    "SCT-001": [
        "urgent", "immediately", "act now", "breaking", "shocking",
        "outrage", "horrifying", "terrifying", "you won't believe",
        "before it's too late", "last chance", "emergency",
    ],
    "SCT-002": [
        "studies show", "experts say", "research proves", "data shows",
        "according to sources", "insiders report", "leaked",
    ],
    "SCT-003": [
        "dr.", "professor", "expert", "leading", "renowned",
        "prestigious", "award-winning", "world-class",
    ],
    "SCT-004": [
        "everyone knows", "millions of people", "trending", "viral",
        "join the", "movement", "don't miss out",
    ],
    "SCT-005": [
        "as a", "people like you", "your generation", "real patriots",
        "true believers", "if you care about",
    ],
    "SCT-006": [
        "act now", "limited time", "expires", "deadline",
        "hours left", "final notice", "last chance",
    ],
    "SCT-007": [
        "share this", "spread the word", "retweet", "tell everyone",
        "they don't want you to know", "censored", "banned",
    ],
    "SCT-011": [
        "can't be trusted", "media lies", "fake news",
        "cover-up", "do your own research", "mainstream media",
    ],
    "SCT-012": [
        "sign the petition", "take the pledge", "you've already started",
        "no going back", "invested too much", "can't stop now",
    ],
}


def scan_local(content: str) -> list[dict[str, Any]]:
    """Pattern-match content against SCT taxonomy. Returns detections."""
    content_lower = content.lower()
    detections = []

    for code, patterns in PATTERN_BANK.items():
        hits = sum(1 for p in patterns if p in content_lower)
        if hits >= 1:
            sct = SCT_TAXONOMY.get(code)
            detections.append({
                "code": code,
                "name": sct.name if sct else code,
                "confidence": min(hits / max(len(patterns) // 2, 1), 1.0),
                "evidence": f"{hits} pattern matches",
            })

    return detections


def run_scan(target_profile, config: dict | None = None) -> ScanResult:
    """Execute scan against a target profile's content.

    Uses LLM-powered scanner if available, falls back to local patterns.
    """
    config = config or {}
    handle = getattr(target_profile, "handle", str(target_profile))
    result = ScanResult(target=handle)

    content_samples = getattr(target_profile, "content_samples", [])
    combined = "\n".join(content_samples) if content_samples else ""

    if not combined:
        logger.warning("No content to scan for %s", handle)
        return result

    # Try LLM scanner first
    try:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key and config.get("use_llm", False):
            # Import from cogdef if available
            from seithar_cogdef_scanner import analyze_with_llm
            report = analyze_with_llm(combined, api_key, handle)
            result.detections = report.get("techniques", [])
            result.severity = report.get("severity", 0)
            result.threat_classification = report.get("threat_classification", "Unknown")
            result.raw = report
            return result
    except ImportError:
        pass

    # Fall back to local pattern matching
    detections = scan_local(combined)
    result.detections = detections
    result.severity = min(10, sum(d["confidence"] * 3 for d in detections))
    result.threat_classification = detections[0]["name"] if detections else "Benign"
    result.raw = {"mode": "local_pattern_matching", "detections": detections}

    return result
