"""
Cache profiles to avoid re-analyzing the same content.
"""

import hashlib
import pickle
from pathlib import Path
from typing import Any

from holespawn.profile import PsychologicalProfile


def _posts_signature(posts: list[str]) -> str:
    content = "".join(sorted(p.strip() for p in posts if p and p.strip()))
    return hashlib.md5(content.encode()).hexdigest()


class ProfileCache:
    """Cache PsychologicalProfile by content hash."""

    def __init__(self, cache_dir: str | Path = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, posts: list[str]) -> PsychologicalProfile | None:
        key = _posts_signature(posts)
        path = self.cache_dir / f"{key}.pkl"
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def set(self, posts: list[str], profile: PsychologicalProfile) -> None:
        key = _posts_signature(posts)
        path = self.cache_dir / f"{key}.pkl"
        with open(path, "wb") as f:
            pickle.dump(profile, f)
        try:
            from loguru import logger
            logger.debug("Cached profile {}", key[:8])
        except ImportError:
            pass

    def clear(self) -> None:
        for p in self.cache_dir.glob("*.pkl"):
            try:
                p.unlink()
            except OSError:
                pass
