"""
Dynamic site generation: choose architecture from profile, build content graph with real hyperlinks, render.
Replaces rigid template flow with profile-driven structure.
"""

import logging
from pathlib import Path
from typing import Any

from holespawn.context import build_context
from holespawn.cost_tracker import CostTracker
from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.llm import call_llm
from holespawn.profile import PsychologicalProfile
from holespawn.site_builder.architectures import choose_architecture
from holespawn.site_builder.architectures.base import BaseArchitecture
from holespawn.site_builder.content import _build_voice_guide
from holespawn.site_builder.dynamic_renderer import render_pages

logger = logging.getLogger(__name__)


def _validate_connectivity(
    content_graph: dict[str, dict[str, Any]],
    architecture: BaseArchitecture,
) -> None:
    """Warn if any article page has fewer than links_per_page_min hyperlinks."""
    min_links = architecture.config.links_per_page_min
    for key, data in content_graph.items():
        if key == "index":
            continue
        content = data.get("content", data.get("body", ""))
        if not content:
            continue
        count = content.count("<a href=")
        if count < min_links:
            logger.warning(
                "Page %s has %d links (min %d). Consider regenerating for heavier linking.",
                key,
                count,
                min_links,
            )


def generate_dynamic_site(
    content: SocialContent,
    profile: PsychologicalProfile,
    spec: ExperienceSpec,
    output_dir: Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    tracker: CostTracker | None = None,
    calls_per_minute: int = 20,
) -> BaseArchitecture:
    """
    Generate site using profile-chosen architecture (wiki, feed, hub, thread, gallery).
    Writes HTML files with real hyperlinks and profile-matched aesthetic.
    Returns the architecture used.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    architecture = choose_architecture(profile)
    context_str = build_context(content, profile)
    voice_guide = _build_voice_guide(profile)

    content_graph = architecture.build_content_graph(
        profile,
        content,
        spec,
        call_llm=call_llm,
        context_str=context_str,
        voice_guide=voice_guide,
        tracker=tracker,
        provider=provider,
        model=model,
        calls_per_minute=calls_per_minute,
    )

    _validate_connectivity(content_graph, architecture)
    render_pages(content_graph, output_dir, profile, spec)
    return architecture
