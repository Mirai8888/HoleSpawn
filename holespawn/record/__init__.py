"""
Active recording: time-stamped snapshots of Twitter/Discord ingest for temporal analysis.
Config: subjects.yaml. Storage: recordings/{source}/{subject_id}/YYYYMMDD_HHMMSS.json + SQLite index.
"""

from .config import load_subjects
from .recorder import record_all

__all__ = ["load_subjects", "record_all"]
