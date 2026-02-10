"""
Run delivery pipeline: load run dir → generate message → send to channel.
"""

import logging
from pathlib import Path
from typing import Any

from holespawn.cost_tracker import CostTracker

from .channels import deliver
from .generator import generate_message

logger = logging.getLogger(__name__)


def run_delivery(
    output_dir: str | Path,
    *,
    channel: str = "file",
    out_path: str | Path | None = None,
    phase_hint: str | None = None,
    tracker: CostTracker | None = None,
) -> dict[str, Any]:
    """
    Load profile + protocol from output_dir, generate one message, deliver to channel.

    channel: "file" | "stdout" | "twitter_dm" | "discord_dm" | "email" (latter three: return text only, no send)
    out_path: for channel=file, directory to write {run_id}_message.txt (default: delivery_out).
    Returns dict: { "payload": {...}, "delivered_to": path or "stdout" or channel name }.
    """
    root = Path(output_dir)
    run_id = root.name
    out_dir = Path(out_path) if out_path else Path("delivery_out")

    payload = generate_message(
        root,
        phase_hint=phase_hint,
        channel_hint=channel,
        tracker=tracker,
    )
    delivered = deliver(payload, channel, out_dir=out_dir, run_id=run_id)
    return {"payload": payload, "delivered_to": delivered}
