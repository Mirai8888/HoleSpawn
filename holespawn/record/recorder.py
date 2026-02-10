"""
Record one run: for each subject in config, fetch (Twitter via self-hosted scraper), write JSON, update SQLite index.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from holespawn.ingest.apify_twitter import fetch_twitter_apify_raw

from .config import load_subjects


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _init_index(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            file_path TEXT NOT NULL,
            source_type TEXT NOT NULL,
            record_count INTEGER NOT NULL,
            UNIQUE(subject_id, timestamp)
        )
        """
    )
    conn.commit()
    conn.close()


def _insert_record(db_path: Path, subject_id: str, timestamp: str, file_path: str, source_type: str, record_count: int) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO recordings (subject_id, timestamp, file_path, source_type, record_count) VALUES (?, ?, ?, ?, ?)",
        (subject_id, timestamp, file_path, source_type, record_count),
    )
    conn.commit()
    conn.close()


def _record_twitter(handle: str, recordings_root: Path, db_path: Path, max_tweets: int = 500) -> bool:
    """Fetch Twitter via scraper, write raw JSON, index. Returns True if recorded."""
    raw = fetch_twitter_apify_raw(handle, max_tweets=max_tweets)
    if raw is None:
        return False
    subject_id = handle if handle.startswith("@") else f"@{handle}"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    subdir = recordings_root / "twitter" / subject_id
    _ensure_dir(subdir)
    file_path = subdir / f"{timestamp}.json"
    def _json_default(o):  # noqa: B008
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=None, default=_json_default)
    rel_path = str(file_path.relative_to(recordings_root))
    _insert_record(db_path, subject_id, timestamp, rel_path, "twitter", len(raw))
    return True


def _record_discord(_server: str, _recordings_root: Path, _db_path: Path) -> bool:
    """Stub: Discord recording not yet implemented. Requires Discord API or export pipeline."""
    return False


def record_all(
    config_path: str | Path | None = None,
    recordings_dir: str | Path | None = None,
    max_tweets_per_user: int = 500,
) -> dict[str, int]:
    """
    Load subjects, record each (Twitter via scraper, Discord stubbed). Returns counts: recorded, skipped, failed.
    """
    import logging
    logger = logging.getLogger(__name__)

    root = Path(recordings_dir or "recordings")
    db_path = root / "recordings.db"
    _ensure_dir(root)
    _init_index(db_path)

    subjects = load_subjects(config_path)
    if not subjects:
        logger.warning("No subjects in config (subjects.yaml). Nothing to record.")
        return {"recorded": 0, "skipped": 0, "failed": 0}

    recorded = 0
    failed = 0
    for s in subjects:
        source = s.get("source", "twitter")
        if source == "twitter":
            handle = s.get("handle", "")
            if _record_twitter(handle, root, db_path, max_tweets=max_tweets_per_user):
                recorded += 1
                logger.info("Recorded @%s", handle.lstrip("@"))
            else:
                failed += 1
                logger.warning("Failed to record @%s (no data or scraper error)", handle.lstrip("@"))
        elif source == "discord":
            if _record_discord(s.get("server", ""), root, db_path):
                recorded += 1
            else:
                failed += 1
                logger.warning("Discord recording not implemented; skipped server %s", s.get("server"))

    return {"recorded": recorded, "skipped": 0, "failed": failed}
