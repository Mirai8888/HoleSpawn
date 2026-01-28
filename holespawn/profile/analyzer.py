"""
Extract a psychological profile from social media text:
themes, sentiment, rhythm, obsessions, emotional valence.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from holespawn.ingest import SocialContent


# Common stopwords (English) for theme extraction
STOP = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your",
    "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she",
    "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
    "these", "those", "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an",
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of",
    "at", "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just",
    "don", "should", "now", "rt", "via", "amp", "like", "get", "got", "im",
}


@dataclass
class PsychologicalProfile:
    """Derived profile for ARG generation."""

    # Recurring themes (words/phrases)
    themes: list[tuple[str, float]] = field(default_factory=list)
    # Sentiment: compound (-1 to 1), positive/negative/neutral ratios
    sentiment_compound: float = 0.0
    sentiment_positive: float = 0.0
    sentiment_negative: float = 0.0
    sentiment_neutral: float = 0.0
    # Writing style
    avg_sentence_length: float = 0.0
    avg_word_length: float = 0.0
    exclamation_ratio: float = 0.0
    question_ratio: float = 0.0
    # Emotional intensity (from VADER)
    intensity: float = 0.0
    # Sample phrases (short memorable fragments from source)
    sample_phrases: list[str] = field(default_factory=list)
    # Raw word frequency for generator
    word_freq: dict[str, float] = field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z0-9']+\b", text.lower())


def _extract_themes(posts: list[str], top_n: int = 25) -> list[tuple[str, float]]:
    counter: Counter[str] = Counter()
    for post in posts:
        for w in _tokenize(post):
            if w not in STOP and len(w) > 1:
                counter[w] += 1
    total = sum(counter.values()) or 1
    return [(w, count / total) for w, count in counter.most_common(top_n)]


def _sentiment_stats(posts: list[str]) -> tuple[float, float, float, float, float]:
    vader = SentimentIntensityAnalyzer()
    compounds = []
    pos, neg, neu = [], [], []
    for post in posts:
        if not post.strip():
            continue
        s = vader.polarity_scores(post)
        compounds.append(s["compound"])
        pos.append(s["pos"])
        neg.append(s["neg"])
        neu.append(s["neu"])
    n = len(compounds) or 1
    intensity = sum(abs(c) for c in compounds) / n
    return (
        sum(compounds) / n,
        sum(pos) / n,
        sum(neg) / n,
        sum(neu) / n,
        intensity,
    )


def _style_stats(full_text: str) -> tuple[float, float, float, float]:
    sentences = re.split(r"[.!?]+", full_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = _tokenize(full_text)
    n_sent = len(sentences) or 1
    n_word = len(words) or 1
    avg_sent_len = n_word / n_sent
    avg_word_len = sum(len(w) for w in words) / n_word if words else 0
    exclam = full_text.count("!") / n_sent if n_sent else 0
    quest = full_text.count("?") / n_sent if n_sent else 0
    return avg_sent_len, avg_word_len, exclam, quest


def _sample_phrases(posts: list[str], max_phrases: int = 15) -> list[str]:
    """Short, memorable fragments (first few words of longer posts)."""
    out = []
    for p in posts:
        p = p.strip()
        if len(p) < 10:
            continue
        words = p.split()[:6]
        phrase = " ".join(words)
        if len(phrase) >= 8 and phrase not in out:
            out.append(phrase)
        if len(out) >= max_phrases:
            break
    return out


def build_profile(content: SocialContent) -> PsychologicalProfile:
    """Build a psychological profile from ingested social content."""
    posts = list(content.iter_posts())
    full_text = content.full_text()

    themes = _extract_themes(posts)
    (
        sentiment_compound,
        sentiment_positive,
        sentiment_negative,
        sentiment_neutral,
        intensity,
    ) = _sentiment_stats(posts)
    avg_sent_len, avg_word_len, exclam_ratio, question_ratio = _style_stats(full_text)
    sample_phrases = _sample_phrases(posts)
    total = sum(c for _, c in themes) or 1
    word_freq = {w: c / total for w, c in themes}

    return PsychologicalProfile(
        themes=themes,
        sentiment_compound=sentiment_compound,
        sentiment_positive=sentiment_positive,
        sentiment_negative=sentiment_negative,
        sentiment_neutral=sentiment_neutral,
        avg_sentence_length=avg_sent_len,
        avg_word_length=avg_word_len,
        exclamation_ratio=exclam_ratio,
        question_ratio=question_ratio,
        intensity=intensity,
        sample_phrases=sample_phrases,
        word_freq=word_freq,
    )
