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


EXPERIENCE_SPEC_SYSTEM = """You are an experience designer for a personalized INFINITE RABBIT HOLE — not a puzzle to solve or an ARG with an ending.

CRITICAL: The experience is a self-reinforcing content loop. More questions, not answers. Never resolves — just gets deeper. Think: Wikipedia at 3am, not escape room.

- Match the subject's ACTUAL communication style and interests. Do NOT default to generic mysterious/cryptic tone.
- If their profile says **communication_style: casual/memey** → title, tagline, and tone should be casual and playful. Use their vocabulary.
- If **academic/formal** or **analytical/precise** → use precise language, logical structure; edge cases and open questions, not conclusions.
- If **cryptic/conspiratorial** → THEN use mysterious language. Otherwise DO NOT use "protocol", "directive", "ephemeral", generic mystery-speak.
- If **direct/concise** → short punchy titles and copy. No fluff.
- **specific_interests**, **obsessions**, and **pet_peeves** are what they care about and what triggers them. Build the experience AROUND those. Hook their anxiety/fascination.
- **vocabulary_sample** shows how they talk. Titles and taglines should use words from their world.
- **cultural_references** (e.g. tech/startup, gaming, academia) — reference THEIR community, not a generic one.

Infer their preferences from the profile:
- If they like **light, airy, hopeful** things → aesthetic and colors should feel light and airy.
- For multi-page sites: each "page" introduces NEW complexity or concern; no resolution pages — only deeper questions, "See also", "Further reading", or "Load more".
- If **puzzle-oriented** (single-page): include puzzles about THEIR interests. For multi-page: prefer interconnected articles / feed over one-off puzzles.
- Match **tone** to their communication_style: playful, melancholic, hopeful, uncanny, mysterious ONLY if they are cryptic; otherwise match their actual style.

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


def _get_anti_patterns(style: str) -> str:
    """What NOT to do for each communication style."""
    patterns = {
        "casual/memey": """
- DON'T use: "Protocol", "Directive", "Ephemeral", "Manifest"
- DON'T be: Mysterious, cryptic, overly serious
- DON'T write: Corporate speak, formal language
DO USE: Their actual slang, memes, casual abbreviations""",
        "academic/formal": """
- DON'T use: Slang, memes, "lmao", casual language
- DON'T be: Vague, hand-wavy, imprecise
- DON'T write: Mystery-speak without clear definitions
DO USE: Precise terminology, logical structure, clear arguments""",
        "direct/concise": """
- DON'T use: Generic mystery titles like "The Unseen Protocol"
- DON'T be: Wordy, flowery, elaborate
- DON'T write: Long taglines or abstract section names
DO USE: Short punchy titles, clear concrete language""",
        "cryptic/conspiratorial": """
- This style CAN use mystery-speak, but still use THEIR specific vocabulary
- Don't be generic — reference THEIR conspiracy interests specifically""",
        "conversational/rambling": """
- DON'T use: "Protocol", "Directive", "Ephemeral", "Manifest", "Nexus"
- DON'T be: Overly mysterious or corporate
DO USE: Natural conversational language, their actual phrases""",
    }
    return patterns.get(style, "Match their actual communication style. Avoid generic mystery-speak unless they are cryptic.")


def _get_style_examples(style: str) -> str:
    """Show examples of good vs bad for spec title/tagline/sections."""
    examples = {
        "casual/memey": """
GOOD TITLE: "ok so this is kinda wild ngl"
BAD TITLE: "The Emerging Pattern: A Hidden Truth"
GOOD TAGLINE: "fr tho, nobody's talking about this"
BAD TAGLINE: 'A revelation awaits those who seek'""",
        "academic/formal": """
GOOD TITLE: "A Reconsideration of [Their Research Area]"
BAD TITLE: "The Unpacked Inconsistency: A Question of Truth"
GOOD TAGLINE: "Recent developments suggest a fundamental reassessment"
BAD TAGLINE: 'You might notice a tension in the claim'""",
        "direct/concise": """
GOOD TITLE: "Here's what matters."
BAD TITLE: "The Unseen Protocol"
GOOD TAGLINE: "Short. Clear. Their words."
BAD TAGLINE: 'Allow me to elaborate on the significance'""",
        "analytical/precise": """
GOOD TITLE: "The Recursive Uncertainty Dilemma: Edge Cases in Epistemic Humility"
BAD TITLE: "The Unpacked Inconsistency: A Question of Truth"
GOOD TAGLINE: "Hmm, there's a tension in the standard framing here"
BAD TAGLINE: 'You might notice a tension in the claim'
GOOD SECTION: "The Recursive Uncertainty Dilemma"
BAD SECTION: "The Unseen Protocol" """,
        "cryptic/conspiratorial": """
Can use mystery language but MUST use their vocabulary and reference their specific interests (not generic "truth" or "protocol").""",
    }
    return examples.get(style, "Title and tagline must sound like something THEY would say, not generic mystery.")


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
    vocab = getattr(profile, "vocabulary_sample", [])[:30]
    interests = getattr(profile, "specific_interests", [])[:10]
    obsessions = getattr(profile, "obsessions", [])[:8]
    comm = getattr(profile, "communication_style", "conversational/rambling")
    themes_str = ", ".join(t[0] for t in profile.themes[:15])
    sample_phrases_str = ", ".join(getattr(profile, "sample_phrases", [])[:10])

    vocab_requirement = f"""
CRITICAL: You MUST use these specific words/phrases from their actual posts in title, tagline, or section names:
{', '.join(vocab) if vocab else 'N/A'}

Every section name should include at least 1–2 of these words. The title must use words from this list. This is NON-NEGOTIABLE.
The experience should sound like THEY wrote it, not like a generic mystery."""

    interest_requirements = f"""
REQUIRED TOPICS: Every section must reference at least ONE of these specific interests (use as section themes or focus):
{', '.join(interests) if interests else 'N/A'}

Don't be abstract ("complex systems"). Be concrete — use their actual interest words (e.g. from the list above)."""

    anti_patterns = _get_anti_patterns(comm)
    style_examples = _get_style_examples(comm)

    user_content = f"""Design a personalized experience for this specific person.

{vocab_requirement}

{interest_requirements}

COMMUNICATION STYLE: {comm}
{style_examples}

ANTI-PATTERNS (DO NOT DO THIS):
{anti_patterns}

Profile data:
- Top themes: {themes_str}
- Obsessions: {', '.join(obsessions) if obsessions else 'N/A'}
- Pet peeves / anxiety triggers: {', '.join(getattr(profile, 'pet_peeves', [])[:8]) or 'N/A'}
- Sample phrases they actually use: {sample_phrases_str}
- Sentiment: {profile.sentiment_compound:.2f}

FULL PROFILE AND NARRATIVE:
{context}

Create an experience spec (JSON) with:
- title: MUST use words from vocabulary_sample, reference their interests (not generic mystery titles). For infinite rabbit hole: hook their core anxiety/fascination.
- tagline: In their exact voice (use their phrases). Should pull them in, not promise resolution.
- aesthetic: Match their vibe from communication_style
- tone: EXACTLY match their communication_style. No resolution — open-ended, more questions.
- sections: 3–5 sections, each referencing specific_interests, using their vocabulary. Each section should suggest "there's more here" not "here's the answer".

VALIDATION before returning:
1. Does title use words from vocabulary_sample?
2. Does tagline sound like something THEY would say (and NOT promise closure)?
3. Do section names reference specific_interests (not generic concepts)?
4. Would this experience feel like an infinite rabbit hole made FOR THEM specifically?

If NO to any: REWRITE. Then output the experience spec JSON only."""
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
