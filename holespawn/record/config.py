"""Load subjects.yaml: list of subjects to record (handle/server, source, interval)."""

from pathlib import Path

import yaml


def load_subjects(config_path: str | Path | None = None) -> list[dict]:
    """
    Load subjects from YAML. Each subject: handle (twitter) or server (discord), source, interval.
    Returns list of dicts with keys handle|server, source ('twitter'|'discord'), interval ('daily'|'weekly').
    """
    path = Path(config_path or "subjects.yaml")
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    subjects = raw.get("subjects") or []
    out = []
    for s in subjects:
        if not isinstance(s, dict):
            continue
        source = (s.get("source") or "twitter").lower().strip()
        if source not in ("twitter", "discord"):
            continue
        interval = (s.get("interval") or "daily").lower().strip()
        if source == "twitter":
            handle = (s.get("handle") or "").strip() or None
            if handle:
                out.append({"handle": handle, "source": "twitter", "interval": interval})
        else:
            server = (s.get("server") or "").strip() or None
            if server:
                out.append({"server": server, "source": "discord", "interval": interval})
    return out
