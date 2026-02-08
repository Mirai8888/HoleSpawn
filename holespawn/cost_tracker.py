"""
Track LLM token usage and estimated cost.
Reads COST_WARN_THRESHOLD and COST_MAX_THRESHOLD from env if not passed.
Pricing can be overridden via a YAML config file; otherwise uses built-in defaults.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


class CostExceededError(Exception):
    """Raised when estimated cost exceeds max_cost and abort_on_max is True."""

    def __init__(self, current: float, max_cost: float):
        self.current = current
        self.max_cost = max_cost
        super().__init__(f"Cost ${current:.2f} exceeded max ${max_cost:.2f}")


# Update this when pricing data is revised (warns if > 90 days old)
PRICING_LAST_UPDATED = "2025-02-01"

# Per 1M tokens (input, output). Override via load_pricing(config_path).
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-flash": (0.15, 0.60),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-sonnet-3.5": (3.00, 15.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),  # deprecated Oct 2025
    "claude-3-haiku": (0.25, 1.25),
}

# Keep PRICING as alias for backward compatibility
PRICING = DEFAULT_PRICING


def check_pricing_freshness() -> None:
    """Warn if built-in pricing data is old and may be inaccurate."""
    try:
        last = date.fromisoformat(PRICING_LAST_UPDATED)
        days_old = (date.today() - last).days
        if days_old > 90:
            try:
                from loguru import logger

                logger.warning(
                    "LLM pricing data is {} days old and may be inaccurate. "
                    "Check for updates or set a pricing config file.",
                    days_old,
                )
            except ImportError:
                pass
    except (ValueError, TypeError):
        pass


def load_pricing(config_path: Path | None = None) -> dict[str, tuple[float, float]]:
    """Load pricing from YAML config if path exists; else return default. Config keys: model name, values: {input, output} per 1M tokens. Loaded entries override defaults."""
    out = DEFAULT_PRICING.copy()
    if config_path and Path(config_path).exists() and yaml is not None:
        try:
            with open(config_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, dict):
                        inp = float(v.get("input", 0))
                        out_val = float(v.get("output", 0))
                        out[str(k).lower().strip()] = (inp, out_val)
        except Exception:
            pass
    return out


def _normalize_model(name: str, pricing: dict[str, tuple[float, float]]) -> str:
    """Map model name to a key in pricing dict."""
    name = (name or "").lower()
    for key in pricing:
        if key in name or name in key:
            return key
    return "claude-sonnet-4-20250514"  # fallback


def _float_env(name: str, default: float) -> float:
    try:
        v = os.getenv(name)
        if v is not None and v.strip():
            return float(v.strip())
    except ValueError:
        pass
    return default


class CostTracker:
    """Track LLM token usage and costs. Uses COST_WARN_THRESHOLD / COST_MAX_THRESHOLD from env if not passed."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        warn_threshold: float | None = None,
        max_cost: float | None = None,
        abort_on_max: bool = False,
        pricing_config: Path | None = None,
    ):
        self.model = model
        self.pricing = load_pricing(pricing_config)
        self._pricing_key = _normalize_model(model, self.pricing)
        check_pricing_freshness()
        self.warn_threshold = (
            warn_threshold
            if warn_threshold is not None
            else _float_env("COST_WARN_THRESHOLD", 1.00)
        )
        self.max_cost = max_cost if max_cost is not None else _float_env("COST_MAX_THRESHOLD", 5.00)
        if self.warn_threshold > self.max_cost:
            raise ValueError(
                f"warn_threshold ({self.warn_threshold}) must be <= max_cost ({self.max_cost}). "
                "Warnings would never trigger otherwise."
            )
        if self.warn_threshold < 0 or self.max_cost < 0:
            raise ValueError("Cost thresholds must be non-negative")
        self.abort_on_max = abort_on_max
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls: list[dict[str, Any]] = []

    def add_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        operation: str = "",
    ) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls.append(
            {
                "operation": operation,
                "input": input_tokens,
                "output": output_tokens,
                "timestamp": datetime.now().isoformat(),
            }
        )
        cost = self.get_cost()
        if cost > self.warn_threshold:
            try:
                from loguru import logger

                logger.warning(
                    "Cost exceeded ${:.2f} threshold (current: ${:.4f})",
                    self.warn_threshold,
                    cost,
                )
            except ImportError:
                pass
        if cost > self.max_cost:
            try:
                from loguru import logger

                logger.error(
                    "Cost exceeded max ${:.2f} (current: ${:.4f}). Consider stopping.",
                    self.max_cost,
                    cost,
                )
            except ImportError:
                pass
            if self.abort_on_max:
                raise CostExceededError(cost, self.max_cost)

    def get_cost(self) -> float:
        prices = self.pricing.get(
            self._pricing_key,
            self.pricing.get("claude-sonnet-4-20250514", (3.00, 15.00)),
        )
        input_cost, output_cost = prices
        return (self.input_tokens * input_cost / 1_000_000) + (
            self.output_tokens * output_cost / 1_000_000
        )

    def print_summary(self) -> None:
        cost = self.get_cost()
        print("\nAPI usage summary")
        print(f"   Model: {self.model}")
        print(f"   Input tokens:  {self.input_tokens:,}")
        print(f"   Output tokens: {self.output_tokens:,}")
        print(f"   Estimated cost: ${cost:.4f}")
        print(f"   API calls: {len(self.calls)}")

    def save_to_file(self, output_dir: Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "cost_breakdown.json"
        data = {
            "model": self.model,
            "total_input_tokens": self.input_tokens,
            "total_output_tokens": self.output_tokens,
            "total_cost": self.get_cost(),
            "calls": self.calls,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        try:
            from loguru import logger

            logger.debug("Saved cost breakdown to {}", path)
        except ImportError:
            pass
