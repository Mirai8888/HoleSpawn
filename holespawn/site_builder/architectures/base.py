"""
Base architecture for dynamic site generation.
Each architecture produces a content graph (page_name -> page_data) with real hyperlinks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional

from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile


@dataclass
class ArchitectureConfig:
    """Configuration for an architecture (page counts, links, style)."""
    page_count: int = 10
    links_per_page_min: int = 3
    style: str = "default"


class BaseArchitecture(ABC):
    """Base for profile-specific site architectures (wiki, feed, hub, thread, gallery)."""

    name: str = "base"
    config: ArchitectureConfig = ArchitectureConfig()

    @abstractmethod
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
        """
        Build content graph: dict of page_key -> page_data.
        page_key: "index" or "topic_slug" or "post_0" (no .html).
        page_data: type, title, content (HTML with <a href>), see_also, etc.
        Content MUST include real hyperlinks (<a href="...">).
        """
        raise NotImplementedError
