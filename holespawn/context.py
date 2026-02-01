"""Shared context builder for AI prompts: profile + narrative."""

from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

MAX_NARRATIVE_CHARS = 30_000


def build_context(content: SocialContent, profile: PsychologicalProfile) -> str:
    """Build prompt context: profile summary + full narrative."""
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
    if profile.sample_phrases:
        lines.append("Sample phrases from subject:")
        for phrase in profile.sample_phrases[:15]:
            lines.append(f'  - "{phrase}"')
    lines.append("")

    raw = content.full_text()
    if len(raw) > MAX_NARRATIVE_CHARS:
        raw = raw[:MAX_NARRATIVE_CHARS] + "\n\n[... narrative truncated ...]"
    lines.append("## Raw narrative (social / text output of the subject)")
    lines.append(raw)

    return "\n".join(lines)
