"""
Pure NLP analysis of Discord data — no LLM calls.
Uses spaCy, NLTK, scikit-learn, networkx, gensim when available; fallbacks for core metrics.
"""

import re
from collections import Counter
from typing import Any

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except ImportError:
    SentimentIntensityAnalyzer = None

try:
    import networkx as nx
except ImportError:
    nx = None

# Optional: spaCy for linguistic analysis (lazy load to avoid import-time failure)
_nlp_spacy = None


def _get_spacy():
    global _nlp_spacy
    if _nlp_spacy is not None:
        return _nlp_spacy
    try:
        import spacy

        _nlp_spacy = spacy.load("en_core_web_sm")
    except Exception:
        pass
    return _nlp_spacy


# Optional: NLTK for lexical (ensure punkt/punkt_tab so sent_tokenize works)
def _safe_sent_tokenize(text: str) -> list[str]:
    try:
        from nltk.tokenize import sent_tokenize as _st
        return _st(text)
    except Exception:
        return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


try:
    import nltk
    from nltk.tokenize import word_tokenize
    for res in ("punkt_tab", "punkt"):
        try:
            nltk.download(res, quiet=True)
            break
        except Exception:
            pass
    sent_tokenize = _safe_sent_tokenize
except ImportError:
    word_tokenize = None
    sent_tokenize = lambda t: [s.strip() for s in re.split(r"[.!?]+", t) if s.strip()]

# Optional: sklearn for clustering / patterns
try:
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:
    TfidfVectorizer = None
    NMF = None

# Optional: gensim for topic modeling
try:
    from gensim import corpora
    from gensim.models import LdaModel
except ImportError:
    corpora = None
    LdaModel = None


def _tokenize_simple(text: str) -> list[str]:
    return re.findall(r"\b[a-z0-9']+\b", text.lower())


