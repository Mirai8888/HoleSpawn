"""
File-based cache for scraper responses. TTL by operation type.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def get_cache_dir() -> Path:
    import os
    p = os.environ.get("SCRAPER_CACHE_DIR")
    if p:
        return Path(p)
    return Path(__file__).resolve().parent.parent.parent / "data" / "scraper_cache"


class ScrapeCache:
    """Cache by (operation, username, params_hash)."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or get_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, operation: str, username: str, **params: object) -> str:
        params_str = json.dumps(params, sort_keys=True, default=str)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        safe_user = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
        return f"{operation}_{safe_user}_{params_hash}"

    def get(
        self,
        operation: str,
        username: str,
        ttl_hours: float = 1,
        **params: object,
    ) -> object | None:
        """Return cached payload if exists and not expired. None otherwise."""
        key = self._key(operation, username, **params)
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        cached_at_str = data.get("cached_at", "2000-01-01T00:00:00")
        cached_at = datetime.fromisoformat(cached_at_str)
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - cached_at > timedelta(hours=ttl_hours):
            try:
                path.unlink()
            except OSError:
                pass
            return None
        return data.get("payload")

    def set(
        self,
        operation: str,
        username: str,
        payload: object,
        **params: object,
    ) -> None:
        """Cache a response."""
        key = self._key(operation, username, **params)
        path = self.cache_dir / f"{key}.json"
        data = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "username": username,
            "payload": payload,
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
