"""
Dynamic site architectures: different structures per profile type.
"""

from holespawn.profile import PsychologicalProfile

from .base import ArchitectureConfig, BaseArchitecture
from .feed import FeedArchitecture
from .gallery import GalleryArchitecture
from .hub_spoke import HubSpokeArchitecture
from .thread import ThreadArchitecture
from .wiki import WikiArchitecture


def choose_architecture(profile: PsychologicalProfile) -> BaseArchitecture:
    """Choose site architecture from profile browsing_style (and optionally communication_style)."""
    style = getattr(profile, "browsing_style", "scanner")
    comm = getattr(profile, "communication_style", "")

    if style == "deep_diver" or comm == "analytical/precise":
        return WikiArchitecture()
    if style == "doom_scroller":
        return FeedArchitecture()
    if style == "thread_reader":
        return ThreadArchitecture()
    if style == "visual_browser":
        return GalleryArchitecture()
    return HubSpokeArchitecture()


__all__ = [
    "choose_architecture",
    "BaseArchitecture",
    "ArchitectureConfig",
    "WikiArchitecture",
    "FeedArchitecture",
    "HubSpokeArchitecture",
    "ThreadArchitecture",
    "GalleryArchitecture",
]
