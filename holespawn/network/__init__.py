"""
Network analysis from file-based data or paid APIs (Apify).
- Graph profiling: fetch social graph -> Louvain communities -> profile key nodes -> vulnerability report + D3 viz.
- Profile-based: load behavioral_matrix.json (or --apify) -> community detection -> engagement brief.
"""

from .analyzer import NetworkAnalyzer, load_edges_file, load_profiles_from_dir
from .apify_network import fetch_profiles_via_apify
from .graph_analysis import (
    NetworkAnalysis,
    build_network_analysis,
    network_analysis_to_dict,
)
from .pipeline import run_network_graph_pipeline

__all__ = [
    "NetworkAnalyzer",
    "load_profiles_from_dir",
    "load_edges_file",
    "fetch_profiles_via_apify",
    "NetworkAnalysis",
    "build_network_analysis",
    "network_analysis_to_dict",
    "run_network_graph_pipeline",
]
