"""
Network analysis from file-based data or paid APIs (Apify).
Load profiles (behavioral_matrix.json) and optional edges; run community detection and structural centrality.
Data source: directory of exported profiles, or Apify (following list + tweets per user). Use only data you are authorized to use.
"""

from .analyzer import NetworkAnalyzer, load_profiles_from_dir, load_edges_file
from .apify_network import fetch_profiles_via_apify

__all__ = ["NetworkAnalyzer", "load_profiles_from_dir", "load_edges_file", "fetch_profiles_via_apify"]
