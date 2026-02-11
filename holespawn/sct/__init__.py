"""
SCT — Seithar Cognitive Defense Taxonomy integration.

Maps psychological profiles to SCT vulnerability surfaces (SCT-001 through SCT-012).
Provides algorithmic vulnerability scoring and LLM-enhanced engagement optimization.
"""

from .mapper import SCTMapper, SCTVulnerabilityMap
from .report import generate_sct_report

__all__ = ["SCTMapper", "SCTVulnerabilityMap", "generate_sct_report"]
