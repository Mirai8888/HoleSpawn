"""
Load and default configuration (config.yaml).
"""

from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "llm": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 4000,
        "temperature": 0.7,
    },
    "generation": {
        "max_retries": 3,
        "validation_enabled": True,
        "timeout_seconds": 60,
    },
    "deployment": {
        "auto_deploy": False,
        "platform": "netlify",
    },
    "costs": {
        "warn_threshold": 1.00,
        "max_cost": 5.00,
    },
    "output": {
        "base_dir": "outputs",
        "keep_last_n": 10,
    },
    "scraping": {
        "method": "archive",
        "apify": {
            "max_tweets": 200,
            "include_retweets": False,
        },
    },
    "rate_limit": {
        "calls_per_minute": 20,
    },
}


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load config from YAML file. Creates default config.yaml if missing."""
    try:
        import yaml
    except ImportError:
        return DEFAULT_CONFIG.copy()

    path = Path(config_path) if config_path else Path("config.yaml")
    if not path.is_absolute():
        root = Path(__file__).resolve().parent.parent
        candidate = root / path
        if candidate.exists():
            path = candidate
        else:
            path = Path.cwd() / path

    if not path.exists():
        _ensure_dir(path.parent)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True)
        return DEFAULT_CONFIG.copy()

    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}

    # Deep merge with defaults so new keys appear
    def merge(base: dict, override: dict) -> dict:
        out = base.copy()
        for k, v in override.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = merge(out[k], v)
            else:
                out[k] = v
        return out

    return merge(DEFAULT_CONFIG, loaded)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
