"""
Temporal NLP over recordings (Phase 3) and cohort aggregation (Phase 4).

- Phase 3: per-subject time series from recordings.db + JSON snapshots:
  VADER + theme extraction per window → influence signature.
- Phase 4: cohort aggregation over inner circle: aggregate time series and
  drift metrics. LLM summarization is layered on top of this JSON.
"""

from .query import list_recordings, list_subjects
from .series import build_series, compute_signature
from .cohort import build_cohort_results, aggregate_cohort

__all__ = [
    "list_recordings",
    "list_subjects",
    "build_series",
    "compute_signature",
    "build_cohort_results",
    "aggregate_cohort",
]
