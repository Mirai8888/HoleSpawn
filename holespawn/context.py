"""Shared context builder for AI prompts: profile + narrative + voice."""

from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

MAX_NARRATIVE_CHARS = 30_000


def _get_profile_attr(profile: PsychologicalProfile, name: str, default):
    """Safe getattr for backward compat with older cached profiles."""
    return getattr(profile, name, default)


def build_context(content: SocialContent, profile: PsychologicalProfile) -> str:
    """Build prompt context: profile summary + voice/style + full narrative."""
    lines = []

    themes_str = ", ".join(t[0] for t in profile.themes[:25])
    lines.append("## Psychological profile (derived from text)")
    lines.append(f"Themes: {themes_str}")
    lines.append(
        f"Sentiment: compound={profile.sentiment_compound:.2f} "
        f"(pos={profile.sentiment_positive:.2f}, neg={profile.sentiment_negative:.2f}, neutral={profile.sentiment_neutral:.2f})"
    )
    lines.append(f"Emotional intensity: {profile.intensity:.2f}")
    lines.append(
        f"Style: avg sentence length={profile.avg_sentence_length:.1f}, "
        f"exclamation ratio={profile.exclamation_ratio:.2f}, question ratio={profile.question_ratio:.2f}"
    )
    # Voice & style (for voice-matched generation)
    comm = _get_profile_attr(profile, "communication_style", "conversational/rambling")
    vocab = _get_profile_attr(profile, "vocabulary_sample", [])
    emoji = _get_profile_attr(profile, "emoji_usage", "none")
    sent_struct = _get_profile_attr(profile, "sentence_structure", "mixed")
    cultural = _get_profile_attr(profile, "cultural_references", [])
    interests = _get_profile_attr(profile, "specific_interests", [])
    obsessions = _get_profile_attr(profile, "obsessions", [])
    peeves = _get_profile_attr(profile, "pet_peeves", [])
    lines.append("## Voice & communication")
    lines.append(f"Communication style: {comm}")
    lines.append(f"Vocabulary sample (use these words): {', '.join(vocab[:25]) if vocab else 'N/A'}")
    lines.append(f"Emoji usage: {emoji}")
    lines.append(f"Sentence structure: {sent_struct}")
    if cultural:
        lines.append(f"Cultural/community references: {', '.join(cultural)}")
    if interests:
        lines.append(f"Specific interests: {', '.join(interests[:12])}")
    if obsessions:
        lines.append(f"Obsessions (weight heavily): {', '.join(obsessions)}")
    if peeves:
        lines.append(f"Pet peeves / complaints: {', '.join(peeves)}")
    # Browsing / consumption (for multi-page attention trap)
    browsing = _get_profile_attr(profile, "browsing_style", "scanner")
    density = _get_profile_attr(profile, "content_density_preference", "moderate")
    lines.append(f"Browsing style: {browsing}")
    lines.append(f"Content density preference: {density}")
    if profile.sample_phrases:
        lines.append("Sample phrases from subject:")
        for phrase in profile.sample_phrases[:15]:
            lines.append(f'  - "{phrase}"')

    # Discord context (when profile was built from Discord data)
    tribal = _get_profile_attr(profile, "tribal_affiliations", [])
    reaction_triggers = _get_profile_attr(profile, "reaction_triggers", [])
    intimacy = _get_profile_attr(profile, "conversational_intimacy", "")
    community_role = _get_profile_attr(profile, "community_role", "")
    rhythm = _get_profile_attr(profile, "engagement_rhythm", {})
    if tribal or reaction_triggers or intimacy or community_role or rhythm:
        lines.append("## Discord context (if available)")
        if tribal:
            lines.append(f"Servers / tribal affiliations: {', '.join(tribal[:12])}")
        if reaction_triggers:
            lines.append(f"Themes they react to emotionally: {', '.join(reaction_triggers[:10])}")
        if intimacy:
            lines.append(f"Conversational intimacy: {intimacy}")
        if community_role:
            lines.append(f"Community role: {community_role}")
        if rhythm:
            lines.append(f"Engagement rhythm: {rhythm}")
        lines.append("")

    lines.append("")

    raw = content.full_text()
    if len(raw) > MAX_NARRATIVE_CHARS:
        raw = raw[:MAX_NARRATIVE_CHARS] + "\n\n[... narrative truncated ...]"
    lines.append("## Raw narrative (social / text output of the subject)")
    lines.append(raw)

    return "\n".join(lines)
