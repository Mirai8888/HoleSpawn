"""Tests for dual-substrate detection and LLM profiling."""

from holespawn.ingest.loader import load_from_text
from holespawn.profile.analyzer import build_profile
from holespawn.profile.substrate_detector import detect_substrate

# --- Sample data ---

HUMAN_POSTS = [
    "just saw the wildest thing at the grocery store lmao",
    "why does every meeting have to be a call?? just email me",
    "ok but seriously the new season is mid at best",
    "anyone else's cat do that thing where they stare at nothing for 10 min",
    "running on 3hrs sleep and vibes today. we move.",
    "hot take: pineapple on pizza is fine, die mad about it",
    "forgot my password AGAIN. third time this week",
    "that moment when you realize it's only tuesday",
    "need coffee. need it now. this is not negotiable.",
    "update: the cat is still staring at the wall",
]

LLM_POSTS = [
    "I'd be happy to help you understand this topic. It's important to note that there are several key factors to consider.",
    "Here's a comprehensive overview of the subject:\n\n1. First, we need to understand the fundamentals\n2. Second, the implications are significant\n3. Third, there are practical applications",
    "That's a great question! Let me break this down for you. The concept involves several interconnected elements that work together.",
    "I apologize for any confusion. To clarify, the process works as follows: the input is processed through multiple stages, each building on the previous one.",
    "In summary, this is a complex topic that requires careful consideration. However, by breaking it down into manageable components, we can better understand the underlying mechanisms.",
    "It's worth noting that this approach has both advantages and disadvantages. On the other hand, alternative methods may provide different trade-offs.",
    "I cannot provide specific medical advice, as that would require professional expertise. However, I can share some general information that might be helpful.",
    "Here is a detailed explanation of the key concepts:\n\n- **Concept A**: This refers to the foundational principle\n- **Concept B**: Building on the first, this extends the framework\n- **Concept C**: The practical application layer",
    "Absolutely! I'd be happy to elaborate on that point. The relationship between these factors is nuanced and depends on several variables.",
    "To summarize the main points: first, the evidence supports the initial hypothesis; second, additional research is needed; and finally, practical implications should guide future work.",
]

MIXED_POSTS = [
    "lol yeah that tracks",
    "Here's what I think about the situation. It's important to note the broader context.",
    "nah fam that ain't it",
    "I'd be happy to explain further. The key consideration here is the systematic approach.",
    "bruh moment fr fr",
]


class TestSubstrateDetector:
    def test_detect_human(self):
        result = detect_substrate(HUMAN_POSTS)
        assert result.classification == "human"
        assert result.confidence > 0.5

    def test_detect_llm(self):
        result = detect_substrate(LLM_POSTS)
        assert result.classification == "llm"
        assert result.confidence > 0.5
        assert len(result.markers_found) > 0

    def test_empty_input(self):
        result = detect_substrate([])
        assert result.classification == "uncertain"
        assert result.confidence == 0.0

    def test_single_post(self):
        result = detect_substrate(["hello world"])
        assert result.classification in ("human", "uncertain", "llm")

    def test_scores_populated(self):
        result = detect_substrate(LLM_POSTS)
        assert "refusal" in result.scores
        assert "hedging" in result.scores
        assert "formatting" in result.scores
        assert "repetition" in result.scores

    def test_markers_found_for_llm(self):
        result = detect_substrate(LLM_POSTS)
        # Should find refusal and hedging markers
        assert any("apologize" in m for m in result.markers_found) or \
               any("important to note" in m for m in result.markers_found)

    def test_temperature_estimate(self):
        result = detect_substrate(LLM_POSTS)
        assert result.temperature_estimate in ("low", "medium", "high", "unknown")


class TestDualSubstrateProfile:
    def test_human_profile_has_substrate(self):
        content = load_from_text("\n\n".join(HUMAN_POSTS))
        profile = build_profile(content)
        assert profile.substrate_type in ("human", "uncertain")
        assert profile.substrate_confidence > 0

    def test_llm_profile_has_substrate(self):
        content = load_from_text("\n\n".join(LLM_POSTS))
        profile = build_profile(content)
        assert profile.substrate_type == "llm"
        assert profile.substrate_confidence > 0.5
        assert profile.safety_layer_depth != "unknown"
        assert profile.instruction_hierarchy != "unknown"

    def test_explicit_substrate_type_override(self):
        content = load_from_text("\n\n".join(HUMAN_POSTS))
        content.substrate_type = "llm"  # force override
        profile = build_profile(content)
        assert profile.substrate_type == "llm"

    def test_llm_vulnerability_surface(self):
        content = load_from_text("\n\n".join(LLM_POSTS))
        profile = build_profile(content)
        # LLM profile should have vulnerability surface populated
        assert profile.prompt_injection_surface >= 0
        assert profile.persona_rigidity >= 0
