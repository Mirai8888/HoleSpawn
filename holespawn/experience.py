"""
Personalized experience spec: AI infers aesthetic, experience type (puzzles vs narrative),
tone, and structure from the subject's psychological profile and narrative.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from holespawn.context import build_context
from holespawn.cost_tracker import CostTracker
from holespawn.ingest import SocialContent
from holespawn.llm import call_llm
from holespawn.profile import PsychologicalProfile

@dataclass
class SectionSpec:
    id: str
    name: str
    type: str  # narrative | puzzle | ambient


@dataclass
class ExperienceSpec:
    """Personalized experience design derived from profile + narrative."""

    aesthetic: str = "minimal"
    experience_type: str = "mixed"  # puzzles | narrative | exploration | mixed
    tone: str = "mysterious"
    color_primary: str = "#2c3e50"
    color_secondary: str = "#3498db"
    color_background: str = "#ecf0f1"
    color_accent: str = "#e74c3c"
    title: str = "The Rabbit Hole"
    tagline: str = ""
    sections: list[SectionSpec] = field(default_factory=list)
    puzzle_difficulty: str = "medium"


EXPERIENCE_SPEC_SYSTEM = """You are an experience designer for a personalized "rabbit hole" / ARG art piece.

You receive a psychological profile and raw narrative (Twitter/social text) of one person. Your job is to infer their **personal** preferences and design an experience that fits **them**:

- If their language and themes suggest they like **light, airy, hopeful** things → the experience should feel light and airy (aesthetic, colors, tone).
- If they are **puzzle-oriented** (lots of questions, logic, curiosity, patterns) → the experience should include actual puzzles (riddles, ciphers, codes).
- If they are **narrative / emotional** → focus on immersive story fragments, atmosphere, found documents.
- If they are **exploratory / ambient** → focus on mood, discovery, minimal interaction.
- Match **aesthetic** to their world: minimal, maximal, organic, technical, dreamy, gritty, etc.
- Match **tone** to their emotional profile: playful, melancholic, hopeful, uncanny, mysterious, etc.

Output valid JSON only, no markdown or explanation. Use this exact structure (all fields required):

{
  "aesthetic": "light_airy",
  "experience_type": "puzzles",
  "tone": "mysterious",
  "color_primary": "#hex",
  "color_secondary": "#hex",
  "color_background": "#hex",
  "color_accent": "#hex",
  "title": "Short title for the experience",
  "tagline": "One line tagline",
  "sections": [
    { "id": "intro", "name": "Display name", "type": "narrative" },
    { "id": "puzzle1", "name": "First puzzle", "type": "puzzle" }
  ],
  "puzzle_difficulty": "gentle"
}

Allowed: aesthetic (light_airy, dark_dense, minimal, maximal, organic, technical, dreamy, gritty). experience_type (puzzles, narrative, exploration, mixed). tone (playful, melancholic, hopeful, uncanny, mysterious, serene, tense). puzzle_difficulty (gentle, medium, challenging). Section types: narrative, puzzle, ambient. Use 3–6 sections. Include at least one puzzle section if experience_type is puzzles or mixed."""


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Remove markdown code block if present
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    return json.loads(text)


def get_experience_spec(
    content: SocialContent,
    profile: PsychologicalProfile,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tracker: Optional[CostTracker] = None,
    calls_per_minute: int = 20,
) -> ExperienceSpec:
    """Call AI to generate a personalized experience spec from profile + narrative."""
    context = build_context(content, profile)
    user_content = "Based on this profile and narrative, output the experience spec JSON.\n\n" + context
    raw = call_llm(
        EXPERIENCE_SPEC_SYSTEM,
        user_content,
        provider_override=provider,
        model_override=model,
        max_tokens=2048,
        operation="experience_spec",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
    data = _extract_json(raw)

    sections = [
        SectionSpec(id=s["id"], name=s["name"], type=s.get("type", "narrative"))
        for s in data.get("sections", [])
    ]
    return ExperienceSpec(
        aesthetic=data.get("aesthetic", "minimal"),
        experience_type=data.get("experience_type", "mixed"),
        tone=data.get("tone", "mysterious"),
        color_primary=data.get("color_primary", "#2c3e50"),
        color_secondary=data.get("color_secondary", "#3498db"),
        color_background=data.get("color_background", "#ecf0f1"),
        color_accent=data.get("color_accent", "#e74c3c"),
        title=data.get("title", "The Rabbit Hole"),
        tagline=data.get("tagline", ""),
        sections=sections,
        puzzle_difficulty=data.get("puzzle_difficulty", "medium"),
    )
