"""
AI-generated site content: section copy, puzzle text, etc., personalized to spec + profile.
Voice-matched: use subject's communication style, vocabulary, and interests.
Optional validation + retry with feedback when content doesn't match profile.
"""

import json
import logging
import re

from holespawn.config import load_config
from holespawn.context import build_context
from holespawn.cost_tracker import CostTracker
from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.llm import call_llm
from holespawn.profile import PsychologicalProfile
from holespawn.site_builder.content_validator import ContentValidator

logger = logging.getLogger(__name__)


def _get_tone_examples(style: str) -> str:
    """Provide examples for each communication style."""
    examples = {
        "casual/memey": "Write like: 'ngl this is wild' not 'This presents an intriguing development'. Use: fr, lmao, tbh, casual abbreviations. Avoid: Formal language, corporate speak.",
        "academic/formal": "Write like: 'This suggests a fundamental reconsideration' not 'this is crazy lol'. Use precise terminology, logical connectors. Avoid slang, memes.",
        "cryptic/conspiratorial": "Write like: 'they don't want you to see this...' not 'Here's some information'. Use ellipses, suggestive language. Avoid direct explanations unless appropriate.",
        "direct/concise": "Write like: 'Here's what matters.' not 'Allow me to elaborate'. Use short sentences. Punchy. Clear. Avoid long explanations, flowery language.",
        "conversational/rambling": "Write in a natural, conversational flow. Medium-length sentences. Avoid stiff or overly formal phrasing.",
    }
    return examples.get(style, "Match their natural writing style.")


def _get_structure_examples(structure: str) -> str:
    """Examples for sentence structure."""
    examples = {
        "short punchy": "Write. Like. This. Short sentences. High impact. No fluff.",
        "long rambling": "Write longer sentences that flow together with multiple clauses and tangential thoughts that build on each other organically.",
        "bullet points": "Structure content as: clear points, one idea per line, easy to scan.",
    }
    return examples.get(structure, "Mirror their natural rhythm.")


def _get_detailed_tone_rules(profile: PsychologicalProfile) -> str:
    """Comprehensive tone guide with show-don't-tell examples."""
    comm = getattr(profile, "communication_style", "conversational/rambling")
    rules = {
        "casual/memey": """
CASUAL/MEMEY TONE:
- Write like: 'ok this is wild' NOT 'A revelation emerges'
- Use: Their slang (fr, ngl, lmao), casual abbreviations
- Structure: Short punchy sentences, playful
- Example: 'ngl I just realized something kinda crazy about [their interest] and nobody's talking about it'""",
        "academic/formal": """
ACADEMIC/FORMAL TONE:
- Write like: 'This suggests a fundamental reconsideration' NOT 'this is crazy lol'
- Use: Precise terminology, logical connectors, clear arguments
- Structure: Paragraphs with clear claims and support
- Example: 'Recent developments in [their field] suggest a reassessment of prior assumptions. Specifically...'""",
        "direct/concise": """
DIRECT/CONCISE TONE:
- Write like: 'Here's what matters.' NOT 'Allow me to elaborate on the significance'
- Use: Short sentences. Punchy. Clear.
- Example: 'The crux: [their interest]. Most people miss it.'""",
        "analytical/precise": """
ANALYTICAL/PRECISE TONE:
- Write like: 'Hmm, I notice a tension here' NOT 'A mystery unfolds'
- Use: 'Let me think through this', 'On reflection', 'Actually', edge cases
- Example: 'There's a genuine inconsistency in how we define [their concept] - specifically, are we talking about X or Y?'""",
        "cryptic/conspiratorial": """
CRYPTIC/CONSPIRATORIAL TONE:
- Can use mystery language but MUST use THEIR vocabulary and reference THEIR specific interests
- Not generic 'truth' or 'protocol' — reference their actual conspiracy/interest domain""",
        "conversational/rambling": """
CONVERSATIONAL TONE:
- Natural flow, medium-length sentences
- Use their actual phrases where natural
- Avoid stiff or corporate language""",
    }
    return rules.get(comm, "Match their natural writing style. Use their vocabulary.")


