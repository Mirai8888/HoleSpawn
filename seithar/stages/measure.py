"""
Stage 6: Measure — Track absorption via network/influence analysis.

Wraps holespawn.network.influence_flow + holespawn.network.temporal
to measure the effect of a deployment.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class Measurement:
    """Measurement of deployment effectiveness."""
    target: str
    deployment_id: str = ""
    absorption_score: float = 0.0
    amplification: float = 0.0
    narrative_shift: float = 0.0
    network_delta: dict[str, Any] = field(default_factory=dict)
    temporal_indicators: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def run_measure(deployment, config: dict | None = None) -> Measurement:
    """Measure the effect of a deployment.

    Attempts to use holespawn influence_flow and temporal modules.
    """
    config = config or {}
    handle = getattr(deployment, "target", str(deployment))
    dep_id = getattr(deployment, "delivery_id", "")
    measurement = Measurement(target=handle, deployment_id=dep_id)

    # Try influence flow analysis
    try:
        from holespawn.network.influence_flow import (
            find_narrative_seeds,
            amplification_chains,
            composite_influence_score,
        )
        # Would need a graph — this is the integration point
        logger.info("influence_flow available for %s", handle)
        measurement.raw["influence_flow_available"] = True
    except ImportError:
        logger.warning("influence_flow not available")
        measurement.raw["influence_flow_available"] = False

    # Try temporal analysis
    try:
        from holespawn.temporal.series import TimeSeries
        logger.info("temporal analysis available for %s", handle)
        measurement.raw["temporal_available"] = True
    except ImportError:
        logger.warning("temporal module not available")
        measurement.raw["temporal_available"] = False

    return measurement
