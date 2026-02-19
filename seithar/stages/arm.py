"""
Stage 4: Arm — Payload generation adapted to target vulnerabilities.

Wraps holespawn.generator + autoprompt concepts to create
engagement payloads tuned to the target's psychological profile.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class ArmedPayload:
    """A payload ready for deployment."""
    target: str
    content: str = ""
    technique_codes: list[str] = field(default_factory=list)
    persona: str = ""
    platform_adaptations: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def run_arm(plan, target_profile=None, config: dict | None = None) -> ArmedPayload:
    """Generate armed payload from operation plan and target profile.

    Attempts to use holespawn.generator if available.
    """
    config = config or {}
    handle = getattr(plan, "target", str(plan))
    payload = ArmedPayload(target=handle)

    vectors = getattr(plan, "vectors", [])
    payload.technique_codes = [v.get("code", "") for v in vectors]

    # Try AI rabbit hole generator
    try:
        from holespawn.generator import AIRabbitHoleGenerator
        profile_data = getattr(target_profile, "psychological", {}) if target_profile else {}
        generator = AIRabbitHoleGenerator()
        result = generator.generate(
            profile=profile_data,
            techniques=payload.technique_codes,
        )
        payload.content = result.get("content", "")
        payload.raw["generator"] = "ai_rabbit_hole"
        logger.info("Generated payload via AIRabbitHoleGenerator")
    except (ImportError, Exception) as e:
        logger.warning("AIRabbitHoleGenerator not available: %s", e)
        # Stub payload for pipeline continuity
        techniques_str = ", ".join(payload.technique_codes[:3])
        payload.content = f"[Payload stub for {handle} using {techniques_str}]"
        payload.raw["generator"] = "stub"

    return payload
