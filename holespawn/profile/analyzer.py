"""
Extract a psychological profile from social media text:
themes, sentiment, rhythm, obsessions, emotional valence, voice/style.
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

    # Voice & style (for voice-matched generation)
    communication_style: str = "conversational/rambling"
    vocabulary_sample: list[str] = field(default_factory=list)
    emoji_usage: str = "none"
    sentence_structure: str = "mixed"
    cultural_references: list[str] = field(default_factory=list)
    specific_interests: list[str] = field(default_factory=list)
    obsessions: list[str] = field(default_factory=list)
    pet_peeves: list[str] = field(default_factory=list)

    # Browsing / consumption patterns (for multi-page attention trap)
    browsing_style: str = "scanner"  # deep_diver, scanner, doom_scroller, visual_browser, thread_reader
    content_density_preference: str = "moderate"  # dense, moderate, sparse
    visual_preference: str = "balanced"  # text_heavy, balanced, image_heavy
    link_following_likelihood: str = "medium"  # high, medium, low
    color_palette: str = "neutral"
    layout_style: str = "balanced"
    typography_vibe: str = "clean sans"


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
    try:
        from tqdm import tqdm
        post_iter = tqdm(posts, desc="Analyzing posts", unit="post", leave=False)
    except ImportError:
        post_iter = posts
    for post in post_iter:
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


def _analyze_communication_style(posts: list[str]) -> str:
    """Determine how the person actually writes."""
    if not posts:
        return "conversational/rambling"
    combined = " ".join(posts).lower()
    irony_markers = ["lmao", "lol", "fr fr", "no cap", "unironically", "ngl", "tbh"]
    has_irony = sum(1 for m in irony_markers if m in combined) >= 2
    academic_markers = ["however", "moreover", "thus", "therefore", "specifically", "furthermore"]
    is_academic = sum(1 for m in academic_markers if m in combined) > 2
    cryptic_markers = ["...", "they dont want you to know", "wake up", "the truth", "they don't want"]
    is_cryptic = any(m in combined for m in cryptic_markers)
    avg_length = sum(len(p.split()) for p in posts) / len(posts) if posts else 0
    is_punchy = avg_length < 15
    if is_cryptic:
        return "cryptic/conspiratorial"
    if is_academic:
        return "academic/formal"
    if has_irony and is_punchy:
        return "casual/memey"
    if is_punchy:
        return "direct/concise"
    return "conversational/rambling"


def _extract_unique_vocabulary(posts: list[str], themes: list[tuple[str, float]], top_n: int = 30) -> list[str]:
    """Their most-used distinctive words (from themes, excluding generic)."""
    return [t[0] for t in themes[:top_n] if t[0] and len(t[0]) > 2]


def _analyze_emoji_usage(posts: list[str]) -> str:
    """Classify emoji usage level."""
    if not posts:
        return "none"
    emoji_pattern = re.compile(r"[\U0001F300-\U0001F9FF]|[\u2600-\u26FF]|[\u2700-\u27BF]")
    counts = [len(emoji_pattern.findall(p)) for p in posts]
    avg = sum(counts) / len(posts) if posts else 0
    if avg > 1.5:
        return "heavy"
    if avg > 0.3:
        return "moderate"
    return "none"


def _analyze_sentence_structure(posts: list[str]) -> str:
    """Classify sentence structure pattern."""
    if not posts:
        return "mixed"
    avg_len = sum(len(p.split()) for p in posts) / len(posts) if posts else 0
    bullet_like = sum(1 for p in posts if p.strip().startswith(("-", "*", "•")) or "\n-" in p) / max(len(posts), 1)
    if bullet_like > 0.2:
        return "bullet points"
    if avg_len < 12:
        return "short punchy"
    if avg_len > 25:
        return "long rambling"
    return "mixed"


def _extract_cultural_references(posts: list[str]) -> list[str]:
    """Identify cultural/community markers."""
    communities = {
        "tech/startup": ["shipped", "mvp", "iteration", "pivot", "build in public", "indiehacker"],
        "leftist": ["mutual aid", "praxis", "comrade", "solidarity", "acc", "e/acc"],
        "crypto": ["ngmi", "wagmi", "gm", "probably nothing", "ser"],
        "ai safety": ["alignment", "x-risk", "agi", "s-risk", "llm"],
        "gaming": ["gg", "speedrun", "meta", "rng", "grind"],
        "academia": ["arxiv", "preprint", "peer review", "citation"],
    }
    combined = " ".join(posts).lower()
    found = []
    for community, markers in communities.items():
        if any(m in combined for m in markers):
            found.append(community)
    return found[:8]


def _extract_obsessions(posts: list[str], themes: list[tuple[str, float]]) -> list[str]:
    """Topics they mention repeatedly with intensity."""
    obsessions = []
    combined = " ".join(posts).lower()
    for theme, freq in themes[:15]:
        if freq < 0.08 or not theme or len(theme) < 3:
            continue
        theme_posts = [p for p in posts if theme in p.lower()]
        if not theme_posts:
            continue
        has_intensity = any("!" in p or theme in p for p in theme_posts[:20])
        if has_intensity or freq > 0.15:
            obsessions.append(theme)
    return obsessions[:8]


def _extract_specific_interests(posts: list[str], themes: list[tuple[str, float]]) -> list[str]:
    """Concrete narrow interests from themes and phrases."""
    interests = [t[0] for t in themes[:15] if t[0] and len(t[0]) > 2 and t[1] > 0.05]
    return interests[:12]


def _extract_pet_peeves(posts: list[str]) -> list[str]:
    """Things they complain about or criticize."""
    neg_markers = ["hate", "annoying", "worst", "terrible", "why does", "cant stand", "so bad"]
    combined = " ".join(posts).lower()
    found = []
    for m in neg_markers:
        if m in combined:
            found.append(m)
    return found[:6]


def _analyze_browsing_style(posts: list[str]) -> str:
    """Infer how they consume content from posting patterns."""
    if not posts:
        return "scanner"
    combined = " ".join(posts).lower()
    n = len(posts)
    anxiety = sum(
        1 for p in posts
        if any(w in p.lower() for w in ["crisis", "worried", "anxious", "doom", "collapse", "everything is"])
    )
    if anxiety > n * 0.25:
        return "doom_scroller"
    long_posts = sum(1 for p in posts if len(p.split()) > 80)
    has_threads = sum(1 for p in posts if "1/" in p or "thread" in p.lower() or "🧵" in p)
    if (long_posts > n * 0.15) or (has_threads >= 2):
        return "deep_diver"
    image_refs = sum(
        1 for p in posts
        if any(m in p.lower() for m in ["pic", "image", "screenshot", "look at this", "photo", "📷"])
    )
    if image_refs > n * 0.25:
        return "visual_browser"
    rt_qt = sum(1 for p in posts if p.strip().startswith(("RT @", "QT", "rt @")))
    if rt_qt > n * 0.35:
        return "thread_reader"
    return "scanner"


def _analyze_content_density(posts: list[str]) -> str:
    """How much content do they prefer (from post length)."""
    if not posts:
        return "moderate"
    avg = sum(len(p.split()) for p in posts) / len(posts)
    if avg > 50:
        return "dense"
    if avg < 15:
        return "sparse"
    return "moderate"


def _infer_aesthetic_from_style(communication_style: str) -> tuple[str, str, str]:
    """Infer color_palette, layout_style, typography_vibe from communication style."""
    aesthetics = {
        "casual/memey": ("bright, high contrast", "chaotic, playful", "sans-serif, varied, emoji-friendly"),
        "academic/formal": ("muted, professional", "structured, hierarchical", "serif, consistent"),
        "cryptic/conspiratorial": ("dark, terminal-like", "minimal, stark", "monospace or distressed"),
        "direct/concise": ("clean, minimal", "brutalist, efficient", "modern sans, large clear type"),
        "conversational/rambling": ("warm, neutral", "balanced", "readable sans"),
    }
    return aesthetics.get(communication_style, ("neutral", "balanced", "clean sans"))


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

    communication_style = _analyze_communication_style(posts)
    vocabulary_sample = _extract_unique_vocabulary(posts, themes)
    emoji_usage = _analyze_emoji_usage(posts)
    sentence_structure = _analyze_sentence_structure(posts)
    cultural_references = _extract_cultural_references(posts)
    obsessions = _extract_obsessions(posts, themes)
    specific_interests = _extract_specific_interests(posts, themes)
    pet_peeves = _extract_pet_peeves(posts)

    browsing_style = _analyze_browsing_style(posts)
    content_density_preference = _analyze_content_density(posts)
    color_palette, layout_style, typography_vibe = _infer_aesthetic_from_style(communication_style)
    visual_preference = "image_heavy" if browsing_style == "visual_browser" else ("text_heavy" if content_density_preference == "dense" else "balanced")
    link_following_likelihood = "high" if browsing_style in ("deep_diver", "doom_scroller") else ("medium" if browsing_style == "thread_reader" else "low")

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
        communication_style=communication_style,
        vocabulary_sample=vocabulary_sample,
        emoji_usage=emoji_usage,
        sentence_structure=sentence_structure,
        cultural_references=cultural_references,
        specific_interests=specific_interests,
        obsessions=obsessions,
        pet_peeves=pet_peeves,
        browsing_style=browsing_style,
        content_density_preference=content_density_preference,
        visual_preference=visual_preference,
        link_following_likelihood=link_following_likelihood,
        color_palette=color_palette,
        layout_style=layout_style,
        typography_vibe=typography_vibe,
    )
