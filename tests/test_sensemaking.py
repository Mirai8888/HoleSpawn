"""Tests for sensemaking collapse detector."""

import math

import pytest

from holespawn.network.sensemaking import (
    CollapseSignal,
    SensemakingReport,
    WindowMetrics,
    _jensen_shannon_divergence,
    _shannon_entropy,
    _count_lexicon_hits,
    _tokenize,
    compute_coherence_score,
    compute_window_metrics,
    detect_collapse,
    CAUSATION_WORDS,
    TENTATIVE_WORDS,
    CERTAINTY_WORDS,
    AUTHORITY_TRUST_WORDS,
    AUTHORITY_DISTRUST_WORDS,
)


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("The quick brown fox jumps over the lazy dog")
        assert "quick" in tokens
        assert "brown" in tokens
        assert "the" not in tokens  # stopword

    def test_empty(self):
        assert _tokenize("") == []

    def test_removes_short(self):
        tokens = _tokenize("I am a go to it")
        assert all(len(t) > 2 for t in tokens)


class TestShannonEntropy:
    def test_uniform(self):
        # 4 equally frequent items -> H = log2(4) = 2.0
        dist = {"a": 10, "b": 10, "c": 10, "d": 10}
        assert abs(_shannon_entropy(dist) - 2.0) < 0.01

    def test_single(self):
        # One item -> H = 0
        assert _shannon_entropy({"a": 100}) == 0.0

    def test_empty(self):
        assert _shannon_entropy({}) == 0.0

    def test_skewed(self):
        # Skewed distribution -> lower entropy
        dist = {"a": 90, "b": 5, "c": 3, "d": 2}
        h = _shannon_entropy(dist)
        assert 0 < h < 2.0


class TestJensenShannonDivergence:
    def test_identical(self):
        dist = {"a": 10, "b": 20}
        assert _jensen_shannon_divergence(dist, dist) < 0.001

    def test_disjoint(self):
        # Completely different distributions -> JSD = 1.0
        a = {"x": 10}
        b = {"y": 10}
        assert abs(_jensen_shannon_divergence(a, b) - 1.0) < 0.01

    def test_partial_overlap(self):
        a = {"x": 10, "y": 5}
        b = {"y": 5, "z": 10}
        jsd = _jensen_shannon_divergence(a, b)
        assert 0 < jsd < 1.0

    def test_symmetry(self):
        a = {"x": 10, "y": 5}
        b = {"y": 8, "z": 3}
        assert abs(
            _jensen_shannon_divergence(a, b) - _jensen_shannon_divergence(b, a)
        ) < 0.0001

    def test_empty(self):
        assert _jensen_shannon_divergence({}, {}) == 0.0


class TestLexiconHits:
    def test_single_word(self):
        assert _count_lexicon_hits("I am confused about this", CAUSATION_WORDS) >= 1

    def test_multi_word_phrase(self):
        assert _count_lexicon_hits(
            "This doesn't make sense to me", CAUSATION_WORDS
        ) >= 1

    def test_authority_trust(self):
        text = "According to experts and research shows this is true"
        assert _count_lexicon_hits(text, AUTHORITY_TRUST_WORDS) >= 2

    def test_authority_distrust(self):
        text = "This is propaganda and a cover up by corrupt officials"
        assert _count_lexicon_hits(text, AUTHORITY_DISTRUST_WORDS) >= 2

    def test_no_hits(self):
        assert _count_lexicon_hits("The cat sat on the mat", CAUSATION_WORDS) == 0


class TestWindowMetrics:
    def test_basic(self):
        posts = [
            "The government announced new policy changes today",
            "Scientists report breakthrough in climate research",
            "Market responds positively to economic data",
        ]
        m = compute_window_metrics(posts, window_id="test")
        assert m.post_count == 3
        assert m.word_count > 0
        assert m.narrative_entropy > 0
        assert m.topic_count > 0
        assert len(m.top_topics) > 0

    def test_empty(self):
        m = compute_window_metrics([], window_id="empty")
        assert m.post_count == 0
        assert m.narrative_entropy == 0.0

    def test_high_causation(self):
        posts = [
            "Why is this happening? Because the system is broken",
            "I don't understand why things changed so suddenly",
            "Can someone explain what caused this? What does this mean?",
        ]
        m = compute_window_metrics(posts, window_id="crisis")
        assert m.causation_rate > 0
        assert m.framework_seeking_index > 0

    def test_authority_distrust(self):
        posts = [
            "The government is lying to us, this is propaganda",
            "Don't trust mainstream media, they are corrupt shills",
            "Wake up sheeple, it's all a cover up and a hoax",
        ]
        m = compute_window_metrics(posts, window_id="distrust")
        assert m.authority_distrust_rate > m.authority_trust_rate
        assert m.authority_trust_index < 0.5

    def test_coherent_community(self):
        posts = [
            "Research confirms the new treatment is effective",
            "Experts agree this approach shows promising results",
            "According to verified studies, the evidence is clear",
        ]
        m = compute_window_metrics(posts, window_id="coherent")
        assert m.authority_trust_index > 0.5

    def test_to_dict(self):
        m = compute_window_metrics(["test post"], window_id="dict_test")
        d = m.to_dict()
        assert "window_id" in d
        assert "narrative_entropy" in d


