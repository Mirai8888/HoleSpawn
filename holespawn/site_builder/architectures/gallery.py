"""
Gallery architecture: visual grid (visual_browser).
Falls back to hub-spoke with gallery-style cards for now.
"""

from typing import Any, Callable, Optional

from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

from .base import BaseArchitecture, ArchitectureConfig
from .hub_spoke import HubSpokeArchitecture


class GalleryArchitecture(BaseArchitecture):
    """Visual browser: grid of cards. Uses hub_spoke with gallery layout."""

    name = "gallery"
    config = ArchitectureConfig(page_count=12, links_per_page_min=3, style="visual_grid")

    def build_content_graph(
        self,
        profile: PsychologicalProfile,
        content: SocialContent,
        spec: ExperienceSpec,
        *,
        call_llm: Callable[..., str],
        context_str: str,
        voice_guide: str,
        tracker: Optional[Any] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        calls_per_minute: int = 20,
    ) -> dict[str, dict[str, Any]]:
        """Build gallery-style graph (hub + topic pages with gallery type)."""
        hub = HubSpokeArchitecture()
        graph = hub.build_content_graph(
            profile, content, spec,
            call_llm=call_llm,
            context_str=context_str,
            voice_guide=voice_guide,
            tracker=tracker,
            provider=provider,
            model=model,
            calls_per_minute=calls_per_minute,
        )
        graph["index"]["layout"] = "gallery"
        return graph
