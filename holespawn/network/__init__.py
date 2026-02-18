"""
Network analysis from file-based data or live-scraped Twitter profiles.
- Graph profiling: fetch social graph -> Louvain communities -> profile key nodes -> vulnerability report + D3 viz.
- Profile-based: load behavioral_matrix.json (or --apify for live scrape) -> community detection -> engagement brief.
"""

from .analyzer import NetworkAnalyzer, load_edges_file, load_profiles_from_dir
from .apify_network import fetch_profiles_via_apify
from .content_overlay import ContentOverlayReport, analyze_content_overlay
from .graph_analysis import (
    NetworkAnalysis,
    build_network_analysis,
    network_analysis_to_dict,
)

# v3 analytical engine modules
from .graph_builder import GraphSpec, build_graph, filter_graph_by_time
from .influence_flow import InfluenceReport, analyze_influence_flow
from .node_profiler import NodeProfile, profile_key_nodes
from .pipeline import run_network_graph_pipeline
from .temporal import TemporalReport, analyze_temporal
from .vulnerability import VulnerabilityReport, analyze_vulnerability

__all__ = [
    "NetworkAnalyzer",
    "load_profiles_from_dir",
    "load_edges_file",
    "fetch_profiles_via_apify",
    "NetworkAnalysis",
    "build_network_analysis",
    "network_analysis_to_dict",
    "NodeProfile",
    "profile_key_nodes",
    "run_network_graph_pipeline",
    # v3 analytical engine
    "GraphSpec",
    "build_graph",
    "filter_graph_by_time",
    "InfluenceReport",
    "analyze_influence_flow",
    "VulnerabilityReport",
    "analyze_vulnerability",
    "TemporalReport",
    "analyze_temporal",
    "ContentOverlayReport",
    "analyze_content_overlay",
]
