"""Build a psychological/behavioral profile from social text."""

from .analyzer import PsychologicalProfile, build_profile
from .substrate_detector import SubstrateSignal, detect_substrate

__all__ = ["build_profile", "PsychologicalProfile", "detect_substrate", "SubstrateSignal"]
