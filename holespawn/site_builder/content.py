"""
AI-generated site content: section copy, puzzle text, etc., personalized to spec + profile.
"""

import json
import os
import re

from holespawn.context import build_context
from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
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


def _call_ai(user_content: str, api_key: str, provider: str, model: str | None) -> str:
    try:
        import anthropic
        from openai import OpenAI
    except ImportError:
        raise ImportError("Install anthropic and openai: pip install anthropic openai") from None

    if provider == "google":
        try:
            from google import genai  # type: ignore
        except ImportError:
            raise ImportError("Install google-genai: pip install google-genai") from None

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model or "gemini-1.5-flash",
            contents=[
                {"role": "user", "parts": [{"text": f"{CONTENT_SYSTEM}\n\n{user_content}"}]},
            ],
        )
        return getattr(resp, "text", None) or ""
    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model or "claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=CONTENT_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        return resp.content[0].text
    else:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            max_tokens=4096,
            messages=[
                {"role": "system", "content": CONTENT_SYSTEM},
                {"role": "user", "content": user_content},
            ],
        )
        return resp.choices[0].message.content or ""


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
    audience_summary: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> list[dict]:
    """Generate section content (narrative + puzzle copy) from spec + profile (+ optional audience)."""
    prov = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai"
    if provider and provider.lower() in ("anthropic", "claude", "openai", "google", "gemini"):
        if provider.lower() in ("anthropic", "claude"):
            prov = "anthropic"
        elif provider.lower() in ("google", "gemini"):
            prov = "google"
        else:
            prov = "openai"

    if prov == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
    elif prov == "google":
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    else:
        api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY")

    context = build_context(content, profile, audience_summary=audience_summary)
    spec_blob = json.dumps({
        "aesthetic": spec.aesthetic,
        "experience_type": spec.experience_type,
        "tone": spec.tone,
        "title": spec.title,
        "tagline": spec.tagline,
        "sections": [{"id": s.id, "name": s.name, "type": s.type} for s in spec.sections],
    }, indent=2)
    user_content = f"Experience spec:\n{spec_blob}\n\nProfile and narrative:\n{context}\n\nOutput the section content JSON."
    raw = _call_ai(user_content, api_key, prov, model)
    data = _extract_json(raw)
    return data.get("sections", [])
