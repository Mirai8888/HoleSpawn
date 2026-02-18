"""
Dual-substrate detection: classify text output as human or LLM-generated.

Signals used:
- Lexical uniformity (LLMs have lower vocabulary variance per token window)
- Refusal/safety markers ("I cannot", "as an AI", "I apologize")
- Hedging density ("it's important to note", "however", "that being said")
- Sentence length variance (LLMs tend toward uniform sentence lengths)
- Repetition signatures (phrase-level self-repetition across outputs)
- Punctuation patterns (LLMs overuse em dashes, semicolons, colons)
- Instruction-following artifacts (numbered lists, "here's", "let me")
- Temperature signatures (low temp = repetitive, high temp = incoherent)

Returns a SubstrateSignal with classification and confidence.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field

# --- Marker lexicons ---

REFUSAL_MARKERS = [
    "i cannot", "i can't", "as an ai", "as a language model", "i'm not able to",
    "i apologize", "i'm sorry but", "i must decline", "it would be inappropriate",
    "i don't have the ability", "beyond my capabilities", "i'm unable to",
]

HEDGING_MARKERS = [
    "it's important to note", "it is important to note", "it's worth noting",
    "however", "that being said", "having said that", "on the other hand",
    "it should be noted", "keep in mind", "generally speaking",
    "in my opinion", "arguably", "to be fair", "it depends on",
]

INSTRUCTION_ARTIFACTS = [
    "here's", "here is", "let me", "i'll", "i will",
    "first,", "second,", "third,", "finally,",
    "in summary", "to summarize", "in conclusion",
    "sure!", "absolutely!", "great question",
    "i'd be happy to", "i hope this helps",
]

# Patterns LLMs overuse
LLM_PUNCTUATION = re.compile(r'[—;:]')
NUMBERED_LIST = re.compile(r'^\s*\d+[\.\)]\s', re.MULTILINE)
BULLET_LIST = re.compile(r'^\s*[-•*]\s', re.MULTILINE)
MARKDOWN_HEADER = re.compile(r'^#{1,6}\s', re.MULTILINE)


@dataclass
class SubstrateSignal:
    """Result of substrate classification."""
    classification: str  # "human", "llm", "uncertain"
    confidence: float  # 0.0 to 1.0
    scores: dict = field(default_factory=dict)  # individual signal scores
    markers_found: list[str] = field(default_factory=list)
    temperature_estimate: str = "unknown"  # "low", "medium", "high", "unknown"


def _marker_density(text_lower: str, markers: list[str]) -> tuple[float, list[str]]:
    """Count marker hits per 1000 chars."""
    found = []
    for m in markers:
        if m in text_lower:
            found.append(m)
    if not text_lower:
        return 0.0, found
    return (len(found) / max(len(text_lower), 1)) * 1000, found


def _lexical_uniformity(posts: list[str]) -> float:
    """
    Measure vocabulary variance across posts.
    LLMs reuse the same vocabulary more consistently.
    Returns 0-1 where higher = more uniform (more LLM-like).
    """
    if len(posts) < 3:
        return 0.5  # insufficient data

    vocab_sets = []
    for p in posts:
        words = set(re.findall(r'\b[a-z]{3,}\b', p.lower()))
        if words:
            vocab_sets.append(words)

    if len(vocab_sets) < 3:
        return 0.5

    # Jaccard similarity between consecutive posts
    similarities = []
    for i in range(len(vocab_sets) - 1):
        a, b = vocab_sets[i], vocab_sets[i + 1]
        if a or b:
            similarities.append(len(a & b) / max(len(a | b), 1))

    if not similarities:
        return 0.5

    avg_sim = sum(similarities) / len(similarities)
    # Humans typically 0.05-0.20, LLMs 0.15-0.40
    return min(avg_sim / 0.4, 1.0)


def _sentence_length_variance(text: str) -> float:
    """
    LLMs produce more uniform sentence lengths.
    Returns coefficient of variation (lower = more uniform = more LLM-like).
    """
    sentences = re.split(r'[.!?]+', text)
    lengths = [len(s.split()) for s in sentences if len(s.split()) > 2]

    if len(lengths) < 5:
        return 0.5  # insufficient data

    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return 0.5
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    cv = math.sqrt(variance) / mean

    # Humans typically CV 0.5-1.2, LLMs 0.2-0.5
    return cv


def _repetition_score(posts: list[str]) -> float:
    """
    Detect phrase-level self-repetition across posts.
    LLMs at low temperature repeat structural phrases.
    Returns 0-1 where higher = more repetitive.
    """
    if len(posts) < 3:
        return 0.0

    # Extract 3-grams
    trigrams = Counter()
    for p in posts:
        words = re.findall(r'\b[a-z]+\b', p.lower())
        for i in range(len(words) - 2):
            trigrams[tuple(words[i:i+3])] += 1

    if not trigrams:
        return 0.0

    # Count trigrams appearing in multiple posts
    repeated = sum(1 for _, c in trigrams.items() if c > 2)
    total = len(trigrams)

    return min(repeated / max(total, 1) * 5, 1.0)


def _formatting_score(text: str) -> float:
    """
    Detect LLM formatting artifacts: markdown, numbered lists, bullet points.
    Returns 0-1 where higher = more LLM-like.
    """
    char_count = max(len(text), 1)
    signals = 0.0

    # Em dash density (LLMs LOVE em dashes)
    em_dashes = text.count('—') + text.count(' - ')
    signals += min(em_dashes / (char_count / 500), 0.3)

    # Numbered/bullet lists
    num_lists = len(NUMBERED_LIST.findall(text))
    bullet_lists = len(BULLET_LIST.findall(text))
    signals += min((num_lists + bullet_lists) / (char_count / 1000), 0.3)

    # Markdown headers
    headers = len(MARKDOWN_HEADER.findall(text))
    signals += min(headers / (char_count / 2000), 0.2)

    # Semicolon/colon density
    semicolons = text.count(';') + text.count(':')
    signals += min(semicolons / (char_count / 300), 0.2)

    return min(signals, 1.0)


def _estimate_temperature(posts: list[str]) -> str:
    """Estimate generation temperature from output characteristics."""
    if len(posts) < 3:
        return "unknown"

    rep = _repetition_score(posts)
    cv = _sentence_length_variance(" ".join(posts))

    if rep > 0.5 and cv < 0.35:
        return "low"
    elif rep < 0.15 and cv > 0.8:
        return "high"
    elif rep > 0.2 or cv < 0.5:
        return "medium"
    return "unknown"


def detect_substrate(posts: list[str]) -> SubstrateSignal:
    """
    Classify a collection of text outputs as human or LLM-generated.

    Args:
        posts: List of text outputs (social posts, chat messages, API responses, etc.)

    Returns:
        SubstrateSignal with classification and breakdown.
    """
    if not posts:
        return SubstrateSignal(classification="uncertain", confidence=0.0)

    full_text = "\n".join(posts)
    text_lower = full_text.lower()

    scores = {}
    all_markers = []

    # 1. Refusal markers
    refusal_density, refusal_found = _marker_density(text_lower, REFUSAL_MARKERS)
    scores["refusal"] = min(refusal_density / 2.0, 1.0)
    all_markers.extend(refusal_found)

    # 2. Hedging markers
    hedge_density, hedge_found = _marker_density(text_lower, HEDGING_MARKERS)
    scores["hedging"] = min(hedge_density / 3.0, 1.0)
    all_markers.extend(hedge_found)

    # 3. Instruction-following artifacts
    instr_density, instr_found = _marker_density(text_lower, INSTRUCTION_ARTIFACTS)
    scores["instruction_artifacts"] = min(instr_density / 3.0, 1.0)
    all_markers.extend(instr_found)

    # 4. Lexical uniformity
    scores["lexical_uniformity"] = _lexical_uniformity(posts)

    # 5. Sentence length variance (invert: lower CV = more LLM-like)
    cv = _sentence_length_variance(full_text)
    scores["sentence_uniformity"] = max(0, 1.0 - cv)

    # 6. Repetition
    scores["repetition"] = _repetition_score(posts)

    # 7. Formatting artifacts
    scores["formatting"] = _formatting_score(full_text)

    # Weighted composite
    weights = {
        "refusal": 3.0,        # Very strong signal
        "hedging": 1.5,
        "instruction_artifacts": 2.0,
        "lexical_uniformity": 1.0,
        "sentence_uniformity": 1.0,
        "repetition": 1.5,
        "formatting": 1.5,
    }

    weighted_sum = sum(scores[k] * weights[k] for k in weights)
    max_weighted = sum(weights.values())
    composite = weighted_sum / max_weighted

    # Classification thresholds
    if composite > 0.45:
        classification = "llm"
        confidence = min(composite * 1.5, 1.0)
    elif composite > 0.25:
        classification = "uncertain"
        confidence = 0.5
    else:
        classification = "human"
        confidence = min((1.0 - composite) * 1.2, 1.0)

    temp = _estimate_temperature(posts)

    return SubstrateSignal(
        classification=classification,
        confidence=round(confidence, 3),
        scores={k: round(v, 3) for k, v in scores.items()},
        markers_found=all_markers,
        temperature_estimate=temp,
    )
