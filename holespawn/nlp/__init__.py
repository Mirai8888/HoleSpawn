"""NLP analysis layer: extraction and quantification (no LLM). Optional deps: spacy, nltk, scikit-learn, networkx, gensim."""

from .discord_analyzer import DiscordNLPAnalyzer

__all__ = ["DiscordNLPAnalyzer"]
