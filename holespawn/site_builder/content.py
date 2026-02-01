"""
AI-generated site content: section copy, puzzle text, etc., personalized to spec + profile.
"""

import json
import re
from typing import Optional

from holespawn.context import build_context
from holespawn.cost_tracker import CostTracker
from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.llm import call_llm
from holespawn.profile import PsychologicalProfile


CONTENT_SYSTEM = """You are writing content for a personalized "rabbit hole" / ARG website. The experience design (aesthetic, type, tone) was already chosen to match the subject's psychological profile.

You receive: (1) the experience spec (aesthetic, tone, sections), (2) the subject's profile and raw narrative.

Your job: write the actual copy for each section so it feels like it was made *for* this person. Match their themes, phrases, and emotional tone. If a section is "narrative", write immersive short prose or found-document style text. If a section is "puzzle", write a riddle, cipher clue, or code-to-unlock prompt; provide a "question", optional "hint", and the exact "answer" (lowercase, no spaces—used to validate in the site). If "ambient", write a short atmospheric line or two.

Output valid JSON only, no markdown or explanation. Structure:

{
  "sections": [
    {
      "id": "intro",
      "title": "Section title",
      "body": "HTML or plain text for narrative/ambient. Use <p> for paragraphs.",
      "type": "narrative"
    },
    {
      "id": "puzzle1",
      "title": "Puzzle title",
      "question": "The riddle or clue text shown to the user.",
      "hint": "Optional hint (can be empty string)",
      "answer": "secret",
      "type": "puzzle"
    }
  ]
}

Rules: "id" must match the section ids from the spec. "body" can contain simple HTML (<p>, <em>, <br>). For puzzles, "answer" must be a single word or short phrase, lowercase, no spaces (e.g. "rabbit", "opendoor"). Generate 1–3 puzzles if the spec has puzzle sections."""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    return json.loads(text)


def get_site_content(
    content: SocialContent,
    profile: PsychologicalProfile,
    spec: ExperienceSpec,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tracker: Optional[CostTracker] = None,
    calls_per_minute: int = 20,
) -> list[dict]:
    """Generate section content (narrative + puzzle copy) from spec + profile."""
    context = build_context(content, profile)
    spec_blob = json.dumps({
        "aesthetic": spec.aesthetic,
        "experience_type": spec.experience_type,
        "tone": spec.tone,
        "title": spec.title,
        "tagline": spec.tagline,
        "sections": [{"id": s.id, "name": s.name, "type": s.type} for s in spec.sections],
    }, indent=2)
    user_content = f"Experience spec:\n{spec_blob}\n\nProfile and narrative:\n{context}\n\nOutput the section content JSON."
    raw = call_llm(
        CONTENT_SYSTEM,
        user_content,
        provider_override=provider,
        model_override=model,
        max_tokens=4096,
        operation="site_content",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
    data = _extract_json(raw)
    return data.get("sections", [])
