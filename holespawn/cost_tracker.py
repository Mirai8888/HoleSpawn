"""
Track LLM token usage and estimated cost.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Per 1M tokens (input, output)
PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-flash": (0.15, 0.60),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-sonnet-3.5": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
}


def _normalize_model(name: str) -> str:
    """Map model name to a key in PRICING."""
    name = (name or "").lower()
    for key in PRICING:
        if key in name or name in key:
            return key
    return "gemini-2.5-flash"  # fallback


class CostTracker:
    """Track LLM token usage and costs."""

    def __init__(
        self,
        model: str = "gemini-flash",
        warn_threshold: float = 1.00,
        max_cost: float = 5.00,
    ):
        self.model = model
        self._pricing_key = _normalize_model(model)
        self.warn_threshold = warn_threshold
        self.max_cost = max_cost
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
        self.calls.append({
            "operation": operation,
            "input": input_tokens,
            "output": output_tokens,
            "timestamp": datetime.now().isoformat(),
        })
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

    def get_cost(self) -> float:
        prices = PRICING.get(self._pricing_key, PRICING["gemini-2.5-flash"])
        input_cost, output_cost = prices
        return (
            (self.input_tokens * input_cost / 1_000_000)
            + (self.output_tokens * output_cost / 1_000_000)
        )

    def print_summary(self) -> None:
        cost = self.get_cost()
        print("\n💰 API usage summary")
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
