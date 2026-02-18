"""
Engagement brief for narrative engineering: psychological profile + social-engineering
framework to shape or steer a person via narrative. Vulnerability map, contact strategies,
phased engagement sequence.
"""

from holespawn.context import build_context
from holespawn.cost_tracker import CostTracker
from holespawn.ingest import SocialContent
from holespawn.llm import call_llm
from holespawn.profile import PsychologicalProfile
from holespawn.sct.enhancer import enhance_engagement
from holespawn.sct.mapper import SCTMapper

ENGAGEMENT_SYSTEM = """You are an analyst producing a **narrative engineering** brief. The goal is to profile one person so they can be shaped or steered through narrative — i.e. what stories, information flows, and social dynamics will move them toward desired beliefs, actions, or roles.

You receive a psychological profile and raw narrative (e.g. social media) for one person. Produce an **engagement brief** that maps:
- Vulnerability map: emotional triggers, trust hooks, resistance points, susceptibilities (what narrative levers work on this profile).
- Contact/approach ideas: concrete ways to open and deepen contact.
- Engagement sequence: phased plan for approach → rapport → embedding narratives → reinforcing alignment → landing the desired outcome. Phases 3 onward must be about **narrative engineering** (embedding stories, shaping belief, anchoring behavior), not puzzles, games, or “revelation/transformation” story arcs.

Do not use: ARG, alternate reality game, puzzles, investigations, “core narrative,” “revelation,” “transformation,” “cathartic resolution.” Do use: narrative embedding, information flow, belief shaping, role positioning, anchoring outcome, desired behavior.

Output valid markdown only. Use exactly these sections (keep headers as-is):

## Vulnerability map (social-engineering lens)
- **Emotional triggers**: Topics or framings that elicit strong engagement (hope, fear, curiosity, belonging, status, etc.).
- **Trust hooks**: What would make this person feel safe to engage (authority, peer similarity, proof, shared references, etc.).
- **Resistance points**: What might make them disengage or distrust (tone, pace, obvious persuasion, mismatch with identity, etc.).
- **Susceptibilities**: Themes, language, and levers this profile is most receptive to (for narrative and copy design).

## Contact / approach ideas
List 5–10 concrete angles for opening or deepening contact (first message, follow-up, channels). Each idea: 1–2 sentences. Vary tone (curiosity, shared interest, authority, scarcity, social proof). Focus on what would feel natural and effective for this profile.

## Engagement sequence
A phased plan (3–5 phases) for narrative engineering this person. Be specific to the profile.

- **Phase 1**: Initial approach — first touch, hook, channel. How to get a response and establish credibility. Shared interests, tone, pacing.

- **Phase 2**: Deepen rapport — “discoveries,” synchronicities, or exclusive content that build on their worldview. Position them as insider or part of a select group. Still trust-building, not yet steering.

- **Phase 3**: Embed narratives — introduce storylines, information flows, or themes that align with their beliefs and pull them toward desired directions. Use their susceptibilities; make it feel self-directed, not pitched. No puzzles or game mechanics.

- **Phase 4**: Reinforce and align — repetition, social proof, exclusive access. Shape what they consider true or important; position them inside a narrative where their role or identity is clear. Tighten alignment with desired outcomes.

- **Phase 5**: Land the outcome — anchor the desired result (belief, commitment, action, ongoing relationship). Concrete next step or behavioral anchor. No “revelation” or “transformation” — operational outcome.

Keep each phase to 2–4 sentences. Be specific to the profile. No ARG, puzzle, or story-arc language in phases 3–5.

Do not add preamble or meta-commentary. Output only the markdown document."""


def get_engagement_brief(
    content: SocialContent,
    profile: PsychologicalProfile,
    *,
    provider: str | None = None,
    model: str | None = None,
    tracker: CostTracker | None = None,
    calls_per_minute: int = 20,
    sct_enhance: bool = False,
) -> str:
    """
    Generate an engagement brief: vulnerability map, DM ideas, orchestration plan.
    Requires ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY.
    """
    context = build_context(content, profile)
    user_content = (
        "Based on this profile and narrative, output the engagement brief (markdown only, no preamble).\n\n"
        + context
    )
    brief = call_llm(
        ENGAGEMENT_SYSTEM,
        user_content,
        provider_override=provider,
        model_override=model,
        max_tokens=4096,
        operation="engagement_brief",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )

    if sct_enhance:
        try:
            matrix = {
                "themes": [(t, 1) for t in (profile.themes or [])],
                "sentiment": {
                    "compound": getattr(profile, "sentiment_compound", 0),
                    "pos": getattr(profile, "sentiment_positive", 0),
                    "neg": getattr(profile, "sentiment_negative", 0),
                    "neu": getattr(profile, "sentiment_neutral", 0),
                },
                "communication_style": getattr(profile, "communication_style", ""),
                "sample_phrases": getattr(profile, "sample_phrases", []),
                "specific_interests": getattr(profile, "specific_interests", []),
            }
            mapper = SCTMapper()
            vuln_map = mapper.map(matrix)
            addendum = enhance_engagement(
                brief, vuln_map,
                provider=provider, model=model,
                tracker=tracker, calls_per_minute=calls_per_minute,
            )
            brief += addendum
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("SCT enhancement failed: %s", e)

    return brief


def _profile_dict_to_context(profile: dict) -> str:
    """Build prompt context from profile dict only (no raw narrative). For repair/refresh."""
    lines = ["## Psychological profile (from stored matrix)", ""]
    themes = profile.get("themes") or []
    if themes and isinstance(themes[0], (list, tuple)):
        theme_str = ", ".join(str(t[0]) for t in themes[:25])
    else:
        theme_str = ", ".join(str(t) for t in themes[:25])
    lines.append(f"Themes: {theme_str}")
    for key in (
        "sentiment_compound",
        "sentiment_positive",
        "sentiment_negative",
        "sentiment_neutral",
        "intensity",
    ):
        val = profile.get(key)
        if val is not None:
            lines.append(f"{key}: {val}")
    lines.append(f"Communication style: {profile.get('communication_style', 'N/A')}")
    lines.append(f"Vocabulary sample: {', '.join((profile.get('vocabulary_sample') or [])[:25])}")
    lines.append(f"Specific interests: {', '.join((profile.get('specific_interests') or [])[:12])}")
    lines.append(f"Obsessions: {', '.join((profile.get('obsessions') or [])[:10])}")
    lines.append(
        f"Cultural references: {', '.join((profile.get('cultural_references') or [])[:10])}"
    )
    if profile.get("sample_phrases"):
        lines.append("Sample phrases:")
        for p in (profile["sample_phrases"] or [])[:15]:
            lines.append(f'  - "{p}"')
    lines.append("")
    lines.append("(Raw narrative not available — generate brief from profile only.)")
    return "\n".join(lines)


def get_engagement_brief_from_profile(
    profile_dict: dict,
    *,
    provider: str | None = None,
    model: str | None = None,
    tracker: CostTracker | None = None,
    calls_per_minute: int = 20,
) -> str:
    """
    Generate or refresh an engagement brief from a stored profile dict only (no raw content).
    Use for repair when the vulnerability map is missing or invalid.
    """
    context = _profile_dict_to_context(profile_dict)
    user_content = (
        "Based on this profile only (no raw narrative), output the engagement brief (markdown only, no preamble).\n\n"
        + context
    )
    return call_llm(
        ENGAGEMENT_SYSTEM,
        user_content,
        provider_override=provider,
        model_override=model,
        max_tokens=4096,
        operation="engagement_brief_from_profile",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