class TestCoherenceScore:
    def test_range(self):
        m = compute_window_metrics(["Some text here"], window_id="t")
        c = compute_coherence_score(m)
        assert 0.0 <= c <= 1.0

    def test_high_coherence(self):
        posts = [
            "The evidence clearly shows this is true according to experts",
            "Research definitely confirms the established facts",
            "Scientists have proven this beyond any doubt",
        ]
        m = compute_window_metrics(posts)
        c = compute_coherence_score(m)
        assert c > 0.4  # Should be moderately high

    def test_low_coherence(self):
        posts = [
            "Why is this happening? I'm so confused and uncertain",
            "Maybe it's a cover up? I don't trust anyone anymore",
            "This doesn't make sense, perhaps they're lying to us",
            "Who knows what's really going on, it's all fake news",
            "I guess nobody can explain why everything is falling apart",
        ]
        m = compute_window_metrics(posts)
        c = compute_coherence_score(m)
        # Should be lower than coherent community
        assert c < 0.7


class TestDetectCollapse:
    def test_stable_community(self):
        # Same type of content across windows
        window = [
            "The research continues to show positive results",
            "Studies confirm the effectiveness of the approach",
            "Evidence supports the established methodology",
        ]
        windows = [window] * 5
        report = detect_collapse(windows)
        assert report.overall_trend == "stable"
        assert len(report.collapse_signals) == 0

    def test_collapse_detection(self):
        # Window 1-3: coherent
        coherent = [
            "Research clearly confirms these findings according to experts",
            "The evidence definitely supports the established facts",
            "Scientists have proven this methodology works reliably",
        ] * 3

        # Window 4-5: collapse
        collapsed = [
            "Why is everything falling apart? Nothing makes sense anymore",
            "Maybe it's all propaganda, I don't trust the so-called experts",
            "Can someone explain what happened? This is confusing and unclear",
            "Wake up, it's a cover up! The authorities are corrupt liars",
            "I'm not sure what to believe, perhaps everything was a hoax",
            "Who knows what's really going on, the whole system is broken",
        ]

        windows = [coherent, coherent, coherent, collapsed, collapsed]
        report = detect_collapse(windows, collapse_threshold=0.05)
        assert len(report.windows) == 5
        assert len(report.coherence_series) == 5
        # Coherence should drop in later windows
        assert report.coherence_series[-1] < report.coherence_series[0]

    def test_report_structure(self):
        windows = [["post one"], ["post two"], ["post three"]]
        report = detect_collapse(windows)
        assert isinstance(report, SensemakingReport)
        assert len(report.windows) == 3
        assert len(report.coherence_series) == 3
        assert len(report.divergence_series) == 2  # n-1 divergences

    def test_report_to_dict(self):
        windows = [["post one"], ["post two"]]
        report = detect_collapse(windows)
        d = report.to_dict()
        assert "coherence_series" in d
        assert "collapse_signals" in d
        assert "overall_trend" in d

    def test_empty(self):
        report = detect_collapse([])
        assert len(report.windows) == 0

    def test_single_window(self):
        report = detect_collapse([["some text here"]])
        assert len(report.windows) == 1
        assert len(report.coherence_series) == 1
        assert len(report.collapse_signals) == 0

    def test_custom_window_ids(self):
        windows = [["a"], ["b"], ["c"]]
        ids = ["2026-02-17", "2026-02-18", "2026-02-19"]
        report = detect_collapse(windows, window_ids=ids)
        assert report.windows[0].window_id == "2026-02-17"

    def test_collapse_signal_has_factors(self):
        coherent = ["The facts are clear and experts agree"] * 5
        collapsed = [
            "Why why why? Nothing makes sense, it's all lies and propaganda",
            "Maybe it's a hoax? Perhaps the corrupt authorities are covering up",
        ] * 5
        windows = [coherent, coherent, collapsed]
        report = detect_collapse(windows, collapse_threshold=0.01, severity_threshold=0.01)
        if report.collapse_signals:
            signal = report.collapse_signals[0]
            assert len(signal.contributing_factors) > 0
            assert signal.severity > 0
