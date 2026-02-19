"""
Stage 5: Deploy — Delivery through the right voice and platform.

Wraps holespawn.delivery + holespawn.network.moltbook_poster
plus persona selection for platform-appropriate delivery.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class Deployment:
    """Record of a deployed payload."""
    target: str
    platform: str = ""
    persona: str = ""
    channel: str = ""
    payload_hash: str = ""
    status: str = "pending"
    delivery_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def run_deploy(armed_payload, platform: str = "twitter",
               persona: str = "default", config: dict | None = None) -> Deployment:
    """Deploy armed payload through specified platform and persona.

    Attempts to use holespawn.delivery if available.
    """
    config = config or {}
    handle = getattr(armed_payload, "target", str(armed_payload))
    deployment = Deployment(target=handle, platform=platform, persona=persona)

    content = getattr(armed_payload, "content", "")

    # Try holespawn delivery system
    try:
        from holespawn.delivery.channels import deliver as _deliver
        result = _deliver(channel="stdout", payload={"target": handle, "content": content})
        if not isinstance(result, dict):
            result = {"status": "ok"}
        deployment.status = "delivered"
        deployment.delivery_id = result.get("id", "")
        deployment.raw = result
        logger.info("Deployed to %s via %s as %s", handle, platform, persona)
    except ImportError:
        logger.warning("holespawn.delivery not available; dry-run mode")
        deployment.status = "dry_run"
        deployment.raw = {"content": content, "mode": "dry_run"}

    # Try moltbook posting if platform matches
    if platform == "moltbook":
        try:
            from holespawn.network.moltbook_poster import post
            post(target=handle, content=content)
            deployment.channel = "moltbook"
        except ImportError:
            logger.warning("moltbook_poster not available")

    return deployment
