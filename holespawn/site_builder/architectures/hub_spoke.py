"""
Hub-spoke architecture: central hub with topic cards and topic pages (scanner default).
"""

import json
import re
from typing import Any, Callable, Optional

from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

from .base import BaseArchitecture, ArchitectureConfig


def _slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.lower()).strip("_") or "page"


def _extract_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    return json.loads(text)


HUB_SYSTEM = """You generate a HUB-SPOKE site for one person. Index = hub with topic cards; each topic = one page with heavy linking.

CRITICAL: Each topic page "body" MUST include real HTML links: <a href="OTHER_TOPIC_SLUG.html">anchor text</a>. Minimum 3 links per page. Available slugs will be listed. Use their vocabulary.

TONE: Match communication_style. No resolution — "See also", "Further questions". Output valid JSON only.
"""


class HubSpokeArchitecture(BaseArchitecture):
    """Scanner default: hub index + 6-10 topic pages with cross-links."""

    name = "hub_spoke"
    config = ArchitectureConfig(page_count=12, links_per_page_min=3, style="topic_cards")

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
        """Build hub: index (cards) + topic pages with content containing <a href>."""
        obs = getattr(profile, "obsessions", [])[:4]
        interests = getattr(profile, "specific_interests", [])[:8]
        topics = list(dict.fromkeys(obs + interests))[:8]
        if not topics:
            topics = ["topic_one", "topic_two"]
        slugs = [_slug(t) for t in topics]
        available = [f"{s}.html" for s in slugs]

        user = f"""Voice guide:
{voice_guide}

Profile (excerpt):
{context_str[:10000]}

TASK: Hub-spoke site. Topics (one page each): {', '.join(topics)}. Slugs for hrefs: {', '.join(available)}

For each topic return in "topic_pages": title, body (HTML with <p> and at least 3 <a href="slug.html">...</a>), related (3-5 other slugs).
Also index_title, index_tagline, cards (id=slug, title, description).

Output JSON:
{{
  "index_title": "...",
  "index_tagline": "...",
  "cards": [ {{ "id": "slug", "title": "...", "description": "..." }}, ... ],
  "topic_pages": [ {{ "title": "...", "body": "<p>...<a href=\\"x.html\\">...</a>...</p>", "related": ["slug2"] }}, ... ]
}}
"""

        raw = call_llm(
            HUB_SYSTEM,
            user,
            provider_override=provider,
            model_override=model,
            max_tokens=6144,
            operation="hub_content",
            tracker=tracker,
            calls_per_minute=calls_per_minute,
        )
        data = _extract_json(raw)

        index_title = data.get("index_title", spec.title)
        index_tagline = data.get("index_tagline", spec.tagline)
        cards = data.get("cards", [])
        topic_pages = data.get("topic_pages", [])

        while len(topic_pages) < len(slugs):
            topic_pages.append({"title": "", "body": "", "related": []})
        cards = cards[: len(slugs)]
        topic_pages = topic_pages[: len(slugs)]

        graph: dict[str, dict[str, Any]] = {}
        for j, c in enumerate(cards):
            sid = c.get("id", slugs[j])
            c["href"] = f"{_slug(sid)}.html"
            c["title"] = c.get("title", topics[j] if j < len(topics) else sid)
            c["description"] = c.get("description", "")

        graph["index"] = {"type": "hub", "title": index_title, "tagline": index_tagline, "cards": cards}

        for j, tp in enumerate(topic_pages[: len(cards)]):
            slug = _slug(cards[j].get("id", slugs[j]))
            related = tp.get("related", [])
            related_links = [{"href": f"{_slug(r)}.html", "title": str(r).replace("_", " ").title()} for r in related[:6]]
            graph[slug] = {
                "type": "article",
                "title": tp.get("title", cards[j].get("title", slug)),
                "content": tp.get("body", ""),
                "see_also": related_links,
                "back_link": "index.html",
            }
        return graph
