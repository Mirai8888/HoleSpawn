"""
Stage 3: Plan — Chain modeling and vector selection.

Wraps ThreadMap chain modeling to identify optimal intervention
vectors based on scan results and target profile.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import logging

from seithar.taxonomy import SCT_TAXONOMY

logger = logging.getLogger(__name__)


@dataclass
class OperationPlan:
    """Selected vectors and chain model for the operation."""
    target: str
    vectors: list[dict[str, Any]] = field(default_factory=list)
    chain_model: dict[str, Any] = field(default_factory=dict)
    priority_techniques: list[str] = field(default_factory=list)
    intervention_points: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def run_plan(scan_results, target_profile=None, config: dict | None = None) -> OperationPlan:
    """Generate operation plan from scan results.

    Attempts to use ThreadMap for chain modeling if available.
    Falls back to heuristic vector selection based on detected vulnerabilities.
    """
    config = config or {}
    handle = getattr(scan_results, "target", str(scan_results))
    plan = OperationPlan(target=handle)

    detections = getattr(scan_results, "detections", [])

    # Try ThreadMap chain modeling
    try:
        from threadmap.chain import HybridChain
        from threadmap.analysis import intervention_ranking, find_chokepoints

        chain = HybridChain(
            chain_id=f"op-{handle}",
            name=f"Operation against {handle}",
        )
        # If ThreadMap is available, build chain from detections
        # (Actual chain construction depends on ThreadMap entity setup)
        plan.raw["threadmap_available"] = True
        logger.info("ThreadMap available for chain modeling")
    except ImportError:
        logger.warning("ThreadMap not available; using heuristic planning")
        plan.raw["threadmap_available"] = False

    # Heuristic vector selection from scan detections
    vulnerabilities = getattr(target_profile, "vulnerabilities", []) if target_profile else []

    for det in sorted(detections, key=lambda d: d.get("confidence", 0), reverse=True):
        code = det.get("code", "")
        sct = SCT_TAXONOMY.get(code)
        if sct:
            plan.vectors.append({
                "code": code,
                "name": sct.name,
                "confidence": det.get("confidence", 0),
                "techniques": sct.operational_techniques,
            })
            plan.priority_techniques.extend(sct.operational_techniques[:2])

    # If we have profile vulnerabilities, cross-reference
    if vulnerabilities:
        plan.raw["vulnerability_overlap"] = vulnerabilities

    return plan
