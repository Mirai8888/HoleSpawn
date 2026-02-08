"""
Validate that generated site content actually matches the psychological profile.
Checks vocabulary usage, interest references, and blocks generic mystery-speak for non-cryptic profiles.
"""


class ContentValidator:
    """Validate that generated content matches profile requirements."""

    def __init__(
        self, profile: object, min_vocab_match: float = 0.15, max_generic_mystery: int = 3
    ):
        self.profile = profile
        self.min_vocab_match = min_vocab_match
        self.max_generic_mystery = max_generic_mystery
        self.errors: list[str] = []

    def validate_content(self, content: str) -> bool:
        """Check if content matches profile (vocabulary, interests, no generic mystery-speak)."""
        self.errors = []
        content_lower = content.lower()

        vocab = getattr(self.profile, "vocabulary_sample", None) or []
        top_vocab = vocab[:30]
        if top_vocab:
            vocab_used = sum(1 for w in top_vocab if w.lower() in content_lower)
            n = len(top_vocab)
            ratio = vocab_used / n if n else 0
            if ratio < self.min_vocab_match:
                self.errors.append(
                    f"Content doesn't use subject's vocabulary (only {vocab_used}/{n} words, "
                    f"{ratio:.0%} match; min {self.min_vocab_match:.0%})"
                )

        comm = getattr(self.profile, "communication_style", "")
        if "cryptic" not in comm and "conspiratorial" not in comm:
            generic = [
                "protocol",
                "directive",
                "ephemeral",
                "manifest",
                "nexus",
                "paradigm shift",
                "unveil",
                "initiate",
                "revelation",
                "emerge",
            ]
            count = sum(1 for w in generic if w in content_lower)
            if count > self.max_generic_mystery:
                self.errors.append(
                    f"Content uses {count} generic mystery words but subject is {comm}. "
                    "Remove: protocol/directive/ephemeral etc."
                )

        interests = getattr(self.profile, "specific_interests", None) or []
        top_interests = interests[:10]
        if top_interests:
            mentioned = any(interest.lower() in content_lower for interest in top_interests)
            if not mentioned:
                self.errors.append(
                    f"Content doesn't reference any of their specific interests: "
                    f"{', '.join(top_interests[:5])}"
                )

        return len(self.errors) == 0

    def validate_sections(self, sections: list[dict]) -> bool:
        """Validate combined body/question text from all sections."""
        combined = []
        for s in sections:
            combined.append(s.get("body", "") or "")
            combined.append(s.get("question", "") or "")
            combined.append(s.get("title", "") or "")
        return self.validate_content(" ".join(combined))

    def get_feedback(self) -> str:
        """Actionable feedback for LLM to fix content."""
        if not self.errors:
            return "Content looks good."
        return "CONTENT VALIDATION FAILED:\n" + "\n".join(f"- {e}" for e in self.errors)
