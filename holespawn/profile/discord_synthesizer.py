"""
LLM-based synthesis of NLP analysis into psychological profile.
Supports local models via OpenAI-compatible API (api_base + model).
"""

import json
import os
import re
from typing import Any, Callable, Optional

from holespawn.config import get_llm_config
from holespawn.cost_tracker import CostTracker
from holespawn.llm import call_llm


def _extract_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group(0))
    return {}


SYNTHESIZE_SYSTEM = """You are a psychologist analyzing structured NLP metrics and raw message samples from a person's Discord activity.

You receive:
1. NLP analysis: vocabulary richness, sentiment distribution, hedging/certainty, reaction triggers, server engagement, network role, topics.
2. Representative message samples.

Output valid JSON only, no markdown or explanation. Use this exact structure:
{
  "vulnerabilities": ["list", "of", "psychological", "vulnerabilities", "or", "attention", "hooks"],
  "hooks": ["what", "would", "capture", "their", "attention"],
  "style": "one label: casual/memey | academic/formal | analytical/precise | direct/concise | conversational/rambling | cryptic/conspiratorial",
  "intimacy_level": "guarded | open | vulnerable",
  "trap_strategies": ["brief", "personalization", "strategies", "for", "content", "and", "design"]
}

Derive from the NLP metrics and samples. Be specific to the data."""


class DiscordLLMSynthesizer:
    """
    LLM-based synthesis of NLP analysis into psychological profile.
    Supports local models via OpenAI-compatible API.
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        preset: Optional[str] = None,
    ):
        if preset:
            config = get_llm_config(preset=preset)
            self.api_base = config.get("api_base")
            self.model = config.get("model")
        else:
            self.api_base = api_base or os.getenv("LLM_API_BASE")
            self.model = model or os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
        self.preset = preset

    def _call(self, system: str, user: str, tracker: Optional[CostTracker] = None) -> str:
        kwargs = {}
        if self.api_base:
            kwargs["api_base_override"] = self.api_base
        if self.model:
            kwargs["model_override"] = self.model
        return call_llm(
            system,
            user,
            max_tokens=2048,
            operation="discord_synthesize",
            tracker=tracker,
            **kwargs,
        )

    def synthesize_psychology(
        self,
        nlp_analysis: dict,
        raw_samples: dict,
        tracker: Optional[CostTracker] = None,
    ) -> dict[str, Any]:
        """
        LLM interprets NLP metrics + raw samples → psychological profile.
        Returns dict with vulnerabilities, hooks, style, intimacy_level, trap_strategies.
        """
        user = f"""NLP analysis (quantitative):
{json.dumps(nlp_analysis, indent=2)[:6000]}

Representative samples:
{json.dumps(raw_samples, indent=2)[:3000]}

Output the JSON only."""
        raw = self._call(SYNTHESIZE_SYSTEM, user, tracker)
        data = _extract_json(raw)
        return {
            "vulnerabilities": data.get("vulnerabilities", [])[:10],
            "hooks": data.get("hooks", [])[:10],
            "style": data.get("style", "conversational/rambling"),
            "intimacy_level": data.get("intimacy_level", "open"),
            "trap_strategies": data.get("trap_strategies", [])[:8],
        }

    def generate_tribal_profile(
        self,
        server_analysis: dict,
        message_samples: dict,
        tracker: Optional[CostTracker] = None,
    ) -> dict[str, Any]:
        """LLM analyzes server affiliations + tribal markers → community psychology."""
        user = f"""Server/community analysis:
{json.dumps(server_analysis, indent=2)[:3000]}

Message samples by context:
{json.dumps(message_samples, indent=2)[:2000]}

Output JSON: {"tribal_themes": ["theme1", "theme2"], "community_values": ["value1"], "language_markers": ["marker1"]}"""
        raw = self._call(
            "You analyze community/tribal psychology from server and message data. Output valid JSON only.",
            user,
            tracker,
        )
        return _extract_json(raw)

    def map_personalization_vectors(
        self,
        psychology: dict,
        nlp_metrics: dict,
        tracker: Optional[CostTracker] = None,
    ) -> dict[str, Any]:
        """LLM combines psychology + NLP patterns → specific personalization strategies for design and content."""
        user = f"""Psychology: {json.dumps(psychology)[:2000]}

NLP metrics (key): {json.dumps({k: v for k, v in list(nlp_metrics.items())[:20]}, default=str)[:2000]}

Output JSON: {"design_hints": [], "content_angles": [], "voice_rules": []}"""
        raw = self._call(
            "You map psychology and NLP to concrete personalization vectors for design system and content generation. Output valid JSON only.",
            user,
            tracker,
        )
        return _extract_json(raw)
