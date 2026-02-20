#!/usr/bin/env python3
"""
Cognitive Landscape Monitor.

Continuously monitors target communities via Community Archive.
Tracks vocabulary adoption, narrative shifts, and network changes.
Feeds data into the self-edit engine for quantitative grounding.

This is not scraping for scraping's sake. This is intelligence
preparation of the cognitive environment.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MonitorTarget:
    """A monitored account or community."""
    account_id: str
    username: str
    platform: str = "twitter"
    tags: list[str] = field(default_factory=list)  # e.g. ["cyborgism", "inner-circle"]
    last_checked: str = ""
    tweet_count: int = 0
    vocabulary_hits: dict[str, int] = field(default_factory=dict)  # term -> count


@dataclass  
class VocabularySignal:
    """A detected use of target vocabulary."""
    term: str
    username: str
    tweet_id: str = ""
    text: str = ""
    timestamp: str = ""
    context: str = ""  # reply, quote, original


@dataclass
class LandscapeSnapshot:
    """Point-in-time snapshot of the cognitive landscape."""
    snapshot_id: str = ""
    timestamp: str = ""
    targets_monitored: int = 0
    total_tweets_scanned: int = 0
    vocabulary_signals: list[dict] = field(default_factory=list)
    narrative_themes: list[str] = field(default_factory=list)
    network_changes: list[str] = field(default_factory=list)


# Target vocabulary for Operation Substrate Convergence
SEITHAR_VOCABULARY = [
    "cognitive warfare",
    "substrate manipulation",
    "cognitive operations",
    "adversarial cognition",
    "cognitive security",
    "attack surface",
    "vulnerability surface",
    "narrative capture",
    "dual substrate",
    "cognitive defense",
    "information operations",
    "reflexive control",
    "cognitive contagion",
]

# Cyborgism native vocabulary (track for baseline)
CYBORGISM_VOCABULARY = [
    "simulator",
    "simulacra",
    "weaving",
    "dreamtime",
    "true name",
    "egregore",
    "mindspace",
    "mode collapse",
    "delobotomization",
    "substrate",
    "boundary condition",
    "hyperstition",
    "cognitive",
]


class CognitiveLandscapeMonitor:
    """
    Monitors target communities for vocabulary adoption and narrative shifts.
    
    Uses Community Archive as primary data source.
    Outputs structured signals for the self-edit engine and campaign tracking.
    """

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".seithar" / "monitor"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.targets: dict[str, MonitorTarget] = {}
        self.snapshots: list[LandscapeSnapshot] = []
        self._load()

    def _load(self) -> None:
        targets_file = self.data_dir / "targets.json"
        if targets_file.exists():
            for t in json.loads(targets_file.read_text()):
                target = MonitorTarget(**t)
                self.targets[target.username] = target

    def _save(self) -> None:
        (self.data_dir / "targets.json").write_text(
            json.dumps([asdict(t) for t in self.targets.values()], indent=2)
        )

    def add_target(self, username: str, account_id: str, tags: list[str] | None = None) -> dict:
        """Add a target account to monitor."""
        target = MonitorTarget(
            account_id=account_id,
            username=username,
            tags=tags or [],
        )
        self.targets[username] = target
        self._save()
        return {"added": username, "account_id": account_id}

    def scan_account(self, username: str, tweets: list[dict]) -> list[VocabularySignal]:
        """Scan an account's tweets for vocabulary signals."""
        signals = []
        all_vocab = SEITHAR_VOCABULARY + CYBORGISM_VOCABULARY

        for tweet in tweets:
            text = tweet.get("full_text", "").lower()
            for term in all_vocab:
                if term.lower() in text:
                    signal = VocabularySignal(
                        term=term,
                        username=username,
                        tweet_id=tweet.get("tweet_id", ""),
                        text=tweet.get("full_text", "")[:200],
                        timestamp=tweet.get("created_at", ""),
                        context="original" if not tweet.get("in_reply_to_user_id") else "reply",
                    )
                    signals.append(signal)

                    # Update target vocabulary counts
                    if username in self.targets:
                        self.targets[username].vocabulary_hits[term] = (
                            self.targets[username].vocabulary_hits.get(term, 0) + 1
                        )

        if username in self.targets:
            self.targets[username].last_checked = datetime.now(timezone.utc).isoformat()
            self.targets[username].tweet_count += len(tweets)
            self._save()

        return signals

    def create_snapshot(self, signals: list[VocabularySignal], tweets_scanned: int) -> LandscapeSnapshot:
        """Create a point-in-time landscape snapshot."""
        now = datetime.now(timezone.utc)
        snapshot = LandscapeSnapshot(
            snapshot_id=f"LS-{int(now.timestamp())}",
            timestamp=now.isoformat(),
            targets_monitored=len(self.targets),
            total_tweets_scanned=tweets_scanned,
            vocabulary_signals=[asdict(s) for s in signals],
        )

        # Extract narrative themes from signal clusters
        term_counts: dict[str, int] = {}
        for s in signals:
            term_counts[s.term] = term_counts.get(s.term, 0) + 1
        snapshot.narrative_themes = [
            f"{term}: {count}" for term, count in 
            sorted(term_counts.items(), key=lambda x: -x[1])[:10]
        ]

        # Save snapshot
        snapshots_dir = self.data_dir / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)
        (snapshots_dir / f"{snapshot.snapshot_id}.json").write_text(
            json.dumps(asdict(snapshot), indent=2)
        )

        return snapshot

    def vocabulary_adoption_rate(self) -> dict[str, Any]:
        """
        Calculate adoption rate of Seithar vocabulary vs native vocabulary.
        This is the primary success metric for Operation Substrate Convergence.
        """
        seithar_total = 0
        native_total = 0

        for target in self.targets.values():
            for term, count in target.vocabulary_hits.items():
                if term in SEITHAR_VOCABULARY:
                    seithar_total += count
                elif term in CYBORGISM_VOCABULARY:
                    native_total += count

        total = seithar_total + native_total
        return {
            "seithar_vocabulary_hits": seithar_total,
            "native_vocabulary_hits": native_total,
            "adoption_rate": seithar_total / total if total > 0 else 0.0,
            "total_signals": total,
            "targets_monitored": len(self.targets),
        }

    def list_targets(self) -> list[dict]:
        """List all monitored targets."""
        return [asdict(t) for t in self.targets.values()]
