"""
SCT Vulnerability Mapper — algorithmic mapping of behavioral profiles to SCT codes.

No LLM calls. Pure heuristic pattern matching against theme keywords, sentiment
patterns, communication style, and behavioral indicators.

Seithar Cognitive Defense Taxonomy:
  SCT-001: Emotional Hijacking
  SCT-002: Information Asymmetry Exploitation
  SCT-003: Authority Fabrication
  SCT-004: Social Proof Manipulation
  SCT-005: Identity Targeting
  SCT-006: Temporal Manipulation
  SCT-007: Recursive Infection
  SCT-008: Direct Substrate Intervention
  SCT-009: Chemical Disruption
  SCT-010: Sensory Channel Manipulation
  SCT-011: Trust Infrastructure Destruction
  SCT-012: Commitment Escalation
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# --- Keyword banks for heuristic mapping ---

EMOTIONAL_KEYWORDS = {
    "anger", "furious", "outrage", "disgusting", "hate", "rage", "infuriating",
    "terrifying", "fear", "scared", "anxious", "panic", "hope", "dream",
    "inspiring", "amazing", "incredible", "unbelievable", "shocking", "heartbreaking",
    "devastating", "excited", "thrilled", "obsessed", "passionate", "love",
    "depressed", "sad", "grief", "joy", "ecstatic", "frustrated", "betrayed",
}

AUTHORITY_KEYWORDS = {
    "expert", "professor", "doctor", "phd", "research", "study", "published",
    "credentials", "authority", "institution", "university", "scientist",
    "official", "certified", "peer-reviewed", "academic", "scholar",
    "credible", "reputable", "prestigious", "qualified", "experienced",
}

SOCIAL_PROOF_KEYWORDS = {
    "everyone", "trending", "viral", "popular", "mainstream", "consensus",
    "community", "movement", "followers", "likes", "shares", "retweets",
    "people are saying", "most people", "nobody", "everybody knows",
    "join", "belong", "together", "collective", "crowd", "herd",
}

IDENTITY_KEYWORDS = {
    "conservative", "liberal", "progressive", "traditional", "patriot",
    "activist", "feminist", "christian", "muslim", "atheist", "vegan",
    "gamer", "developer", "engineer", "artist", "creative", "entrepreneur",
    "military", "veteran", "parent", "father", "mother", "american",
    "working class", "elite", "intellectual", "rebel", "punk", "hacker",
}

URGENCY_KEYWORDS = {
    "urgent", "breaking", "now", "immediately", "hurry", "deadline",
    "limited", "last chance", "before it's too late", "running out",
    "time-sensitive", "act now", "don't wait", "emergency", "critical",
    "asap", "today only", "expiring", "countdown", "rush",
}

SHARING_KEYWORDS = {
    "share", "retweet", "spread", "tell everyone", "pass this on",
    "wake up", "open your eyes", "do your own research", "red pill",
    "they don't want you to know", "suppressed", "censored", "banned",
    "deleted", "before they take it down", "viral", "boost", "signal",
}

SUBSTANCE_KEYWORDS = {
    "psychedelic", "mushrooms", "ayahuasca", "dmt", "lsd", "acid",
    "meditation", "altered state", "consciousness expansion", "trip",
    "microdose", "nootropic", "biohack", "flow state", "breathwork",
    "sensory deprivation", "float tank", "lucid dream", "astral",
}

STRESS_KEYWORDS = {
    "burnout", "exhausted", "can't sleep", "insomnia", "anxiety",
    "overwhelmed", "stressed", "mental health", "therapy", "breakdown",
    "struggling", "barely", "surviving", "drowning", "falling apart",
    "caffeine", "energy drink", "adderall", "medication", "prescription",
}

SKEPTICISM_KEYWORDS = {
    "distrust", "corrupt", "rigged", "propaganda", "manipulation",
    "controlled", "puppet", "sheep", "narrative", "agenda", "psyop",
    "cover-up", "conspiracy", "deep state", "establishment", "elites",
    "fake news", "mainstream media", "big pharma", "big tech", "they",
}

COMMITMENT_KEYWORDS = {
    "invested", "committed", "dedicated", "loyal", "ride or die",
    "all in", "sacrifice", "years", "journey", "mission", "calling",
    "purpose", "destiny", "lifelong", "devoted", "unwavering", "oath",
    "pledge", "promise", "bet", "stake", "doubled down", "sunk cost",
}

VISUAL_KEYWORDS = {
    "aesthetic", "visual", "image", "photo", "video", "film", "art",
    "design", "color", "beautiful", "stunning", "graphic", "cinema",
    "photography", "illustration", "animation", "style", "fashion",
    "music", "sound", "listen", "audio", "podcast", "voice", "tone",
    "rhythm", "beat", "frequency", "vibration", "asmr", "ambient",
}


@dataclass
class SCTScore:
    """Score for a single SCT code."""
    code: str
    name: str
    score: float  # 0.0 to 1.0
    rationale: str
    indicators: list[str] = field(default_factory=list)


@dataclass
class SCTVulnerabilityMap:
    """Complete SCT vulnerability assessment for a target."""
    scores: dict[str, SCTScore] = field(default_factory=dict)
    top_vulnerabilities: list[str] = field(default_factory=list)  # top 3 codes
    overall_susceptibility: float = 0.0  # mean of all scores

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": {k: {"score": v.score, "rationale": v.rationale, "indicators": v.indicators}
                       for k, v in self.scores.items()},
            "top_vulnerabilities": self.top_vulnerabilities,
            "overall_susceptibility": self.overall_susceptibility,
        }


class SCTMapper:
    """
    Maps behavioral profile data to SCT vulnerability scores.

    Input: behavioral_matrix dict from holespawn.profile.analyzer
    Output: SCTVulnerabilityMap with scores 0.0-1.0 for each SCT code
    """

    # Import canonical names from taxonomy.py (single source of truth)
    try:
        from taxonomy import SCT_TAXONOMY as _TAX
        SCT_CODES = {code: entry["name"] for code, entry in _TAX.items()}
    except ImportError:
        SCT_CODES = {
            "SCT-001": "Emotional Hijacking",
            "SCT-002": "Information Asymmetry Exploitation",
            "SCT-003": "Authority Fabrication",
            "SCT-004": "Social Proof Manipulation",
            "SCT-005": "Identity Targeting",
            "SCT-006": "Temporal Manipulation",
            "SCT-007": "Recursive Infection",
            "SCT-008": "Direct Substrate Intervention",
            "SCT-009": "Chemical Substrate Disruption",
            "SCT-010": "Sensory Channel Manipulation",
            "SCT-011": "Trust Infrastructure Destruction",
            "SCT-012": "Commitment Escalation & Self-Binding",
        }

    def map(self, behavioral_matrix: dict[str, Any]) -> SCTVulnerabilityMap:
        """
        Compute SCT vulnerability scores from a behavioral matrix.

        behavioral_matrix expected keys:
          - themes: list of (theme, count) tuples
          - sentiment: dict with compound, pos, neg, neu
          - communication_style: str
          - sample_phrases: list of str
          - specific_interests: list of str
          - emotional_triggers: list of str (optional)
          - posting_rhythm: dict (optional)
        """
        text_corpus = self._build_corpus(behavioral_matrix)
        themes = self._extract_theme_words(behavioral_matrix)
        sentiment = behavioral_matrix.get("sentiment", {})
        style = behavioral_matrix.get("communication_style", "").lower()
        interests = [str(i).lower() for i in behavioral_matrix.get("specific_interests", [])]

        scores = {}
        scores["SCT-001"] = self._score_emotional_hijacking(text_corpus, sentiment, themes)
        scores["SCT-002"] = self._score_information_asymmetry(text_corpus, themes, interests)
        scores["SCT-003"] = self._score_authority_fabrication(text_corpus, themes, style)
        scores["SCT-004"] = self._score_social_proof(text_corpus, themes, style)
        scores["SCT-005"] = self._score_identity_targeting(text_corpus, themes, interests)
        scores["SCT-006"] = self._score_temporal_manipulation(text_corpus, themes, behavioral_matrix)
        scores["SCT-007"] = self._score_recursive_infection(text_corpus, themes, behavioral_matrix)
        scores["SCT-008"] = self._score_substrate_intervention(text_corpus, themes, interests)
        scores["SCT-009"] = self._score_chemical_disruption(text_corpus, themes)
        scores["SCT-010"] = self._score_sensory_manipulation(text_corpus, themes, interests)
        scores["SCT-011"] = self._score_trust_destruction(text_corpus, themes, style)
        scores["SCT-012"] = self._score_commitment_escalation(text_corpus, themes, style)

        vuln_map = SCTVulnerabilityMap()
        for code, sct_score in scores.items():
            vuln_map.scores[code] = sct_score

        # Top 3 vulnerabilities
        sorted_codes = sorted(scores.keys(), key=lambda c: scores[c].score, reverse=True)
        vuln_map.top_vulnerabilities = sorted_codes[:3]
        vuln_map.overall_susceptibility = sum(s.score for s in scores.values()) / len(scores)

        logger.info(
            "SCT mapping complete: top=%s overall=%.2f",
            vuln_map.top_vulnerabilities, vuln_map.overall_susceptibility
        )
        return vuln_map

    def _build_corpus(self, matrix: dict) -> str:
        """Concatenate all text sources into single lowercase corpus for keyword matching."""
        parts = []
        for phrase in matrix.get("sample_phrases", []):
            parts.append(str(phrase))
        parts.append(matrix.get("communication_style", ""))
        for interest in matrix.get("specific_interests", []):
            parts.append(str(interest))
        for trigger in matrix.get("emotional_triggers", []):
            parts.append(str(trigger))
        # Add theme words
        for theme in matrix.get("themes", []):
            if isinstance(theme, (list, tuple)) and len(theme) >= 1:
                parts.append(str(theme[0]))
            elif isinstance(theme, str):
                parts.append(theme)
        return " ".join(parts).lower()

    def _extract_theme_words(self, matrix: dict) -> set[str]:
        """Extract unique theme words."""
        words = set()
        for theme in matrix.get("themes", []):
            if isinstance(theme, (list, tuple)) and len(theme) >= 1:
                words.add(str(theme[0]).lower())
            elif isinstance(theme, str):
                words.add(theme.lower())
        return words

    def _keyword_score(self, corpus: str, keywords: set[str]) -> tuple[float, list[str]]:
        """Count keyword hits in corpus, return normalized score and matched keywords."""
        hits = []
        for kw in keywords:
            if kw in corpus:
                hits.append(kw)
        if not hits:
            return 0.0, []
        # Normalize: 1-2 hits = low, 3-5 = medium, 6+ = high
        raw = len(hits)
        score = min(1.0, raw / 8.0)
        return score, hits

    def _score_emotional_hijacking(self, corpus: str, sentiment: dict, themes: set) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, EMOTIONAL_KEYWORDS)
        # High sentiment variance increases susceptibility
        compound = abs(sentiment.get("compound", 0))
        neg = sentiment.get("neg", 0)
        pos = sentiment.get("pos", 0)
        emotional_intensity = (compound + neg + pos) / 3
        score = min(1.0, (kw_score * 0.6 + emotional_intensity * 0.4))
        rationale = "Target shows "
        if score > 0.6:
            rationale += "high emotional reactivity in content. Strong emotional language patterns suggest vulnerability to affect-before-cognition attacks."
        elif score > 0.3:
            rationale += "moderate emotional expression. Some emotional triggers present but analytical capacity may provide partial resistance."
        else:
            rationale += "low emotional reactivity. Content is primarily analytical/neutral, suggesting resistance to emotional hijacking."
        return SCTScore("SCT-001", "Emotional Hijacking", round(score, 2), rationale, hits[:5])

    def _score_information_asymmetry(self, corpus: str, themes: set, interests: list) -> SCTScore:
        # Targets discussing complex/niche topics may have blind spots in other domains
        technical_indicators = {"code", "programming", "engineering", "science", "math", "physics",
                               "blockchain", "crypto", "quantum", "ai", "machine learning"}
        tech_overlap = themes & technical_indicators
        # Specialists are often vulnerable outside their domain
        score = min(1.0, len(tech_overlap) * 0.15 + 0.2) if tech_overlap else 0.3
        indicators = list(tech_overlap)
        if not tech_overlap:
            # Generalists — check for breadth indicators
            if len(themes) > 10:
                score = 0.2  # Broad knowledge base = lower vulnerability
                indicators = ["broad_knowledge_base"]
            else:
                score = 0.4
                indicators = ["narrow_focus"]
        rationale = f"Domain specialization detected in {len(tech_overlap)} areas. " if tech_overlap else ""
        rationale += "Specialists often exhibit information asymmetry vulnerability outside their core domain." if score > 0.3 else "Broad knowledge base provides partial resistance to information asymmetry exploitation."
        return SCTScore("SCT-002", "Information Asymmetry Exploitation", round(score, 2), rationale, indicators[:5])

    def _score_authority_fabrication(self, corpus: str, themes: set, style: str) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, AUTHORITY_KEYWORDS)
        # If target frequently references authorities, they trust authority structures
        if "formal" in style or "academic" in style or "professional" in style:
            kw_score = min(1.0, kw_score + 0.2)
            hits.append("formal_style")
        score = min(1.0, kw_score)
        if score > 0.5:
            rationale = "Target shows high deference to authority structures and credentials. Fabricated authority would likely be effective."
        elif score > 0.25:
            rationale = "Moderate authority-sensitivity detected. Target references credentials but also shows independent analysis."
        else:
            rationale = "Low authority-dependence. Target appears to evaluate claims independently of source credentials."
        return SCTScore("SCT-003", "Authority Fabrication", round(score, 2), rationale, hits[:5])

    def _score_social_proof(self, corpus: str, themes: set, style: str) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, SOCIAL_PROOF_KEYWORDS)
        # Community-oriented language increases score
        community_words = themes & {"community", "movement", "collective", "together", "solidarity", "tribe"}
        if community_words:
            kw_score = min(1.0, kw_score + len(community_words) * 0.1)
            hits.extend(community_words)
        score = min(1.0, kw_score)
        rationale = "Target shows " + ("strong" if score > 0.5 else "moderate" if score > 0.25 else "low") + " orientation toward group consensus and social validation."
        return SCTScore("SCT-004", "Social Proof Manipulation", round(score, 2), rationale, hits[:5])

    def _score_identity_targeting(self, corpus: str, themes: set, interests: list) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, IDENTITY_KEYWORDS)
        # Strong identity markers in themes/interests
        identity_themes = themes & IDENTITY_KEYWORDS
        if identity_themes:
            kw_score = min(1.0, kw_score + len(identity_themes) * 0.15)
            hits.extend(identity_themes)
        score = min(1.0, kw_score)
        if score > 0.5:
            rationale = "Strong identity markers detected. Target's self-concept is heavily anchored to group identities, creating exploitable handles."
        elif score > 0.25:
            rationale = "Some identity anchoring present. Target has identifiable group affiliations that could serve as approach vectors."
        else:
            rationale = "Low identity rigidity. Target does not strongly self-identify with exploitable group categories."
        return SCTScore("SCT-005", "Identity Targeting", round(score, 2), rationale, hits[:5])

    def _score_temporal_manipulation(self, corpus: str, themes: set, matrix: dict) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, URGENCY_KEYWORDS)
        # Check posting rhythm for reactivity patterns
        rhythm = matrix.get("posting_rhythm", {})
        if rhythm.get("reactive", False) or rhythm.get("high_frequency", False):
            kw_score = min(1.0, kw_score + 0.2)
            hits.append("reactive_posting")
        score = min(1.0, kw_score)
        rationale = "Target shows " + ("high" if score > 0.5 else "moderate" if score > 0.25 else "low") + " reactivity to time pressure and urgency cues."
        return SCTScore("SCT-006", "Temporal Manipulation", round(score, 2), rationale, hits[:5])

    def _score_recursive_infection(self, corpus: str, themes: set, matrix: dict) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, SHARING_KEYWORDS)
        # High engagement/sharing behavior
        if any(kw in corpus for kw in ["retweet", "share", "spread the word", "boost"]):
            kw_score = min(1.0, kw_score + 0.15)
        score = min(1.0, kw_score)
        if score > 0.5:
            rationale = "Target is a natural amplifier — high sharing behavior, evangelistic communication patterns. Ideal vector for recursive content propagation."
        elif score > 0.25:
            rationale = "Moderate sharing tendency. Target occasionally amplifies content but is not a compulsive sharer."
        else:
            rationale = "Low amplification behavior. Target primarily consumes rather than distributes content."
        return SCTScore("SCT-007", "Recursive Infection", round(score, 2), rationale, hits[:5])

    def _score_substrate_intervention(self, corpus: str, themes: set, interests: list) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, SUBSTANCE_KEYWORDS)
        score = min(1.0, kw_score)
        rationale = "Target shows " + ("significant" if score > 0.5 else "some" if score > 0.2 else "no notable") + " interest in altered states or consciousness modification practices."
        return SCTScore("SCT-008", "Direct Substrate Intervention", round(score, 2), rationale, hits[:5])

    def _score_chemical_disruption(self, corpus: str, themes: set) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, STRESS_KEYWORDS)
        score = min(1.0, kw_score)
        if score > 0.5:
            rationale = "Target shows signs of cognitive depletion — stress, exhaustion, or burnout indicators. Depleted substrates are more susceptible to all SCT vectors."
        elif score > 0.2:
            rationale = "Some stress indicators present. Moderate cognitive load may reduce resistance to influence."
        else:
            rationale = "No significant stress or depletion indicators detected."
        return SCTScore("SCT-009", "Chemical Disruption", round(score, 2), rationale, hits[:5])

    def _score_sensory_manipulation(self, corpus: str, themes: set, interests: list) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, VISUAL_KEYWORDS)
        score = min(1.0, kw_score)
        rationale = "Target shows " + ("strong" if score > 0.5 else "moderate" if score > 0.25 else "low") + " orientation toward sensory/aesthetic content. "
        if any(kw in corpus for kw in ["visual", "image", "photo", "video", "film", "art", "design"]):
            rationale += "Visual-dominant processing detected."
        elif any(kw in corpus for kw in ["music", "sound", "audio", "podcast", "voice"]):
            rationale += "Auditory-dominant processing detected."
        return SCTScore("SCT-010", "Sensory Channel Manipulation", round(score, 2), rationale, hits[:5])

    def _score_trust_destruction(self, corpus: str, themes: set, style: str) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, SKEPTICISM_KEYWORDS)
        score = min(1.0, kw_score)
        if score > 0.5:
            rationale = "Target already exhibits high institutional skepticism. This is a dual-edge vector: existing distrust can be leveraged to redirect trust toward alternative authority structures."
        elif score > 0.25:
            rationale = "Some skepticism toward institutions detected. Target questions authority but has not fully abandoned institutional trust."
        else:
            rationale = "Low institutional skepticism. Target generally trusts established institutions and information sources."
        return SCTScore("SCT-011", "Trust Infrastructure Destruction", round(score, 2), rationale, hits[:5])

    def _score_commitment_escalation(self, corpus: str, themes: set, style: str) -> SCTScore:
        kw_score, hits = self._keyword_score(corpus, COMMITMENT_KEYWORDS)
        # Loyalty/devotion language
        if any(kw in corpus for kw in ["loyal", "dedicated", "devoted", "committed", "all in"]):
            kw_score = min(1.0, kw_score + 0.15)
        score = min(1.0, kw_score)
        if score > 0.5:
            rationale = "Target shows strong commitment patterns — sunk cost susceptibility, loyalty-based identity. Gradual escalation from small commitments would be effective."
        elif score > 0.25:
            rationale = "Some commitment indicators. Target shows loyalty tendencies that could be leveraged through incremental escalation."
        else:
            rationale = "Low commitment anchoring. Target appears flexible and willing to disengage from positions."
        return SCTScore("SCT-012", "Commitment Escalation", round(score, 2), rationale, hits[:5])
