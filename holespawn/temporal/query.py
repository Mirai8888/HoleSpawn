"""
Query recordings index (SQLite) for a subject; return rows for loading JSON snapshots.
"""

import sqlite3
from pathlib import Path


def list_recordings(
    db_path: str | Path,
    subject_id: str,
    *,
    source_type: str | None = None,
    limit: int | None = None,
    order_desc: bool = True,
) -> list[dict]:
    """
    Return recording rows for subject_id from recordings.db.
    Each row: subject_id, timestamp, file_path, source_type, record_count.
    """
    path = Path(db_path)
    if not path.is_file():
        return []

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT subject_id, timestamp, file_path, source_type, record_count FROM recordings WHERE subject_id = ?"
        + (" AND source_type = ?" if source_type else "")
        + " ORDER BY timestamp " + ("DESC" if order_desc else "ASC")
        + (" LIMIT ?" if limit is not None else ""),
        (subject_id,) + ((source_type,) if source_type else ()) + ((limit,) if limit is not None else ()),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
