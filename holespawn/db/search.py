"""
Agenda-based search: descriptive query over stored profiles.
Returns ranked list of matching profiles for research/product understanding — no targeting.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

from holespawn.cost_tracker import CostTracker
from holespawn.llm import call_llm


def _profile_summary(row: tuple) -> str:
    """Build a short text summary from a profile row for LLM ranking."""
    try:
        matrix = json.loads(row[4]) if row[4] else {}
    except json.JSONDecodeError:
        matrix = {}
    themes = matrix.get("themes") or []
    theme_str = ", ".join(str(t[0]) for t in themes[:12]) if themes else ""
    interests = matrix.get("specific_interests") or []
    obsessions = matrix.get("obsessions") or []
    style = matrix.get("communication_style") or ""
    brief = (row[5] or "")[:500].strip()
    parts = [
        f"run_id: {row[2]}",
        f"username: {row[1]}",
        f"themes: {theme_str}",
        f"interests: {', '.join(interests[:10])}",
        f"obsessions: {', '.join(obsessions[:5])}",
        f"style: {style}",
    ]
    if brief:
        parts.append(f"brief_excerpt: {brief}")
    return "\n".join(parts)


SEARCH_SYSTEM = """You are a research assistant. You receive an **agenda** (a descriptive query or set of criteria) and a list of **profile summaries** (each with run_id, username, themes, interests, style, brief excerpt). Your task is to rank which profiles best match the agenda for **research or product understanding** — e.g. "who cares about X", "who is susceptible to framing Y", "which audiences align with topic Z". This is for analysis only, not for selecting targets for campaigns.

Output valid JSON only, no markdown or preamble. Format:
[
  {"run_id": "...", "rank": 1, "reason": "one sentence why this profile matches the agenda"},
  ...
]
Include every run_id that was provided, ordered by relevance (most relevant first). Keep reasons short and factual."""


def search_by_agenda(
    agenda: str,
    db_path: str | Path,
    *,
    limit: int = 20,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tracker: Optional[CostTracker] = None,
    calls_per_minute: int = 20,
) -> list[dict[str, Any]]:
    """
    Rank stored profiles by relevance to the agenda (descriptive query).
    Returns list of {"run_id", "output_dir", "source_username", "rank", "reason"}.
    For research/product understanding only — no targeting.
    """
    from pathlib import Path
    path = Path(db_path)
    if path.is_dir():
        path = path / "holespawn.sqlite"
    if not path.is_file():
        return []

    import sqlite3
    conn = sqlite3.connect(str(path))
    rows = conn.execute(
        """SELECT id, source_username, run_id, output_dir, behavioral_matrix, engagement_brief
           FROM profiles ORDER BY created_at DESC"""
    ).fetchall()
    conn.close()

    if not rows:
        return []

    # Cap how many we send to LLM
    rows = rows[: min(limit, 50)]
    summaries = []
    for r in rows:
        run_id = r[2]
        summary = _profile_summary(r)
        summaries.append(summary)

    user_content = f"""Agenda (descriptive query):\n{agenda}\n\nProfile summaries:\n"""
    user_content += "\n---\n".join(summaries)
    user_content += "\n\nOutput a JSON array of {run_id, rank, reason} for each profile, ordered by relevance."

    try:
        raw = call_llm(
            SEARCH_SYSTEM,
            user_content,
            provider_override=provider,
            model_override=model,
            max_tokens=4096,
            operation="agenda_search",
            tracker=tracker,
            calls_per_minute=calls_per_minute,
        )
    except Exception as e:
        log.warning("Agenda search LLM call failed: %s", e)
        return []

    # Parse JSON (strip markdown if present)
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        ranked = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(ranked, list):
        return []

    run_to_row = {r[2]: r for r in rows}
    result = []
    for i, item in enumerate(ranked[:limit]):
        run_id = item.get("run_id")
        if not run_id or run_id not in run_to_row:
            continue
        r = run_to_row[run_id]
        result.append({
            "run_id": run_id,
            "output_dir": r[3],
            "source_username": r[1],
            "rank": item.get("rank", i + 1),
            "reason": item.get("reason") or "",
        })
    return result