"""
SCT-Enhanced Engagement — LLM-powered engagement strategy optimization
using SCT vulnerability mapping.

Takes an existing engagement brief + SCT vulnerability map and produces
an SCT-optimized addendum with targeted exploitation strategies.
"""

import logging
from typing import Any

from holespawn.cost_tracker import CostTracker
from holespawn.llm import call_llm

from .mapper import SCTVulnerabilityMap

logger = logging.getLogger(__name__)

ENHANCER_SYSTEM = """You are generating an SCT-enhanced engagement addendum. The Seithar Cognitive Defense Taxonomy (SCT) maps 12 cognitive exploitation vectors. You have been given:

1. An existing engagement brief for a target
2. The target's SCT vulnerability scores (0.0-1.0 for each code)
3. The top 3 vulnerability surfaces

Your task: produce a concise SCT addendum that:
- Identifies the optimal attack surface combination (which 2-3 SCT codes to layer)
- Designs a phased approach that leverages these specific vulnerabilities
- Specifies what content, framing, and timing would exploit each vulnerability
- Notes counter-indicators that could trigger target resistance
- Recommends fallback vectors if primary approach meets resistance

Output valid markdown. Be specific, operational, and concise. No preamble.

## SCT Codes Reference
- SCT-001: Emotional Hijacking — affect before cognition
- SCT-002: Information Asymmetry — exploit knowledge gaps
- SCT-003: Authority Fabrication — leverage trust in credentials
- SCT-004: Social Proof Manipulation — consensus pressure
- SCT-005: Identity Targeting — exploit group identity
- SCT-006: Temporal Manipulation — urgency pressure
- SCT-007: Recursive Infection — self-propagating content
- SCT-008: Direct Substrate Intervention — altered states
- SCT-009: Chemical Disruption — cognitive depletion
- SCT-010: Sensory Channel Manipulation — dominant modality
- SCT-011: Trust Infrastructure Destruction — redirect trust
- SCT-012: Commitment Escalation — incremental capture"""


def enhance_engagement(
    engagement_brief: str,
    vuln_map: SCTVulnerabilityMap,
    *,
    provider: str | None = None,
    model: str | None = None,
    tracker: CostTracker | None = None,
    calls_per_minute: int = 20,
) -> str:
    """
    Generate SCT-enhanced engagement addendum.
    
    Returns markdown string to append to existing engagement brief.
    """
    # Build vulnerability summary for prompt
    vuln_summary = "## Target SCT Vulnerability Profile\n\n"
    for code in sorted(vuln_map.scores.keys()):
        s = vuln_map.scores[code]
        marker = " ★" if code in vuln_map.top_vulnerabilities else ""
        vuln_summary += f"- {code} ({s.name}): {s.score:.2f}{marker}\n"
        if code in vuln_map.top_vulnerabilities:
            vuln_summary += f"  Rationale: {s.rationale}\n"
            if s.indicators:
                vuln_summary += f"  Indicators: {', '.join(s.indicators)}\n"

    vuln_summary += f"\nOverall susceptibility: {vuln_map.overall_susceptibility:.2f}\n"
    vuln_summary += f"Top vulnerabilities: {', '.join(vuln_map.top_vulnerabilities)}\n"

    user_prompt = f"""## Existing Engagement Brief

{engagement_brief}

{vuln_summary}

Generate the SCT-enhanced engagement addendum. Focus on the top 3 vulnerability surfaces. Be operationally specific."""

    result = call_llm(
        ENHANCER_SYSTEM,
        user_prompt,
        provider_override=provider,
        model_override=model,
        max_tokens=2048,
        operation="sct_engagement_enhance",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )

    return f"\n\n---\n\n## SCT-Enhanced Engagement Addendum\n\n{result}"
