"""
Stage 1: Profile — Target substrate profiling.

Wraps holespawn.scraper, holespawn.network, holespawn.profile
to build a comprehensive psychological/network profile of a target.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class TargetProfile:
    """Assembled profile of a target."""
    handle: str
    platform: str = "twitter"
    psychological: dict[str, Any] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)
    vulnerabilities: list[str] = field(default_factory=list)
    content_samples: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def run_profile(target: str, config: dict | None = None) -> TargetProfile:
    """Execute profiling pipeline against a target.

    Attempts to use holespawn modules if available, falls back to
    returning a stub profile for pipeline continuity.
    """
    config = config or {}
    profile = TargetProfile(handle=target)

    # --- Scraper ---
    try:
        from holespawn.scraper import run_scrape
        scrape_data = run_scrape(target, config=config)
        profile.content_samples = scrape_data.get("posts", [])
        profile.raw["scraper"] = scrape_data
        logger.info("Scraper collected %d samples for %s", len(profile.content_samples), target)
    except ImportError:
        logger.warning("holespawn.scraper not available; skipping scrape")
    except Exception as e:
        logger.error("Scraper failed for %s: %s", target, e)

    # --- Network analysis ---
    try:
        from holespawn.network.graph_builder import build_graph
        from holespawn.network.graph_analysis import analyze_graph
        graph = build_graph(target)
        analysis = analyze_graph(graph)
        profile.network = analysis
        profile.raw["network"] = analysis
    except ImportError:
        logger.warning("holespawn.network not available; skipping network analysis")
    except Exception as e:
        logger.error("Network analysis failed for %s: %s", target, e)

    # --- Psychological profile ---
    try:
        from holespawn.profile.analyzer import analyze_profile
        psych = analyze_profile(target, posts=profile.content_samples)
        profile.psychological = psych
        profile.vulnerabilities = psych.get("vulnerabilities", [])
        profile.raw["profile"] = psych
    except ImportError:
        logger.warning("holespawn.profile not available; skipping psych analysis")
    except Exception as e:
        logger.error("Profile analysis failed for %s: %s", target, e)

    return profile
