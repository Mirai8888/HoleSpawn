"""
Extract a psychological profile from social media text:
themes, sentiment, rhythm, obsessions, emotional valence, voice/style.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from holespawn.ingest import SocialContent

# Theme frequency classification (typical social media word distribution)
THEME_FREQUENCY_RARE_THRESHOLD = 0.08  # Below this = mentioned infrequently
THEME_FREQUENCY_OBSESSION_THRESHOLD = 0.15  # Above this = core obsession

# Emotional intensity threshold for pattern detection (VADER compound)
EMOTIONAL_INTENSITY_THRESHOLD = 0.3

# Analysis parameters
TOP_THEMES_COUNT = 20  # Good coverage without noise
MIN_POSTS_FOR_ANALYSIS = 5  # Minimum posts for reliable profiling

try:
    from loguru import logger
except ImportError:
    logger = None


# Common stopwords (English) for theme extraction
STOP = {
    "i",
    "me",
    "my",
    "myself",
    "we",
    "our",
    "ours",
    "ourselves",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "he",
    "him",
    "his",
    "himself",
    "she",
    "her",
    "hers",
    "herself",
    "it",
    "its",
    "itself",
    "they",
    "them",
    "their",
    "theirs",
    "themselves",
    "what",
    "which",
    "who",
    "whom",
    "this",
    "that",
    "these",
    "those",
    "am",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "a",
    "an",
    "the",
    "and",
    "but",
    "if",
    "or",
    "because",
    "as",
    "until",
    "while",
    "of",
    "at",
    "by",
    "for",
    "with",
    "about",
    "against",
    "between",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "to",
    "from",
    "up",
    "down",
    "in",
    "out",
    "on",
    "off",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "s",
    "t",
    "can",
    "will",
    "just",
    "don",
    "should",
    "now",
    "rt",
    "via",
    "amp",
    "like",
    "get",
    "got",
    "im",
    # Contractions and informal
    "it's", "i'm", "don't", "can't", "won't", "didn't", "doesn't", "isn't",
    "aren't", "wasn't", "weren't", "haven't", "hasn't", "hadn't", "wouldn't",
    "shouldn't", "couldn't", "i've", "you've", "we've", "they've", "i'll",
    "you'll", "we'll", "they'll", "i'd", "you'd", "we'd", "they'd", "that's",
    "there's", "here's", "what's", "who's", "let's", "it'll", "he's", "she's",
    "ive", "youve", "weve", "theyve", "ill", "youll", "well", "theyll",
    "id", "youd", "wed", "theyd", "thats", "theres", "heres", "whats",
    # Common short words that aren't meaningful themes
    "one", "two", "three", "new", "old", "even", "also", "still", "much",
    "many", "way", "thing", "things", "something", "anything", "everything",
    "nothing", "someone", "anyone", "everyone", "really", "actually", "basically",
    "literally", "maybe", "probably", "definitely", "absolutely", "pretty",
    "quite", "rather", "always", "never", "often", "sometimes", "already",
    "yet", "ever", "since", "today", "tomorrow", "yesterday", "tonight",
    "back", "going", "come", "came", "goes", "went", "take", "took",
    "make", "made", "making", "say", "said", "says", "saying",
    "think", "thought", "know", "knew", "see", "saw", "look", "looking",
    "want", "need", "use", "used", "using", "try", "tried",
    "give", "gave", "put", "keep", "kept", "let", "seem", "seemed",
    "tell", "told", "find", "found", "call", "called", "ask", "asked",
    "work", "feel", "felt", "leave", "left", "long", "right", "big",
    "good", "bad", "great", "little", "lot", "lots", "bit", "kind",
    "part", "point", "place", "time", "times", "year", "years", "day", "days",
    "week", "weeks", "month", "months", "world", "life", "people", "person",
    "man", "woman", "guy", "first", "last", "next", "end", "start",
    "different", "every", "another", "whole", "real", "sure", "full",
    "later", "earlier", "ago", "away", "around", "else", "though",
    "enough", "almost", "getting", "better", "best", "worst", "hard",
    "easy", "far", "close", "high", "low", "small", "large",
    # URL fragments and social media noise
    "com", "www", "https", "http", "org", "net", "io", "co",
    "pic", "twitter", "status", "utm", "ref", "source", "amp",
    "lol", "lmao", "omg", "tbh", "imo", "imho", "smh", "ngl",
    # Additional common non-meaningful words
    "yes", "no", "per", "would", "could", "might", "may", "must",
    "shall", "will", "won", "re", "ve", "ll", "isn", "aren", "wasn",
    "weren", "haven", "hasn", "hadn", "wouldn", "shouldn", "couldn",
    "doesn", "didn", "won", "super", "totally", "finally", "especially",
    "please", "thanks", "thank", "sorry", "okay", "ok", "oh", "well",
    "hey", "hi", "hello", "yeah", "yep", "nope", "nah", "hmm",
    "watching", "version", "final", "happen", "happened", "happening",
    "goes", "mean", "means", "set", "run", "running", "read", "reading",
    "writes", "write", "writing", "saw", "seen", "hear", "heard",
    "believe", "guess", "hope", "wish", "wonder",
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
    browsing_style: str = (
        "scanner"  # deep_diver, scanner, doom_scroller, visual_browser, thread_reader
    )
    content_density_preference: str = "moderate"  # dense, moderate, sparse
    visual_preference: str = "balanced"  # text_heavy, balanced, image_heavy
    link_following_likelihood: str = "medium"  # high, medium, low
    color_palette: str = "neutral"
    layout_style: str = "balanced"
    typography_vibe: str = "clean sans"

    # Discord-specific (when content.discord_data is present)
    tribal_affiliations: list[str] = field(default_factory=list)  # Server themes/values
    reaction_triggers: list[str] = field(default_factory=list)  # What gets emotional response
    conversational_intimacy: str = "moderate"  # guarded | open | vulnerable
    community_role: str = "participant"  # lurker | participant | leader
    engagement_rhythm: dict = field(default_factory=dict)  # Activity patterns (peak_hours, etc.)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z0-9']+\b", text.lower())


def _extract_themes(posts: list[str], top_n: int = 25) -> list[tuple[str, float]]:
    counter: Counter[str] = Counter()
    for post in posts:
        for w in _tokenize(post):
            # Skip stopwords, single chars, pure numbers, and very short tokens
            if w not in STOP and len(w) > 2 and not w.isdigit() and not w.replace(".", "").isdigit():
                counter[w] += 1
    total = sum(counter.values())
    if total == 0:
        if logger:
            logger.warning("No valid themes extracted (all stopwords)")
        return []
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
    n = len(posts)

    # Score multiple style dimensions
    irony_markers = ["lmao", "lol", "fr fr", "no cap", "unironically", "ngl", "tbh", "bruh"]
    irony_score = sum(1 for m in irony_markers if m in combined)

    academic_markers = ["however", "moreover", "thus", "therefore", "specifically",
                        "furthermore", "consequently", "methodology", "hypothesis",
                        "peer-reviewed", "empirically", "systematically"]
    academic_score = sum(1 for m in academic_markers if m in combined)

    # Conspiratorial requires STRONG signals, not just "..."
    conspiracy_markers = ["they dont want you to know", "they don't want you to know",
                          "wake up sheeple", "open your eyes", "deep state",
                          "the elites", "cover-up", "coverup", "psyop"]
    conspiracy_score = sum(1 for m in conspiracy_markers if m in combined)

    # Technical/insider voice — domain expertise + insider framing
    technical_markers = ["implementation", "architecture", "protocol", "infrastructure",
                         "specification", "configuration", "vulnerability", "exploit",
                         "firmware", "compiler", "kernel", "api", "endpoint",
                         "latency", "throughput", "stack", "pipeline", "deployment"]
    technical_score = sum(1 for m in technical_markers if m in combined)

    # Observational/analytical — pattern recognition language
    analytical_markers = ["interesting", "notable", "pattern", "trend", "correlation",
                          "implication", "context", "nuance", "counterpoint",
                          "observation", "in other words", "which means"]
    analytical_score = sum(1 for m in analytical_markers if m in combined)

    # Passionate/advocacy — cause-driven language
    advocacy_markers = ["must", "should", "need to", "important", "critical",
                        "unacceptable", "demand", "fight", "protect", "defend",
                        "stand up", "speak out", "justice", "rights"]
    advocacy_score = sum(1 for m in advocacy_markers if m in combined)

    avg_length = sum(len(p.split()) for p in posts) / n
    is_punchy = avg_length < 15
    is_verbose = avg_length > 30

    # Classify by highest signal
    scores = {
        "technical/insider": technical_score * 1.5,
        "academic/formal": academic_score * 2.0,
        "analytical/observational": analytical_score * 1.5,
        "casual/memey": irony_score * 2.0,
        "passionate/advocacy": advocacy_score * 1.0,
        "cryptic/conspiratorial": conspiracy_score * 3.0,
    }

    best_style = max(scores, key=scores.get)
    best_score = scores[best_style]

    # Require minimum signal strength
    if best_score >= 3:
        return best_style

    # Fall back to structural analysis
    if is_punchy:
        return "direct/concise"
    if is_verbose:
        return "conversational/rambling"
    return "conversational/mixed"


def _extract_unique_vocabulary(
    posts: list[str], themes: list[tuple[str, float]], top_n: int = 30
) -> list[str]:
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
    if avg > EMOTIONAL_INTENSITY_THRESHOLD:
        return "moderate"
    return "none"


def _analyze_sentence_structure(posts: list[str]) -> str:
    """Classify sentence structure pattern."""
    if not posts:
        return "mixed"
    avg_len = sum(len(p.split()) for p in posts) / len(posts) if posts else 0
    bullet_like = sum(
        1 for p in posts if p.strip().startswith(("-", "*", "•")) or "\n-" in p
    ) / max(len(posts), 1)
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
    # Use top themes regardless of frequency — the ranking itself signals interest
    # Original 0.05 threshold was too aggressive for diverse profiles
    interests = [t[0] for t in themes[:20] if t[0] and len(t[0]) > 2 and t[1] > 0.01]
    if len(interests) < 5:
        # Fall back to raw top themes if threshold filters too aggressively
        interests = [t[0] for t in themes[:12] if t[0] and len(t[0]) > 2]
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
        1
        for p in posts
        if any(
            w in p.lower()
            for w in ["crisis", "worried", "anxious", "doom", "collapse", "everything is"]
        )
    )
    if anxiety > n * 0.25:
        return "doom_scroller"
    long_posts = sum(1 for p in posts if len(p.split()) > 80)
    has_threads = sum(1 for p in posts if "1/" in p or "thread" in p.lower() or "🧵" in p)
    if (long_posts > n * 0.15) or (has_threads >= 2):
        return "deep_diver"
    image_refs = sum(
        1
        for p in posts
        if any(
            m in p.lower() for m in ["pic", "image", "screenshot", "look at this", "photo", "📷"]
        )
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
        "casual/memey": (
            "bright, high contrast",
            "chaotic, playful",
            "sans-serif, varied, emoji-friendly",
        ),
        "academic/formal": ("muted, professional", "structured, hierarchical", "serif, consistent"),
        "cryptic/conspiratorial": (
            "dark, terminal-like",
            "minimal, stark",
            "monospace or distressed",
        ),
        "direct/concise": (
            "clean, minimal",
            "brutalist, efficient",
            "modern sans, large clear type",
        ),
        "conversational/rambling": ("warm, neutral", "balanced", "readable sans"),
        "conversational/mixed": ("warm, neutral", "balanced", "readable sans"),
        "technical/insider": (
            "dark, terminal-like",
            "structured, code-inspired",
            "monospace, technical",
        ),
        "analytical/observational": (
            "cool, muted blues",
            "structured, hierarchical",
            "clean serif, data-focused",
        ),
        "passionate/advocacy": (
            "bold, warm contrast",
            "dynamic, action-oriented",
            "strong sans-serif, impactful",
        ),
    }
    return aesthetics.get(communication_style, ("neutral", "balanced", "clean sans"))


def _extract_discord_signals(discord_data: dict) -> dict:
    """
    Extract Discord-specific profile signals from export payload.
    Returns dict with tribal_affiliations, reaction_triggers, conversational_intimacy,
    community_role, engagement_rhythm.
    """
    out: dict = {
        "tribal_affiliations": [],
        "reaction_triggers": [],
        "conversational_intimacy": "moderate",
        "community_role": "participant",
        "engagement_rhythm": {},
    }
    if not discord_data:
        return out

    # Tribal affiliations: server names as community themes
    servers = discord_data.get("servers") or []
    for s in servers:
        if isinstance(s, dict) and s.get("server_name"):
            out["tribal_affiliations"].append(str(s["server_name"]).strip())
        elif isinstance(s, str):
            out["tribal_affiliations"].append(s.strip())
    out["tribal_affiliations"] = list(dict.fromkeys(out["tribal_affiliations"]))[:15]

    # Reaction triggers: themes from messages they reacted to (reactions_given.message_content)
    reactions_given = discord_data.get("reactions_given") or []
    reacted_contents: list[str] = []
    for r in reactions_given:
        if isinstance(r, dict) and r.get("message_content"):
            reacted_contents.append(str(r["message_content"]).strip()[:200])
    if reacted_contents:
        # Simple word extraction for themes they emotionally engage with
        combined = " ".join(reacted_contents).lower()
        words = re.findall(r"\b[a-z]{4,}\b", combined)
        from collections import Counter

        stop = STOP | {
            "this",
            "that",
            "what",
            "when",
            "with",
            "from",
            "have",
            "been",
            "were",
            "about",
        }
        counts = Counter(w for w in words if w not in stop)
        out["reaction_triggers"] = [w for w, _ in counts.most_common(12)]

    # Conversational intimacy: from message length and vulnerability markers
    messages = discord_data.get("messages") or []
    if messages:
        contents = []
        for m in messages:
            if isinstance(m, dict) and m.get("content"):
                contents.append(str(m["content"]))
        if contents:
            avg_len = sum(len(c.split()) for c in contents) / len(contents)
            combined = " ".join(contents).lower()
            vulnerable = sum(
                1
                for w in [
                    "honestly",
                    "actually",
                    "feel",
                    "struggle",
                    "anxious",
                    "worried",
                    "idk",
                    "imo",
                    "tbh",
                ]
                if w in combined
            )
            if avg_len > 40 and vulnerable > 2:
                out["conversational_intimacy"] = "vulnerable"
            elif avg_len < 12 and vulnerable < 1:
                out["conversational_intimacy"] = "guarded"
            else:
                out["conversational_intimacy"] = "open"

    # Community role: from interactions and message volume
    interactions = discord_data.get("interactions") or []
    total_interactions = (
        sum(int(x.get("interaction_count", 0)) for x in interactions if isinstance(x, dict))
        if interactions
        else 0
    )
    msg_count = len(discord_data.get("messages") or [])
    if msg_count > 100 and total_interactions > 50:
        out["community_role"] = "leader"
    elif msg_count < 20:
        out["community_role"] = "lurker"
    else:
        out["community_role"] = "participant"

    # Engagement rhythm: pass through activity_patterns
    activity = discord_data.get("activity_patterns") or {}
    if isinstance(activity, dict):
        out["engagement_rhythm"] = {
            k: v
            for k, v in activity.items()
            if k in ("peak_hours", "active_days", "message_frequency")
        }

    return out


def build_profile(content: SocialContent) -> PsychologicalProfile:
    """Build a psychological profile from ingested social content."""
    posts = list(content.iter_posts())
    if not posts:
        raise ValueError("Cannot build profile from empty posts list")
    if len(posts) < MIN_POSTS_FOR_ANALYSIS and logger:
        logger.warning(
            "Building profile from only {} posts - results may be unreliable",
            len(posts),
        )
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
    visual_preference = (
        "image_heavy"
        if browsing_style == "visual_browser"
        else ("text_heavy" if content_density_preference == "dense" else "balanced")
    )
    link_following_likelihood = (
        "high"
        if browsing_style in ("deep_diver", "doom_scroller")
        else ("medium" if browsing_style == "thread_reader" else "low")
    )

    # Discord-specific signals when present
    discord_supplement = _extract_discord_signals(getattr(content, "discord_data", None))

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
        tribal_affiliations=discord_supplement["tribal_affiliations"],
        reaction_triggers=discord_supplement["reaction_triggers"],
        conversational_intimacy=discord_supplement["conversational_intimacy"],
        community_role=discord_supplement["community_role"],
        engagement_rhythm=discord_supplement["engagement_rhythm"],
    )
