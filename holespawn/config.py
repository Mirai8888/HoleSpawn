"""
Load and default configuration (config.yaml).
Local model presets for OpenAI-compatible endpoints (Ollama, LM Studio, vLLM).
"""

import os
from pathlib import Path
from typing import Any

# Local model presets (OpenAI-compatible API)
LOCAL_MODEL_PRESETS: dict[str, dict[str, Any]] = {
    "ollama-llama3": {
        "api_base": "http://localhost:11434/v1",
        "model": "llama3.1:8b",
        "provider": "openai_compatible",
        "notes": "Good balance of speed and quality",
    },
    "ollama-mistral": {
        "api_base": "http://localhost:11434/v1",
        "model": "mistral:7b",
        "provider": "openai_compatible",
        "notes": "Faster, lighter weight",
    },
    "lmstudio": {
        "api_base": "http://localhost:1234/v1",
        "model": "local-model",
        "provider": "openai_compatible",
        "notes": "LM Studio default endpoint",
    },
    "vllm": {
        "api_base": "http://localhost:8000/v1",
        "model": "meta-llama/Meta-Llama-3-8B-Instruct",
        "provider": "openai_compatible",
        "notes": "Production local inference",
    },
}


def get_llm_config(
    preset: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """
    Get LLM configuration for local or cloud models.
    Priority: explicit params > preset > env vars (LLM_API_BASE, LLM_MODEL) > default (Claude).
    """
    if preset and preset in LOCAL_MODEL_PRESETS:
        config = dict(LOCAL_MODEL_PRESETS[preset])
    else:
        config = {
            "api_base": api_base or os.getenv("LLM_API_BASE"),
            "model": model or os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            "provider": provider or "anthropic",
        }
    if api_base is not None:
        config["api_base"] = api_base
    if model is not None:
        config["model"] = model
    if config.get("api_base"):
        config["provider"] = config.get("provider") or "openai_compatible"
    return config


DEFAULT_CONFIG: dict[str, Any] = {
    "llm": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4000,
        "temperature": 0.7,
    },
    "generation": {
        "max_retries": 3,
        "validation_enabled": True,
        "max_validation_retries": 3,
        "timeout_seconds": 60,
        "voice_matching": {
            "enforce_vocabulary_usage": True,
            "min_vocabulary_match": 0.2,
            "block_generic_cryptic": True,
            "require_interest_relevance": True,
        },
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
