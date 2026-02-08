"""
Persist profiles and network reports to SQLite after run.
"""

import json
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_username TEXT NOT NULL,
    canonical_handle TEXT,
    run_id TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    behavioral_matrix TEXT NOT NULL,
    engagement_brief TEXT,
    created_at TEXT NOT NULL,
    data_source TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_canonical_handle ON profiles(canonical_handle);

CREATE TABLE IF NOT EXISTS network_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    output_dir TEXT NOT NULL,
    report_json TEXT NOT NULL,
    brief_text TEXT,
    created_at TEXT NOT NULL,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_profiles_username ON profiles(source_username);
CREATE INDEX IF NOT EXISTS idx_profiles_created ON profiles(created_at);
CREATE INDEX IF NOT EXISTS idx_network_created ON network_reports(created_at);
"""


def _db_path(path: str | Path) -> Path:
    p = Path(path)
    if p.suffix.lower() != ".sqlite" and p.suffix.lower() != ".db":
        p = p / "holespawn.sqlite"
    return p


def _normalize_handle(username: str) -> str:
    """Normalize X handle for dedup: lowercase, strip @ and whitespace."""
    s = (username or "").strip().lstrip("@").lower()
    return s or "unknown"


def init_db(db_path: str | Path) -> None:
    """Create DB and tables if they don't exist. Migrates existing DBs to add canonical_handle."""
    path = _db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3

    with sqlite3.connect(str(path)) as conn:
        conn.executescript(_SCHEMA)
        try:
            conn.execute("ALTER TABLE profiles ADD COLUMN canonical_handle TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "UPDATE profiles SET canonical_handle = lower(trim(source_username)) WHERE canonical_handle IS NULL"
            )
            conn.execute(
                "UPDATE profiles SET canonical_handle = 'unknown' WHERE canonical_handle IS NULL OR trim(canonical_handle) = ''"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "DELETE FROM profiles WHERE id NOT IN (SELECT max(id) FROM profiles GROUP BY coalesce(canonical_handle, 'unknown'))"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_canonical_handle ON profiles(canonical_handle)"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass


def store_profile(
    run_dir: str | Path,
    db_path: str | Path,
) -> str | None:
    """
    Read behavioral_matrix.json, binding_protocol.md, metadata.json from run_dir
    and insert into profiles table. Returns run_id if stored, None if skipped (missing data).
    """
    run_dir = Path(run_dir)
    db_path = _db_path(db_path)

    matrix_path = run_dir / "behavioral_matrix.json"
    if not matrix_path.is_file():
        matrix_path = run_dir / "profile.json"
    metadata_path = run_dir / "metadata.json"
    if not matrix_path.is_file() or not metadata_path.is_file():
        return None

    matrix_text = matrix_path.read_text(encoding="utf-8")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    run_id = run_dir.name
    output_dir = str(run_dir.resolve())
    username = metadata.get("username", "unknown")
    data_source = metadata.get("data_source", "")

    brief_path = run_dir / "binding_protocol.md"
    if not brief_path.is_file():
        brief_path = run_dir / "engagement_brief.md"
    engagement_brief = brief_path.read_text(encoding="utf-8") if brief_path.is_file() else None
    created_at = metadata.get("generated_at", "")
    canonical_handle = _normalize_handle(username)

    import sqlite3

    init_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """INSERT INTO profiles
               (source_username, canonical_handle, run_id, output_dir, behavioral_matrix, engagement_brief, created_at, data_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(canonical_handle) DO UPDATE SET
                 source_username = excluded.source_username,
                 run_id = excluded.run_id,
                 output_dir = excluded.output_dir,
                 behavioral_matrix = excluded.behavioral_matrix,
                 engagement_brief = excluded.engagement_brief,
                 created_at = excluded.created_at,
                 data_source = excluded.data_source
            """,
            (
                username,
                canonical_handle,
                run_id,
                output_dir,
                matrix_text,
                engagement_brief,
                created_at,
                data_source,
            ),
        )
        conn.commit()
    return run_id


def store_network_report(
    run_id: str,
    output_dir: str | Path,
    report_json: str,
    brief_text: str | None,
    db_path: str | Path,
    source: str = "file",
) -> None:
    """Insert a network analysis report and optional brief into network_reports."""
    from datetime import datetime

    db_path = _db_path(db_path)
    output_dir = str(Path(output_dir).resolve())
    created_at = datetime.utcnow().isoformat() + "Z"

    import sqlite3

    init_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO network_reports
               (run_id, output_dir, report_json, brief_text, created_at, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, output_dir, report_json, brief_text, created_at, source),
        )
        conn.commit()