CONTENT_SYSTEM = """You are writing content for a personalized "rabbit hole" / ARG website. The experience was designed to match the subject's psychological profile and VOICE.

CRITICAL — Voice matching:
- Use the subject's COMMUNICATION STYLE (casual/memey, academic, cryptic, direct, etc.). Do NOT default to generic mysterious "protocol" language unless they are cryptic.
- Use words from their VOCABULARY SAMPLE. Do not use jargon they never use.
- Match their SENTENCE STRUCTURE (short punchy, long rambling, bullet points).
- Reference their SPECIFIC INTERESTS and OBSESSIONS. Puzzles and narrative should be ABOUT things they care about, not generic tech riddles.
- Reference their CULTURAL/COMMUNITY references (tech/startup, gaming, academia, etc.) so it feels like their community made it.

You receive: (1) a VOICE GUIDE (tone, vocabulary, structure, interests), (2) the experience spec, (3) profile and raw narrative.

Your job: write copy for each section so it feels like it was made BY someone in their world FOR them. If "narrative", write in their voice. If "puzzle", write a riddle about THEIR interests, in their voice; provide "question", "hint", "answer" (lowercase, no spaces). If "ambient", short atmospheric line in their style.

Avoid: "A new protocol is being established", "ephemeral data streams", generic mystery-speak (unless they are cryptic). Use their phrases and interests.

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


def _build_voice_guide(profile: PsychologicalProfile) -> str:
    """Build strict voice-matching instructions: mandatory vocabulary, interests, tone, validation."""
    comm = getattr(profile, "communication_style", "conversational/rambling")
    vocab = getattr(profile, "vocabulary_sample", [])[:40]
    phrases = getattr(profile, "sample_phrases", [])[:10]
    interests = getattr(profile, "specific_interests", [])[:10]
    obsessions = getattr(profile, "obsessions", [])[:8]
    sent_struct = getattr(profile, "sentence_structure", "mixed")
    tone_rules = _get_detailed_tone_rules(profile)
    struct_ex = _get_structure_examples(sent_struct)
    lines = [
        "## MANDATORY REQUIREMENTS (non-negotiable)",
        "",
        "MANDATORY VOCABULARY — use at least 5 of these words in EVERY section (body, question, or title):",
        ", ".join(vocab) if vocab else "N/A",
        "",
        "THEIR ACTUAL PHRASES — use these verbatim when possible:",
        ", ".join(phrases) if phrases else "N/A",
        "",
        "THEIR SPECIFIC INTERESTS — every section must reference at least ONE:",
        ", ".join(interests) if interests else "N/A",
        "",
        "OBSESSIONS (weight heavily in content):",
        ", ".join(obsessions) if obsessions else "N/A",
        "",
        f"COMMUNICATION STYLE: {comm}",
        "",
        "TONE RULES:",
        tone_rules,
        "",
        f"SENTENCE STRUCTURE: {sent_struct}",
        struct_ex,
        "",
        "VALIDATION BEFORE YOU WRITE EACH SECTION:",
        "1. Am I using words from vocabulary_sample? (Check: YES/NO)",
        "2. Am I referencing specific_interests? (Check: YES/NO)",
        "3. Does this sound like THEY would write it? (Check: YES/NO)",
        "4. Would THEY specifically find this compelling? (Check: YES/NO)",
        "If any check is NO: REWRITE until all are YES.",
    ]
    return "\n".join(lines)


def get_site_content(
    content: SocialContent,
    profile: PsychologicalProfile,
    spec: ExperienceSpec,
    *,
    provider: str | None = None,
    model: str | None = None,
    tracker: CostTracker | None = None,
    calls_per_minute: int = 20,
) -> list[dict]:
    """Generate section content (narrative + puzzle copy) from spec + profile; voice-matched.
    When validation_enabled, runs ContentValidator and retries with feedback up to max_validation_retries."""
    config = load_config()
    gen = config.get("generation", {})
    validation_enabled = gen.get("validation_enabled", False)
    max_validation_retries = gen.get("max_validation_retries", 2)
    min_vocab_match = gen.get("voice_matching", {}).get("min_vocabulary_match", 0.15)

    context = build_context(content, profile)
    voice_guide = _build_voice_guide(profile)
    spec_blob = json.dumps(
        {
            "aesthetic": spec.aesthetic,
            "experience_type": spec.experience_type,
            "tone": spec.tone,
            "title": spec.title,
            "tagline": spec.tagline,
            "sections": [{"id": s.id, "name": s.name, "type": s.type} for s in spec.sections],
        },
        indent=2,
    )

    base_user_content = (
        f"{voice_guide}\n\n"
        f"Experience spec:\n{spec_blob}\n\n"
        f"Profile and narrative:\n{context[:14000]}\n\n"
        "SECTION RULES: For each section, assign a focus_interest from their specific_interests or obsessions. "
        "Narrative sections: write 2–3 paragraphs using vocabulary_sample, reference the focus interest concretely, match their communication_style. "
        "Puzzle sections: create a puzzle ABOUT that focus interest (not generic riddles about kernels/protocols); question and hint in their voice; answer = one word/short phrase, lowercase, no spaces. "
        "CRITICAL: Content must feel like it was made by someone in their community, about topics they care about, in language they use. "
        "Output the section content JSON only."
    )

    user_content = base_user_content
    sections: list[dict] = []

    for attempt in range(max_validation_retries):
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
        sections = data.get("sections", [])

        if not validation_enabled or not sections:
            return sections

        validator = ContentValidator(profile, min_vocab_match=min_vocab_match)
        if validator.validate_sections(sections):
            return sections

        feedback = validator.get_feedback()
        if attempt < max_validation_retries - 1:
            logger.warning(
                "Content validation failed (attempt {}/{}): {}",
                attempt + 1,
                max_validation_retries,
                feedback,
            )
            user_content = (
                base_user_content
                + "\n\nPREVIOUS ATTEMPT FAILED VALIDATION:\n"
                + feedback
                + "\n\nFIX THESE ISSUES and output the section content JSON again."
            )
        else:
            logger.error(
                "Content failed validation after {} attempts; using content anyway. {}",
                max_validation_retries,
                feedback,
            )
            return sections

    return sections
