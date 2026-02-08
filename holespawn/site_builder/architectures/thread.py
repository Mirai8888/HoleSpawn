"""
Thread architecture: nested discussion / thread_reader style.
Falls back to hub-spoke with thread-like styling for now.
"""

from collections.abc import Callable
from typing import Any

from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

from .base import ArchitectureConfig, BaseArchitecture
from .hub_spoke import HubSpokeArchitecture


class ThreadArchitecture(BaseArchitecture):
    """Thread reader: nested discussion. Uses hub_spoke structure with thread styling."""

    name = "thread"
    config = ArchitectureConfig(page_count=10, links_per_page_min=3, style="nested_discussion")

    def build_content_graph(
        self,
        profile: PsychologicalProfile,
        content: SocialContent,
        spec: ExperienceSpec,
        *,
        call_llm: Callable[..., str],
        context_str: str,
        voice_guide: str,
        tracker: Any | None = None,
        provider: str | None = None,
        model: str | None = None,
        calls_per_minute: int = 20,
    ) -> dict[str, dict[str, Any]]:
        """Build thread-style graph (hub + topic pages with "thread" type for styling)."""
        hub = HubSpokeArchitecture()
        graph = hub.build_content_graph(
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
        for key, data in graph.items():
            if key != "index" and data.get("type") == "article":
                data["style"] = "thread"
        return graph