def _sent_tokenize_simple(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def _content_words() -> set[str]:
    """Simple content-word heuristic (no NLTK)."""
    stop = {
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "it",
        "they",
        "them",
        "the",
        "a",
        "an",
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
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "this",
        "that",
        "and",
        "but",
        "or",
        "if",
        "then",
        "so",
        "just",
        "not",
        "no",
        "yes",
    }
    return stop


class DiscordNLPAnalyzer:
    """
    Pure NLP analysis of Discord data — no LLM calls.
    Returns structured metrics for use by LLM synthesis layer.
    """

    def analyze_messages(self, messages: list[dict]) -> dict[str, Any]:
        """Extract linguistic patterns from messages."""
        contents = []
        for m in messages:
            if isinstance(m, dict):
                c = m.get("content") or m.get("body") or ""
                if isinstance(c, str) and c.strip():
                    contents.append(c.strip())
            elif isinstance(m, str) and m.strip():
                contents.append(m.strip())

        if not contents:
            return self._empty_message_analysis()

        all_text = " ".join(contents)
        tokens = _tokenize_simple(all_text)
        try:
            sentences = sent_tokenize(all_text) if sent_tokenize else _sent_tokenize_simple(all_text)
        except LookupError:
            sentences = _sent_tokenize_simple(all_text)
        if not sentences:
            sentences = [all_text] if all_text else []

        # Lexical
        type_token = len(set(tokens)) / len(tokens) if tokens else 0.0
        avg_word_len = sum(len(w) for w in tokens) / len(tokens) if tokens else 0.0
        avg_sent_len = (
            sum(len(_tokenize_simple(s)) for s in sentences) / len(sentences) if sentences else 0.0
        )
        stop = _content_words()
        content_count = sum(1 for w in tokens if w not in stop)
        lexical_density = content_count / len(tokens) if tokens else 0.0

        # Sentiment (VADER)
        sentiment_dist = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
        compounds = []
        if SentimentIntensityAnalyzer:
            vader = SentimentIntensityAnalyzer()
            for c in contents[:500]:
                d = vader.polarity_scores(c)
                sentiment_dist["positive"] += d.get("pos", 0)
                sentiment_dist["negative"] += d.get("neg", 0)
                sentiment_dist["neutral"] += d.get("neu", 0)
                compounds.append(d.get("compound", 0))
            n = len(contents[:500]) or 1
            sentiment_dist["positive"] /= n
            sentiment_dist["negative"] /= n
            sentiment_dist["neutral"] /= n
        emotional_range = float(max(compounds) - min(compounds)) if compounds else 0.0

        # Discourse markers (regex)
        hedging = sum(
            1
            for c in contents
            if re.search(r"\b(maybe|kinda|sort of|perhaps|probably|imo|tbh|idk)\b", c.lower())
        )
        certainty = sum(
            1
            for c in contents
            if re.search(r"\b(definitely|obviously|clearly|actually|literally)\b", c.lower())
        )
        questions = sum(1 for c in contents if "?" in c)
        exclamations = sum(1 for c in contents if "!" in c)
        n = len(contents) or 1
        hedging_frequency = hedging / n
        certainty_markers = certainty / n
        question_frequency = questions / n
        exclamation_frequency = exclamations / n

        # POS distribution (spaCy if available)
        pos_distribution: dict[str, float] = {}
        spacy_nlp = _get_spacy()
        if spacy_nlp and contents:
            pos_counts: Counter = Counter()
            for doc in spacy_nlp.pipe(contents[:200], batch_size=50):
                for t in doc:
                    if t.pos_:
                        pos_counts[t.pos_] += 1
            total = sum(pos_counts.values()) or 1
            pos_distribution = {k: v / total for k, v in pos_counts.most_common(15)}

        # Phrase patterns: common bigrams
        bigrams = []
        for c in contents:
            t = _tokenize_simple(c)
            for i in range(len(t) - 1):
                if t[i] not in _content_words() or t[i + 1] not in _content_words():
                    bigrams.append((t[i], t[i + 1]))
        phrase_patterns = [f"{a} {b}" for (a, b), _ in Counter(bigrams).most_common(20)]

        return {
            "vocabulary_richness": type_token,
            "avg_word_length": avg_word_len,
            "avg_sentence_length": avg_sent_len,
            "lexical_density": lexical_density,
            "sentence_structures": {},  # placeholder; could add simple/compound from spacy
            "pos_distribution": pos_distribution,
            "phrase_patterns": phrase_patterns,
            "sentiment_distribution": sentiment_dist,
            "emotional_range": emotional_range,
            "emotion_triggers": [],  # LLM can infer from topics + sentiment
            "hedging_frequency": hedging_frequency,
            "certainty_markers": certainty_markers,
            "question_frequency": question_frequency,
            "exclamation_frequency": exclamation_frequency,
            "message_velocity": {"total_messages": len(contents)},
            "burst_patterns": [],
            "response_latency": 0.0,
        }

    def _empty_message_analysis(self) -> dict[str, Any]:
        return {
            "vocabulary_richness": 0.0,
            "avg_word_length": 0.0,
            "avg_sentence_length": 0.0,
            "lexical_density": 0.0,
            "sentence_structures": {},
            "pos_distribution": {},
            "phrase_patterns": [],
            "sentiment_distribution": {"positive": 0.0, "negative": 0.0, "neutral": 0.0},
            "emotional_range": 0.0,
            "emotion_triggers": [],
            "hedging_frequency": 0.0,
            "certainty_markers": 0.0,
            "question_frequency": 0.0,
            "exclamation_frequency": 0.0,
            "message_velocity": {},
            "burst_patterns": [],
            "response_latency": 0.0,
        }

    def analyze_reactions(self, reactions: list[dict]) -> dict[str, Any]:
        """Pattern analysis of reaction behavior."""
        if not reactions:
            return {
                "reaction_diversity": 0.0,
                "top_reaction_contexts": [],
                "emotional_reaction_map": {},
                "reaction_triggers": [],
                "reciprocity_score": 0.0,
            }

        emoji_counts: Counter = Counter()
        contexts: list[str] = []
        for r in reactions:
            if isinstance(r, dict):
                emoji = r.get("emoji") or r.get("reaction") or ""
                if emoji:
                    emoji_counts[str(emoji).strip()] += 1
                msg = (r.get("message_content") or "")[:200]
                if msg:
                    contexts.append(msg)

        total = sum(emoji_counts.values()) or 1
        probs = [c / total for c in emoji_counts.values()]
        try:
            import math

            reaction_diversity = -sum(p * math.log(p) for p in probs if p > 0) if probs else 0.0
        except Exception:
            reaction_diversity = float(len(emoji_counts)) / 10.0  # fallback

        # Reaction triggers: token frequency in messages they reacted to
        all_context_tokens = []
        for c in contexts:
            all_context_tokens.extend(_tokenize_simple(c))
        stop = _content_words()
        trigger_counts = Counter(w for w in all_context_tokens if w not in stop and len(w) > 2)
        reaction_triggers = [w for w, _ in trigger_counts.most_common(15)]

        return {
            "reaction_diversity": reaction_diversity,
            "top_reaction_contexts": [(e, "message") for e, _ in emoji_counts.most_common(10)],
            "emotional_reaction_map": dict(emoji_counts.most_common(10)),
            "reaction_triggers": reaction_triggers,
            "reciprocity_score": 0.0,  # would need "reactions received" data
        }

    def analyze_servers(self, servers: list[dict], messages: list[dict]) -> dict[str, Any]:
        """Community affiliation analysis."""
        server_names: list[str] = []
        for s in servers or []:
            if isinstance(s, dict) and s.get("server_name"):
                server_names.append(str(s["server_name"]).strip())
            elif isinstance(s, str):
                server_names.append(s.strip())

        # Engagement per server (from messages)
        server_engagement: Counter = Counter()
        for m in messages or []:
            if isinstance(m, dict):
                name = m.get("server_name") or m.get("server_id") or ""
                if name:
                    server_engagement[str(name)] += 1
        engagement_dist = dict(server_engagement)
        primary = [s for s, _ in server_engagement.most_common(3)]

        # Tribal markers: distinctive words per server (simplified)
        topic_by_server: dict[str, list[str]] = {}
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            name = m.get("server_name") or m.get("server_id") or "default"
            name = str(name)
            c = m.get("content") or m.get("body") or ""
            if name not in topic_by_server:
                topic_by_server[name] = []
            topic_by_server[name].extend(_tokenize_simple(c)[:50])
        for k in topic_by_server:
            stop = _content_words()
            counts = Counter(w for w in topic_by_server[k] if w not in stop and len(w) > 2)
            topic_by_server[k] = [w for w, _ in counts.most_common(10)]

        return {
            "server_engagement_distribution": engagement_dist,
            "primary_communities": primary or server_names[:3],
            "community_overlap": 0.5,  # placeholder
            "tribal_markers": list(dict.fromkeys(server_names))[:15],
            "topic_by_server": topic_by_server,
        }

    def analyze_network(self, interactions: list[dict]) -> dict[str, Any]:
        """Graph analysis of interaction patterns."""
        if not nx or not interactions:
            return {
                "centrality_score": 0.0,
                "community_role": "participant",
                "interaction_reciprocity": 0.0,
                "influence_score": 0.0,
                "cluster_membership": [],
            }

        G = nx.Graph()
        for i in interactions:
            if not isinstance(i, dict):
                continue
            uid = i.get("user_id") or i.get("username") or ""
            count = int(i.get("interaction_count", 0))
            if uid:
                G.add_node(uid, weight=count)
        # Edges: connect nodes that appear in same list (simplified; real would use reply chains)
        nodes = list(G.nodes())
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 : i + 3]:  # loose coupling
                if G.degree(a) + G.degree(b) < 10:
                    G.add_edge(a, b, weight=1)

        centrality_score = 0.0
        if G.number_of_nodes() > 0:
            try:
                cent = nx.degree_centrality(G)
                centrality_score = sum(cent.values()) / len(cent) if cent else 0.0
            except Exception:
                pass

        # Role from degree
        if G.number_of_nodes() == 0:
            community_role = "participant"
        elif centrality_score > 0.6:
            community_role = "hub"
        elif centrality_score < 0.2:
            community_role = "peripheral"
        else:
            community_role = "bridge"

        return {
            "centrality_score": centrality_score,
            "community_role": community_role,
            "interaction_reciprocity": 0.0,
            "influence_score": centrality_score,
            "cluster_membership": list(G.nodes())[:5],
        }

    def extract_topics(self, messages: list[dict]) -> dict[str, Any]:
        """Topic extraction without LLM (NMF or LDA when available)."""
        contents = []
        for m in messages:
            if isinstance(m, dict):
                c = m.get("content") or m.get("body") or ""
                if isinstance(c, str) and c.strip():
                    contents.append(c.strip())
            elif isinstance(m, str) and m.strip():
                contents.append(m.strip())

        primary_topics: list[tuple[str, float]] = []
        topic_evolution: list[dict] = []
        obsession_indicators: list[str] = []
        curiosity_topics: list[str] = []

        if not contents:
            return {
                "primary_topics": [],
                "topic_evolution": [],
                "obsession_indicators": [],
                "curiosity_topics": [],
            }

        # Fallback: word frequency as "topics"
        all_tokens = []
        for c in contents:
            all_tokens.extend(_tokenize_simple(c))
        stop = _content_words()
        counts = Counter(w for w in all_tokens if w not in stop and len(w) > 2)
        primary_topics = [(w, c / len(all_tokens)) for w, c in counts.most_common(15)]

        # Questions -> curiosity
        for c in contents:
            if "?" in c:
                curiosity_topics.extend(_tokenize_simple(c))
        curiosity_counts = Counter(w for w in curiosity_topics if w not in stop and len(w) > 2)
        curiosity_topics = [w for w, _ in curiosity_counts.most_common(8)]

        # NMF if sklearn available
        if TfidfVectorizer and NMF and len(contents) >= 5:
            try:
                vec = TfidfVectorizer(max_features=100, stop_words="english", ngram_range=(1, 2))
                X = vec.fit_transform(contents)
                nmf = NMF(n_components=min(5, len(contents) - 1), random_state=42)
                W = nmf.fit_transform(X)
                terms = vec.get_feature_names_out()
                for i in range(W.shape[1]):
                    top_idx = W[:, i].argsort()[-3:][::-1]
                    top_words = [terms[j] for j in top_idx if j < len(terms)]
                    if top_words:
                        primary_topics.append((top_words[0], float(W[:, i].max())))
            except Exception:
                pass

        return {
            "primary_topics": primary_topics[:15],
            "topic_evolution": topic_evolution,
            "obsession_indicators": [t[0] for t in primary_topics[:5]],
            "curiosity_topics": curiosity_topics,
        }
