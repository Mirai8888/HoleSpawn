"""
Delivery channels: where generated content goes.
v1: file, stdout only. Future: twitter_dm, discord_dm, email (stub).
"""

from pathlib import Path
from typing import Any


def deliver_to_file(payload: dict[str, Any], out_dir: str | Path, run_id: str) -> str:
    """Write payload text to out_dir/{run_id}_message.txt. Returns path written."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    safe_id = run_id.replace("/", "_").replace("\\", "_")[:80]
    path = root / f"{safe_id}_message.txt"
    text = payload.get("text", "")
    path.write_text(text, encoding="utf-8")
    return str(path)


def deliver_to_stdout(payload: dict[str, Any]) -> str:
    """Return the message text for caller to print. No side effects."""
    return payload.get("text", "")


def deliver(
    payload: dict[str, Any],
    channel: str,
    *,
    out_dir: str | Path | None = None,
    run_id: str = "run",
) -> str:
    """
    Dispatch to channel. Returns path (file) or text (stdout).
    twitter_dm / discord_dm / email: return payload text only (no send in v1).
    """
    if channel == "file":
        if not out_dir:
            out_dir = Path("delivery_out")
        return deliver_to_file(payload, out_dir, run_id)
    if channel == "stdout":
        return deliver_to_stdout(payload)
    # Stub: other channels just return text; no actual send
    return payload.get("text", "")
