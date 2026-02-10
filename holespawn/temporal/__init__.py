"""
Temporal NLP over recordings: VADER + theme extraction per time window.
No LLM. Output: time series for sparklines, drift metrics (influence signature).
"""

from .query import list_recordings
from .series import build_series, compute_signature

__all__ = ["list_recordings", "build_series", "compute_signature"]
