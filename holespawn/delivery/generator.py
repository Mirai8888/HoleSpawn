"""
Generate one delivery unit (e.g. DM-style message) from binding protocol + profile context.
"""

import json
import logging
from pathlib import Path
from typing import Any

from holespawn.cost_tracker import CostTracker
from holespawn.llm import call_llm

logger = logging.getLogger(__name__)

SYSTEM = """You are generating a single outbound message for a specific person, based on a psychological and approach brief (binding protocol).

Your task: write ONE short message (e.g. suitable for a first DM or email) that:
- Uses the suggested trust hooks and approach ideas from the protocol
- Matches the tone and style indicated (e.g. technical, cryptic, anti-establishment)
- Does not sound like marketing or persuasion; sounds like a genuine peer reaching out
- Contains no links unless the protocol explicitly suggests one
- Is concise: a few lines or one short paragraph

Output only the message text. No preamble, no "Here's a message:", no explanation."""


def _load_profile_summary(output_dir: Path) -> dict[str, Any]:
    """Load behavioral_matrix.json and return a short summary for context."""
    path = output_dir / "behavioral_matrix.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    themes = data.get("themes", [])[:10]
    theme_str = ", ".join(str(t[0]) for t in themes if isinstance(t, (list, tuple)) and len(t) >= 1)
    return {
        "communication_style": data.get("communication_style", ""),
        "sample_phrases": data.get("sample_phrases", [])[:5],
        "top_themes": theme_str,
        "specific_interests": data.get("specific_interests", [])[:8],
    }


def generate_message(
    output_dir: str | Path,
    *,
    phase_hint: str | None = None,
    channel_hint: str = "twitter_dm",
    max_tokens: int = 512,
    tracker: CostTracker | None = None,
) -> dict[str, Any]:
    """
    Load binding protocol (and optional profile summary) from output_dir; call LLM to generate one message.

    Returns dict with keys: channel, text, (optional) subject for email.
    """
    root = Path(output_dir)
    protocol_path = root / "binding_protocol.md"
    if not protocol_path.exists():
        raise FileNotFoundError(f"binding_protocol.md not found in {root}")

    protocol_text = protocol_path.read_text(encoding="utf-8")
    profile_summary = _load_profile_summary(root)

    user_parts = [
        "## Binding protocol (approach brief)\n\n",
        protocol_text,
    ]
    if profile_summary:
        user_parts.append("\n\n## Profile context (for tone match)\n\n")
        user_parts.append(json.dumps(profile_summary, indent=2, ensure_ascii=False))
    if phase_hint:
        user_parts.append(f"\n\n## Phase hint\n\n{phase_hint}")
    user_parts.append("\n\nGenerate one message only (no preamble).")

    user_content = "".join(user_parts)
    text = call_llm(
        SYSTEM,
        user_content,
        max_tokens=max_tokens,
        operation="delivery_generate",
        tracker=tracker,
    )
    text = (text or "").strip()
    return {"channel": channel_hint, "text": text}
