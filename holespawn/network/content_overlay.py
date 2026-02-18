"""
Content-aware network analysis: map topics/narratives onto graph nodes,
belief clustering, narrative divergence, and sentiment flow.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

try:
    from networkx.algorithms.community import greedy_modularity_communities
except ImportError:
    from networkx.algorithms.community.modularity_max import greedy_modularity_communities

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
except ImportError:
    _vader = None

# Basic stopwords for topic extraction (extend as needed)
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "don", "now", "and", "but", "or",
    "if", "it", "its", "he", "she", "they", "them", "his", "her", "their",
    "this", "that", "these", "those", "i", "me", "my", "we", "our", "you",
    "your", "up", "about", "which", "who", "whom", "what", "rt", "amp",
    "get", "got", "like", "one", "also", "us", "im", "dont", "cant",
}


@dataclass
class NodeTopicProfile:
    """Topics and sentiment profile for a single node."""
    user: str
    top_topics: list[tuple[str, int]] = field(default_factory=list)
    hashtags: list[tuple[str, int]] = field(default_factory=list)
    avg_sentiment: float = 0.0
    tweet_count: int = 0

    def to_dict(self) -> dict:
        return {
            "user": self.user,
            "top_topics": self.top_topics,
            "hashtags": self.hashtags,
            "avg_sentiment": round(self.avg_sentiment, 4),
            "tweet_count": self.tweet_count,
        }


@dataclass
class BeliefCluster:
    """Group of nodes clustered by content similarity rather than structure."""
    cluster_id: int
    members: list[str] = field(default_factory=list)
    shared_topics: list[str] = field(default_factory=list)
    avg_sentiment: float = 0.0

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "members": self.members,
            "shared_topics": self.shared_topics,
            "avg_sentiment": round(self.avg_sentiment, 4),
        }


@dataclass
class NarrativeDivergence:
    """Where two communities disagree on topics."""
    community_a: int
    community_b: int
    divergent_topics: list[dict[str, Any]] = field(default_factory=list)
    sentiment_gap: float = 0.0

    def to_dict(self) -> dict:
        return {
            "community_a": self.community_a,
            "community_b": self.community_b,
            "divergent_topics": self.divergent_topics,
            "sentiment_gap": round(self.sentiment_gap, 4),
        }


@dataclass
class ContentOverlayReport:
    """Full content-aware analysis result."""
    node_profiles: list[NodeTopicProfile] = field(default_factory=list)
    belief_clusters: list[BeliefCluster] = field(default_factory=list)
    divergences: list[NarrativeDivergence] = field(default_factory=list)
    sentiment_flow: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_profiles": [p.to_dict() for p in self.node_profiles],
            "belief_clusters": [c.to_dict() for c in self.belief_clusters],
            "divergences": [d.to_dict() for d in self.divergences],
            "sentiment_flow": self.sentiment_flow,
        }


def _extract_topics(text: str, top_n: int = 20) -> list[tuple[str, int]]:
    """Extract topic words from text, returning (word, count) pairs."""
    words = re.findall(r"[a-z]{3,}", text.lower())
    filtered = [w for w in words if w not in _STOPWORDS and not w.isdigit()]
    return Counter(filtered).most_common(top_n)


def _sentiment(text: str) -> float:
    """Get compound sentiment score. Returns 0.0 if VADER unavailable."""
    if _vader is None:
        return 0.0
    return _vader.polarity_scores(text)["compound"]


def build_node_topic_profiles(
    tweets: list[dict],
    nodes: set[str] | None = None,
) -> dict[str, NodeTopicProfile]:
    """
    Build topic and sentiment profiles for each node from their tweets.

    Args:
        tweets: List of tweet dicts from scraper parser.
        nodes: Optional set of nodes to include. If None, all authors.

    Returns:
        Dict mapping username to NodeTopicProfile.
    """
    user_texts: dict[str, list[str]] = defaultdict(list)
    user_hashtags: dict[str, list[str]] = defaultdict(list)

    for tw in tweets:
        author = (tw.get("author") or "").lower()
        if not author:
            continue
        if nodes and author not in nodes:
            continue
        text = tw.get("full_text") or tw.get("text") or ""
        user_texts[author].append(text)
        for h in (tw.get("hashtags") or []):
            user_hashtags[author].append(h.lower())

    profiles: dict[str, NodeTopicProfile] = {}
    for user, texts in user_texts.items():
        combined = " ".join(texts)
        topics = _extract_topics(combined)
        hashtags = Counter(user_hashtags[user]).most_common(10)
        sentiments = [_sentiment(t) for t in texts]
        avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0.0

        profiles[user] = NodeTopicProfile(
            user=user,
            top_topics=topics,
            hashtags=hashtags,
            avg_sentiment=avg_sent,
            tweet_count=len(texts),
        )

    return profiles


def cluster_by_beliefs(
    profiles: dict[str, NodeTopicProfile],
    min_shared_topics: int = 3,
) -> list[BeliefCluster]:
    """
    Group nodes by content similarity (shared topics) rather than structure.

    Uses a simple overlap-based approach: build a similarity graph where
    edges exist between users sharing >= min_shared_topics, then detect communities.
    """
    if len(profiles) < 2:
        return []

    # Build topic sets per user
    user_topics: dict[str, set[str]] = {}
    for user, prof in profiles.items():
        user_topics[user] = {t for t, _ in prof.top_topics[:15]}

    # Build similarity graph
    S = nx.Graph()
    users = list(user_topics.keys())
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            shared = user_topics[users[i]] & user_topics[users[j]]
            if len(shared) >= min_shared_topics:
                S.add_edge(users[i], users[j], weight=len(shared),
                          shared_topics=list(shared))

    if S.number_of_edges() == 0:
        return []

    # Add isolate nodes that have profiles
    for u in users:
        if u not in S:
            S.add_node(u)

    # Detect communities in similarity graph
    try:
        communities = list(greedy_modularity_communities(S))
    except Exception:
        communities = [set(S.nodes())]

    clusters = []
    for cid, members in enumerate(communities):
        if len(members) < 2:
            continue
        # Find topics shared across most members
        topic_counts: Counter = Counter()
        sentiments = []
        for m in members:
            if m in profiles:
                for t, _ in profiles[m].top_topics[:10]:
                    topic_counts[t] += 1
                sentiments.append(profiles[m].avg_sentiment)

        # Topics present in >50% of members
        threshold = len(members) * 0.5
        shared = [t for t, c in topic_counts.most_common(20) if c >= threshold]

        clusters.append(BeliefCluster(
            cluster_id=cid,
            members=sorted(members),
            shared_topics=shared[:10],
            avg_sentiment=sum(sentiments) / len(sentiments) if sentiments else 0.0,
        ))

    return clusters


def analyze_narrative_divergence(
    G: nx.DiGraph,
    profiles: dict[str, NodeTopicProfile],
) -> list[NarrativeDivergence]:
    """
    Find topics where structurally-detected communities disagree.

    Compares topic usage and sentiment between community pairs.
    """
    U = G.to_undirected()
    if U.number_of_nodes() < 3:
        return []

    try:
        communities = list(greedy_modularity_communities(U))
    except Exception:
        return []

    if len(communities) < 2:
        return []

    # Build topic distributions per community
    def _community_topics(members: set) -> tuple[Counter, float]:
        topic_counts: Counter = Counter()
        sentiments = []
        for m in members:
            if m in profiles:
                for t, c in profiles[m].top_topics[:10]:
                    topic_counts[t] += c
                sentiments.append(profiles[m].avg_sentiment)
        avg_s = sum(sentiments) / len(sentiments) if sentiments else 0.0
        return topic_counts, avg_s

    comm_data = []
    for cid, members in enumerate(communities):
        topics, sentiment = _community_topics(set(members))
        comm_data.append((cid, topics, sentiment))

    divergences = []
    for i in range(len(comm_data)):
        for j in range(i + 1, len(comm_data)):
            cid_a, topics_a, sent_a = comm_data[i]
            cid_b, topics_b, sent_b = comm_data[j]

            # Find topics with divergent usage
            all_topics = set(topics_a) | set(topics_b)
            divergent = []
            for t in all_topics:
                a_freq = topics_a.get(t, 0)
                b_freq = topics_b.get(t, 0)
                total = a_freq + b_freq
                if total < 3:
                    continue
                # Divergence = how unevenly distributed
                ratio = min(a_freq, b_freq) / max(a_freq, b_freq) if max(a_freq, b_freq) > 0 else 0
                if ratio < 0.3:  # One side uses it 3x+ more
                    divergent.append({
                        "topic": t,
                        f"community_{cid_a}_freq": a_freq,
                        f"community_{cid_b}_freq": b_freq,
                        "skew_ratio": round(ratio, 4),
                    })

            divergent.sort(key=lambda x: x["skew_ratio"])

            if divergent:
                divergences.append(NarrativeDivergence(
                    community_a=cid_a,
                    community_b=cid_b,
                    divergent_topics=divergent[:15],
                    sentiment_gap=abs(sent_a - sent_b),
                ))

    divergences.sort(key=lambda d: d.sentiment_gap, reverse=True)
    return divergences


def analyze_sentiment_flow(
    G: nx.DiGraph,
    profiles: dict[str, NodeTopicProfile],
) -> dict[str, Any]:
    """
    Analyze how sentiment propagates through the network.

    Measures correlation between connected nodes' sentiment and identifies
    sentiment clusters / emotional contagion patterns.
    """
    if not profiles or G.number_of_edges() == 0:
        return {"edges_analyzed": 0}

    # Edge sentiment correlations
    same_sign = 0
    diff_sign = 0
    sentiment_diffs = []

    for u, v in G.edges():
        if u in profiles and v in profiles:
            su = profiles[u].avg_sentiment
            sv = profiles[v].avg_sentiment
            if su * sv > 0:
                same_sign += 1
            elif su * sv < 0:
                diff_sign += 1
            sentiment_diffs.append(abs(su - sv))

    total = same_sign + diff_sign
    homophily = same_sign / total if total > 0 else 0

    # Identify emotional hubs (high degree + extreme sentiment)
    emotional_hubs = []
    for node in G.nodes():
        if node not in profiles:
            continue
        sent = profiles[node].avg_sentiment
        degree = G.degree(node)
        if abs(sent) > 0.3 and degree > 2:
            emotional_hubs.append({
                "node": node,
                "sentiment": round(sent, 4),
                "degree": degree,
                "valence": "positive" if sent > 0 else "negative",
            })

    emotional_hubs.sort(key=lambda x: abs(x["sentiment"]) * x["degree"], reverse=True)

    return {
        "edges_analyzed": total,
        "sentiment_homophily": round(homophily, 4),
        "avg_sentiment_diff": round(sum(sentiment_diffs) / len(sentiment_diffs), 4) if sentiment_diffs else 0,
        "emotional_hubs": emotional_hubs[:20],
    }


def analyze_content_overlay(
    G: nx.DiGraph,
    tweets: list[dict],
) -> ContentOverlayReport:
    """
    Run full content-aware analysis on a graph with associated tweet data.

    Args:
        G: NetworkX DiGraph (from graph_builder).
        tweets: List of tweet dicts from scraper parser.

    Returns:
        ContentOverlayReport with topic profiles, belief clusters,
        divergence analysis, and sentiment flow.
    """
    nodes = set(G.nodes())
    profiles = build_node_topic_profiles(tweets, nodes)
    clusters = cluster_by_beliefs(profiles)
    divergences = analyze_narrative_divergence(G, profiles)
    sentiment = analyze_sentiment_flow(G, profiles)

    return ContentOverlayReport(
        node_profiles=list(profiles.values()),
        belief_clusters=clusters,
        divergences=divergences,
        sentiment_flow=sentiment,
    )
