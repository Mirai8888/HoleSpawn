"""
Sensemaking Collapse Detector.

Measures narrative coherence in a community over time. When coherence drops
sharply -- conflicting narratives spike, framework-seeking language increases,
authority trust metrics fall -- that's a sensemaking collapse: a threshold
moment for intervention.

Theoretical foundations:
- Weick (1993) "The Collapse of Sensemaking in Organizations" -- cosmology
  episodes occur when people lose the sense that the universe is rational
  and orderly. Both the sense of what is occurring AND the means to rebuild
  that sense collapse simultaneously.
- Shannon entropy over topic distributions measures narrative diversity.
  Low entropy = consensus. High entropy = fragmentation.
- Jensen-Shannon divergence between time windows detects distributional
  shift in community discourse.
- VADER sentiment variance measures affective polarization. High variance
  means the community can't agree on how to feel.
- LIWC-inspired lexicons detect cognitive processing markers: tentative
  language ("maybe", "perhaps"), certainty language ("always", "definitely"),
  and causation-seeking ("because", "why", "how come"). Ratio shifts
  indicate sensemaking state transitions.

Metrics produced:
1. Narrative entropy (H): Shannon entropy over topic/keyword distribution
2. Narrative divergence (JSD): Jensen-Shannon divergence between windows
3. Sentiment dispersion (σ): Variance of sentiment scores across posts
4. Framework-seeking index (FSI): Rate of causation/explanation-seeking language
5. Authority trust index (ATI): Ratio of authority-citing vs authority-questioning
6. Coherence score (C): Composite metric, 0-1 scale
7. Collapse signal: Boolean threshold + severity when C drops sharply

All metrics are computed from raw text without LLM calls. Pure NLP.
No external API dependencies.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Sequence

logger = logging.getLogger(__name__)

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
except ImportError:
    _vader = None
    logger.warning("vaderSentiment not available; sentiment metrics disabled")


# ---------------------------------------------------------------------------
# Lexicons (LIWC-inspired, no license dependency)
# ---------------------------------------------------------------------------

# Framework-seeking: language that seeks causal explanations
CAUSATION_WORDS = frozenset({
    "because", "why", "cause", "caused", "causing", "reason", "reasons",
    "therefore", "hence", "thus", "since", "due", "owing", "explains",
    "explained", "explanation", "how come", "what happened", "makes sense",
    "doesn't make sense", "figure out", "understand", "understanding",
    "confused", "confusing", "unclear", "what does this mean", "meaning",
    "interpret", "interpretation", "framework", "paradigm", "theory",
    "narrative", "story", "account for", "justify", "justification",
})

# Tentative / uncertainty markers
TENTATIVE_WORDS = frozenset({
    "maybe", "perhaps", "possibly", "might", "could", "seems", "appears",
    "apparently", "supposedly", "allegedly", "uncertain", "unsure", "doubt",
    "doubtful", "questionable", "unclear", "ambiguous", "idk", "dunno",
    "not sure", "hard to say", "who knows", "guess", "guessing",
    "probably", "likely", "unlikely", "wonder", "wondering",
})

# Certainty / conviction markers
CERTAINTY_WORDS = frozenset({
    "always", "never", "definitely", "certainly", "absolutely", "clearly",
    "obviously", "undoubtedly", "without doubt", "no question", "proven",
    "fact", "facts", "truth", "true", "false", "lie", "lies", "guaranteed",
    "100%", "totally", "completely", "entirely", "exactly", "precisely",
    "known", "established", "confirmed", "evidence", "proof",
})

# Authority trust markers
AUTHORITY_TRUST_WORDS = frozenset({
    "expert", "experts", "authority", "authorities", "official", "officials",
    "according to", "research shows", "studies show", "scientists",
    "government", "institution", "institutional", "credible", "reliable",
    "trustworthy", "verified", "confirmed by", "reported by", "source",
})

# Authority distrust markers
AUTHORITY_DISTRUST_WORDS = frozenset({
    "they don't want you to know", "cover up", "coverup", "censored",
    "suppressed", "propaganda", "controlled", "manipulation", "manipulated",
    "sheep", "sheeple", "wake up", "woke", "mainstream", "msm",
    "can't trust", "don't trust", "untrustworthy", "corrupt", "corruption",
    "agenda", "narrative", "psyop", "false flag", "hoax", "scam",
    "grifter", "shill", "bought", "paid", "compromised", "biased",
    "disinformation", "misinformation", "fake news", "liar", "liars",
})

# Stopwords for topic extraction
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into", "about",
    "that", "this", "it", "its", "they", "them", "their", "we", "our",
    "you", "your", "he", "she", "his", "her", "i", "me", "my", "and",
    "or", "but", "not", "no", "if", "so", "just", "than", "then", "when",
    "what", "which", "who", "how", "all", "each", "every", "both", "few",
    "more", "most", "other", "some", "such", "only", "own", "same", "too",
    "very", "also", "up", "out", "get", "got", "one", "two", "like",
    "even", "new", "know", "think", "see", "go", "going", "come", "make",
    "take", "want", "look", "use", "find", "give", "tell", "say", "said",
    "really", "right", "well", "still", "back", "much", "many", "any",
    "way", "thing", "things", "people", "time", "now", "here", "there",
})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WindowMetrics:
    """Metrics for a single time window."""
    window_id: str
    post_count: int = 0
    word_count: int = 0
    # Narrative
    narrative_entropy: float = 0.0  # Shannon entropy over topic distribution
    top_topics: list[tuple[str, int]] = field(default_factory=list)
    topic_count: int = 0
    # Sentiment
    sentiment_mean: float = 0.0
    sentiment_variance: float = 0.0
    sentiment_scores: list[float] = field(default_factory=list)
    # Language markers
    causation_rate: float = 0.0  # causation words / total words
    tentative_rate: float = 0.0
    certainty_rate: float = 0.0
    framework_seeking_index: float = 0.0  # (causation + tentative) / (certainty + epsilon)
    # Authority
    authority_trust_rate: float = 0.0
    authority_distrust_rate: float = 0.0
    authority_trust_index: float = 0.0  # trust / (trust + distrust + epsilon)

    def to_dict(self) -> dict:
        return {
            "window_id": self.window_id,
            "post_count": self.post_count,
            "word_count": self.word_count,
            "narrative_entropy": round(self.narrative_entropy, 4),
            "top_topics": self.top_topics[:10],
            "topic_count": self.topic_count,
            "sentiment_mean": round(self.sentiment_mean, 4),
            "sentiment_variance": round(self.sentiment_variance, 4),
            "causation_rate": round(self.causation_rate, 6),
            "tentative_rate": round(self.tentative_rate, 6),
            "certainty_rate": round(self.certainty_rate, 6),
            "framework_seeking_index": round(self.framework_seeking_index, 4),
            "authority_trust_rate": round(self.authority_trust_rate, 6),
            "authority_distrust_rate": round(self.authority_distrust_rate, 6),
            "authority_trust_index": round(self.authority_trust_index, 4),
        }


@dataclass
class CollapseSignal:
    """A detected sensemaking collapse event."""
    window_id: str
    severity: float  # 0-1, higher = more severe
    coherence_score: float  # composite coherence at this window
    coherence_delta: float  # change from previous window
    contributing_factors: list[str] = field(default_factory=list)
    metrics: WindowMetrics | None = None

    def to_dict(self) -> dict:
        d = {
            "window_id": self.window_id,
            "severity": round(self.severity, 4),
            "coherence_score": round(self.coherence_score, 4),
            "coherence_delta": round(self.coherence_delta, 4),
            "contributing_factors": self.contributing_factors,
        }
        if self.metrics:
            d["metrics"] = self.metrics.to_dict()
        return d


@dataclass
class SensemakingReport:
    """Full sensemaking analysis across time windows."""
    windows: list[WindowMetrics] = field(default_factory=list)
    coherence_series: list[float] = field(default_factory=list)
    divergence_series: list[float] = field(default_factory=list)
    collapse_signals: list[CollapseSignal] = field(default_factory=list)
    overall_trend: str = "stable"  # stable, degrading, collapsed, recovering

    def to_dict(self) -> dict:
        return {
            "window_count": len(self.windows),
            "windows": [w.to_dict() for w in self.windows],
            "coherence_series": [round(c, 4) for c in self.coherence_series],
            "divergence_series": [round(d, 4) for d in self.divergence_series],
            "collapse_signals": [s.to_dict() for s in self.collapse_signals],
            "overall_trend": self.overall_trend,
        }


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    words = re.findall(r"[a-z0-9']+", text.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def _count_lexicon_hits(text: str, lexicon: frozenset[str]) -> int:
    """Count occurrences of lexicon phrases in text."""
    text_lower = text.lower()
    count = 0
    for phrase in lexicon:
        if " " in phrase:
            count += text_lower.count(phrase)
        else:
            # Word boundary match for single words
            count += len(re.findall(r'\b' + re.escape(phrase) + r'\b', text_lower))
    return count


def _shannon_entropy(distribution: dict[str, int]) -> float:
    """Compute Shannon entropy H = -sum(p * log2(p)) over a count distribution."""
    total = sum(distribution.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in distribution.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def _jensen_shannon_divergence(
    dist_a: dict[str, int], dist_b: dict[str, int],
) -> float:
    """
    Compute Jensen-Shannon divergence between two count distributions.

    JSD(P||Q) = 0.5 * KLD(P||M) + 0.5 * KLD(Q||M), where M = 0.5*(P+Q).
    Symmetric, bounded [0, 1] when using log2.
    """
    all_keys = set(dist_a.keys()) | set(dist_b.keys())
    if not all_keys:
        return 0.0

    total_a = sum(dist_a.values()) or 1
    total_b = sum(dist_b.values()) or 1

    jsd = 0.0
    for key in all_keys:
        p = dist_a.get(key, 0) / total_a
        q = dist_b.get(key, 0) / total_b
        m = 0.5 * (p + q)
        if m > 0:
            if p > 0:
                jsd += 0.5 * p * math.log2(p / m)
            if q > 0:
                jsd += 0.5 * q * math.log2(q / m)

    return min(max(jsd, 0.0), 1.0)  # Clamp for numerical stability


def compute_window_metrics(
    posts: Sequence[str],
    window_id: str = "w0",
) -> WindowMetrics:
    """
    Compute all sensemaking metrics for a single time window of posts.

    Args:
        posts: List of text content (one string per post/message).
        window_id: Identifier for this window.

    Returns:
        WindowMetrics with all computed values.
    """
    metrics = WindowMetrics(window_id=window_id, post_count=len(posts))

    if not posts:
        return metrics

    # Concatenate and tokenize
    all_text = " ".join(posts)
    tokens = _tokenize(all_text)
    metrics.word_count = len(tokens)

    if metrics.word_count == 0:
        return metrics

    # Topic distribution (term frequency of content words)
    topic_counts: Counter[str] = Counter(tokens)
    metrics.topic_count = len(topic_counts)
    metrics.top_topics = topic_counts.most_common(20)

    # Narrative entropy
    metrics.narrative_entropy = _shannon_entropy(dict(topic_counts))

    # Sentiment (per-post)
    if _vader:
        scores = []
        for post in posts:
            if post.strip():
                score = _vader.polarity_scores(post)["compound"]
                scores.append(score)
        if scores:
            metrics.sentiment_scores = scores
            metrics.sentiment_mean = sum(scores) / len(scores)
            if len(scores) > 1:
                mean = metrics.sentiment_mean
                metrics.sentiment_variance = sum(
                    (s - mean) ** 2 for s in scores
                ) / (len(scores) - 1)

    # Language markers
    wc = metrics.word_count
    metrics.causation_rate = _count_lexicon_hits(all_text, CAUSATION_WORDS) / wc
    metrics.tentative_rate = _count_lexicon_hits(all_text, TENTATIVE_WORDS) / wc
    metrics.certainty_rate = _count_lexicon_hits(all_text, CERTAINTY_WORDS) / wc

    # Framework-seeking index: (causation + tentative) / (certainty + epsilon)
    # High FSI = community seeking explanations. Low FSI = community has answers.
    eps = 1e-6
    metrics.framework_seeking_index = (
        (metrics.causation_rate + metrics.tentative_rate)
        / (metrics.certainty_rate + eps)
    )

    # Authority trust index
    trust_hits = _count_lexicon_hits(all_text, AUTHORITY_TRUST_WORDS)
    distrust_hits = _count_lexicon_hits(all_text, AUTHORITY_DISTRUST_WORDS)
    metrics.authority_trust_rate = trust_hits / wc
    metrics.authority_distrust_rate = distrust_hits / wc
    metrics.authority_trust_index = (
        trust_hits / (trust_hits + distrust_hits + eps)
    )

    return metrics


def compute_coherence_score(
    metrics: WindowMetrics,
    prev_metrics: WindowMetrics | None = None,
    max_entropy: float | None = None,
) -> float:
    """
    Compute composite coherence score (0-1) for a window.

    Components (weighted):
    - Entropy normalization (30%): lower entropy = higher coherence
    - Sentiment dispersion (25%): lower variance = higher coherence
    - Framework-seeking (20%): lower FSI = higher coherence (community has answers)
    - Authority trust (15%): higher trust index = higher coherence
    - Temporal divergence (10%): lower JSD from previous window = higher coherence

    Returns float in [0, 1] where 1 = perfectly coherent, 0 = total collapse.
    """
    # Normalize entropy to [0, 1]. Max theoretical entropy = log2(vocab_size)
    if max_entropy is None:
        max_entropy = math.log2(max(metrics.topic_count, 2))
    entropy_norm = 1.0 - min(metrics.narrative_entropy / (max_entropy + 1e-6), 1.0)

    # Sentiment dispersion: variance in [0, ~4] for VADER compound [-1, 1]
    # Normalize: 0 variance = 1.0, variance of 1.0 = 0.0
    sentiment_norm = max(1.0 - metrics.sentiment_variance, 0.0)

    # FSI: typical range [0, ~10]. Normalize with sigmoid-like function.
    # FSI < 1 = coherent (community has answers), FSI > 3 = seeking
    fsi_norm = 1.0 / (1.0 + metrics.framework_seeking_index)

    # Authority trust index already in [0, 1]
    ati_norm = metrics.authority_trust_index

    # Temporal divergence (if previous window available)
    jsd_norm = 1.0
    if prev_metrics and prev_metrics.top_topics:
        dist_a = dict(prev_metrics.top_topics)
        dist_b = dict(metrics.top_topics)
        jsd = _jensen_shannon_divergence(dist_a, dist_b)
        jsd_norm = 1.0 - jsd

    # Weighted composite
    coherence = (
        0.30 * entropy_norm
        + 0.25 * sentiment_norm
        + 0.20 * fsi_norm
        + 0.15 * ati_norm
        + 0.10 * jsd_norm
    )

    return max(min(coherence, 1.0), 0.0)


def detect_collapse(
    windows: list[list[str]],
    window_ids: list[str] | None = None,
    collapse_threshold: float = 0.15,
    severity_threshold: float = 0.3,
) -> SensemakingReport:
    """
    Detect sensemaking collapse across time-ordered windows of community posts.

    Args:
        windows: List of post lists, one per time window. Ordered chronologically.
        window_ids: Optional labels for each window (default: w0, w1, ...).
        collapse_threshold: Minimum coherence drop between windows to flag as
            collapse signal. Default 0.15 (15% drop).
        severity_threshold: Minimum absolute severity to include in signals.

    Returns:
        SensemakingReport with per-window metrics, coherence series,
        divergence series, and collapse signals.
    """
    if not windows:
        return SensemakingReport()

    if window_ids is None:
        window_ids = [f"w{i}" for i in range(len(windows))]

    report = SensemakingReport()

    # Compute per-window metrics
    all_metrics = []
    for i, (posts, wid) in enumerate(zip(windows, window_ids)):
        m = compute_window_metrics(posts, window_id=wid)
        all_metrics.append(m)
        report.windows.append(m)

    # Compute max entropy across all windows for consistent normalization
    max_entropy = max(
        (math.log2(max(m.topic_count, 2)) for m in all_metrics),
        default=1.0,
    )

    # Coherence series
    prev = None
    for m in all_metrics:
        c = compute_coherence_score(m, prev_metrics=prev, max_entropy=max_entropy)
        report.coherence_series.append(c)
        prev = m

    # Divergence series (JSD between consecutive windows)
    for i in range(1, len(all_metrics)):
        dist_a = dict(all_metrics[i - 1].top_topics)
        dist_b = dict(all_metrics[i].top_topics)
        jsd = _jensen_shannon_divergence(dist_a, dist_b)
        report.divergence_series.append(jsd)

    # Detect collapse signals
    for i in range(1, len(report.coherence_series)):
        delta = report.coherence_series[i] - report.coherence_series[i - 1]
        if delta < -collapse_threshold:
            m = all_metrics[i]
            severity = min(abs(delta) / 0.5, 1.0)  # Normalize to [0, 1]

            if severity < severity_threshold:
                continue

            # Identify contributing factors
            factors = []
            prev_m = all_metrics[i - 1]

            # Entropy spike
            if m.narrative_entropy > prev_m.narrative_entropy * 1.3:
                factors.append(
                    f"narrative fragmentation: entropy increased "
                    f"{prev_m.narrative_entropy:.2f} -> {m.narrative_entropy:.2f}"
                )

            # Sentiment dispersion spike
            if m.sentiment_variance > prev_m.sentiment_variance * 1.5:
                factors.append(
                    f"affective polarization: sentiment variance increased "
                    f"{prev_m.sentiment_variance:.3f} -> {m.sentiment_variance:.3f}"
                )

            # Framework-seeking spike
            if m.framework_seeking_index > prev_m.framework_seeking_index * 1.5:
                factors.append(
                    f"explanation-seeking surge: FSI increased "
                    f"{prev_m.framework_seeking_index:.2f} -> {m.framework_seeking_index:.2f}"
                )

            # Authority trust drop
            if m.authority_trust_index < prev_m.authority_trust_index * 0.7:
                factors.append(
                    f"authority trust erosion: ATI dropped "
                    f"{prev_m.authority_trust_index:.2f} -> {m.authority_trust_index:.2f}"
                )

            # JSD spike
            if i - 1 < len(report.divergence_series):
                jsd = report.divergence_series[i - 1]
                if jsd > 0.3:
                    factors.append(
                        f"narrative shift: JSD={jsd:.3f} between windows"
                    )

            if not factors:
                factors.append("composite coherence drop without single dominant factor")

            report.collapse_signals.append(CollapseSignal(
                window_id=window_ids[i],
                severity=severity,
                coherence_score=report.coherence_series[i],
                coherence_delta=delta,
                contributing_factors=factors,
                metrics=m,
            ))

    # Overall trend
    if len(report.coherence_series) >= 3:
        recent = report.coherence_series[-3:]
        if report.collapse_signals and report.collapse_signals[-1].window_id == window_ids[-1]:
            report.overall_trend = "collapsed"
        elif all(recent[j] < recent[j - 1] for j in range(1, len(recent))):
            report.overall_trend = "degrading"
        elif all(recent[j] > recent[j - 1] for j in range(1, len(recent))):
            report.overall_trend = "recovering"
        else:
            report.overall_trend = "stable"

    return report
