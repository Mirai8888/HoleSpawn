"""
Cache profiles to avoid re-analyzing the same content.
Uses JSON (not pickle) for security. Writes are atomic.
"""

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from holespawn.profile import PsychologicalProfile


def _posts_signature(posts: list[str]) -> str:
    content = "".join(sorted(p.strip() for p in posts if p and p.strip()))
    return hashlib.md5(content.encode()).hexdigest()


def _path(key: str, cache_dir: Path) -> Path:
    return cache_dir / f"{key}.json"


def _profile_from_dict(data: dict[str, Any]) -> PsychologicalProfile:
    """Build PsychologicalProfile from JSON-loaded dict (themes as list of lists)."""
    data = dict(data)
    if "themes" in data:
        data["themes"] = [tuple(t) for t in data["themes"]]
    return PsychologicalProfile(**data)


class ProfileCache:
    """Cache PsychologicalProfile by content hash. JSON-backed, atomic writes."""

    def __init__(self, cache_dir: str | Path = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, posts: list[str]) -> PsychologicalProfile | None:
        key = _posts_signature(posts)
        path = _path(key, self.cache_dir)
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return _profile_from_dict(data)
        except (json.JSONDecodeError, ValueError, OSError, KeyError, TypeError):
            return None

    def set(self, posts: list[str], profile: PsychologicalProfile) -> None:
        key = _posts_signature(posts)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = _path(key, self.cache_dir)
        fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(asdict(profile), f)
            shutil.move(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        try:
            from loguru import logger
            logger.debug("Cached profile {}", key[:8])
        except ImportError:
            pass

    def clear(self) -> None:
        for p in self.cache_dir.glob("*.json"):
            if p.suffix == ".json" and ".tmp" not in p.name:
                try:
                    p.unlink()
                except OSError:
                    pass
        for p in self.cache_dir.glob("*.pkl"):
            try:
                p.unlink()
            except OSError:
                pass
