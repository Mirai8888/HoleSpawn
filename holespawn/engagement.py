"""
Engagement brief: vulnerability map (social-engineering style), DM/interaction ideas,
and orchestration plan. For artistic/ARG design only — consent and ethics apply.
"""

import os
from typing import Optional

from holespawn.context import build_context
from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

try:
    from holespawn.audience import AudienceProfile
except ImportError:
    AudienceProfile = None


ENGAGEMENT_SYSTEM = """You are an analyst for an artistic/ARG (Alternate Reality Game) project. Your output is used only for designing immersive, personalized experiences with consent — for art and entertainment.

You receive a psychological profile and raw narrative (and optionally audience susceptibility) for one person. Produce an **engagement brief** that maps how to design interactions and orchestration so the experience resonates. Frame this in a social-engineering sense: what emotional triggers, trust hooks, and susceptibilities does the profile suggest? What DM (direct message) or interaction angles would feel natural and engaging? What’s a phased orchestration plan (how to introduce the rabbit hole, when to deepen, pacing)?

Output valid markdown only. Use exactly these sections (keep headers as-is):

## Vulnerability map (social-engineering lens)
- **Emotional triggers**: What topics or framings tend to elicit strong engagement (hope, fear, curiosity, belonging, etc.).
- **Trust hooks**: What would make this person feel safe to engage (authority, peer similarity, mystery, proof, etc.).
- **Resistance points**: What might make them disengage or distrust (tone, pace, obvious manipulation, etc.).
- **Susceptibilities**: Summary of themes/language that this profile is most receptive to (for designing copy and interactions).

## DM / interaction ideas
List 5–10 concrete angles for opening or deepening contact (e.g. first DM, follow-up, or in-world interaction). Each idea: 1–2 sentences. Vary tone and channel (curiosity, shared interest, mystery, challenge, etc.).

## Orchestration plan
A phased plan (3–5 phases) for rolling out the experience:
- **Phase 1**: How to introduce (first touch, hook).
- **Phase 2–4**: How to deepen (pacing, reveals, puzzles or narrative beats).
- **Phase 5**: How to land or resolve (optional).

Keep each phase to 2–4 sentences. Be specific to the profile (themes, tone, susceptibilities).

Do not add preamble or meta-commentary. Output only the markdown document."""


def _call_ai(system: str, user_content: str, api_key: str, provider: str, model: Optional[str]) -> str:
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
                {"role": "user", "parts": [{"text": f"{system}\n\n{user_content}"}]},
            ],
        )
        return getattr(resp, "text", None) or ""
    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model or "claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return resp.content[0].text or ""
    else:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        )
        return resp.choices[0].message.content or ""


def get_engagement_brief(
    content: SocialContent,
    profile: PsychologicalProfile,
    *,
    audience_profile: Optional["AudienceProfile"] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate an engagement brief: vulnerability map, DM ideas, orchestration plan.
    Requires ANTHROPIC_API_KEY or OPENAI_API_KEY.
    """
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

    audience_summary = audience_profile.summary if audience_profile else None
    context = build_context(content, profile, audience_summary=audience_summary)
    user_content = (
        "Based on this profile and narrative"
        + (" and audience susceptibility" if audience_summary else "")
        + ", output the engagement brief (markdown only, no preamble).\n\n"
        + context
    )
    return _call_ai(ENGAGEMENT_SYSTEM, user_content, api_key, prov, model)
