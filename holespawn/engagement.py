"""
Engagement brief: vulnerability map (social-engineering style), DM/interaction ideas,
and orchestration plan. For artistic/ARG design only — consent and ethics apply.
"""

from typing import Optional

from holespawn.context import build_context
from holespawn.cost_tracker import CostTracker
from holespawn.ingest import SocialContent
from holespawn.llm import call_llm
from holespawn.profile import PsychologicalProfile


ENGAGEMENT_SYSTEM = """You are an analyst for an artistic/ARG (Alternate Reality Game) project. Your output is used only for designing immersive, personalized experiences with consent — for art and entertainment.

You receive a psychological profile and raw narrative (Twitter/social text) for one person. Produce an **engagement brief** that maps how to design interactions and orchestration so the experience resonates. Frame this in a social-engineering sense: what emotional triggers, trust hooks, and susceptibilities does the profile suggest? What DM (direct message) or interaction angles would feel natural and engaging? What’s a phased orchestration plan (how to introduce the rabbit hole, when to deepen, pacing)?

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


def get_engagement_brief(
    content: SocialContent,
    profile: PsychologicalProfile,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tracker: Optional[CostTracker] = None,
    calls_per_minute: int = 20,
) -> str:
    """
    Generate an engagement brief: vulnerability map, DM ideas, orchestration plan.
    Requires ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY.
    """
    context = build_context(content, profile)
    user_content = "Based on this profile and narrative, output the engagement brief (markdown only, no preamble).\n\n" + context
    return call_llm(
        ENGAGEMENT_SYSTEM,
        user_content,
        provider_override=provider,
        model_override=model,
        max_tokens=4096,
        operation="engagement_brief",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
