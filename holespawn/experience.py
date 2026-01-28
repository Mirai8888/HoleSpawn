"""
Personalized experience spec: AI infers aesthetic, experience type (puzzles vs narrative),
tone, and structure from the subject's psychological profile and narrative.
"""

import json
import os
import re
from dataclasses import dataclass, field

from holespawn.context import build_context
from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

try:
    from holespawn.audience import AudienceProfile
except ImportError:
    AudienceProfile = None


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

You receive a psychological profile and raw narrative (social media / text) of one person. Optionally you also receive **audience susceptibility** (who they follow and what that audience engages with). Your job is to infer their **personal** preferences and design an experience that fits **them** (and, if audience data is present, what their audience is most susceptible to):

- If their language and themes suggest they like **light, airy, hopeful** things → the experience should feel light and airy (aesthetic, colors, tone).
- If they are **puzzle-oriented** (lots of questions, logic, curiosity, patterns) → the experience should include actual puzzles (riddles, ciphers, codes).
- If they are **narrative / emotional** → focus on immersive story fragments, atmosphere, found documents.
- If they are **exploratory / ambient** → focus on mood, discovery, minimal interaction.
- If **audience susceptibility** is provided, shape the experience so it resonates with what this audience engages with (themes, tone, emotional triggers).
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


def _call_ai(user_content: str, api_key: str, provider: str, model: str | None) -> str:
    try:
        import anthropic
        from openai import OpenAI
    except ImportError:
        raise ImportError("Install anthropic and openai: pip install anthropic openai") from None

    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model or "claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=EXPERIENCE_SPEC_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        return resp.content[0].text
    else:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            max_tokens=2048,
            messages=[
                {"role": "system", "content": EXPERIENCE_SPEC_SYSTEM},
                {"role": "user", "content": user_content},
            ],
        )
        return resp.choices[0].message.content or ""


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
    audience_profile: "AudienceProfile | None" = None,
    provider: str | None = None,
    model: str | None = None,
) -> ExperienceSpec:
    """Call AI to generate a personalized experience spec from profile + narrative (+ optional audience)."""
    prov = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai"
    if provider and provider.lower() in ("anthropic", "claude", "openai"):
        prov = "anthropic" if provider.lower() in ("anthropic", "claude") else "openai"
    api_key = os.getenv("ANTHROPIC_API_KEY") if prov == "anthropic" else os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY or OPENAI_API_KEY")

    audience_summary = audience_profile.summary if audience_profile else None
    context = build_context(content, profile, audience_summary=audience_summary)
    user_content = "Based on this profile and narrative" + (" and audience susceptibility" if audience_summary else "") + ", output the experience spec JSON.\n\n" + context
    raw = _call_ai(user_content, api_key, prov, model)
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
