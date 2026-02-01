"""
Feed architecture: infinite scroll of anxiety-inducing posts (doom_scroller).
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


FEED_SYSTEM = """You generate an INFINITE FEED site for one person (doom-scroller style). Each post triggers their anxieties and links to more.

CRITICAL: Each entry "body" MUST include real HTML links: <a href="post_N.html">anchor text</a> to other posts (N = 0,1,2,...). Minimum 2 links per entry. Use their vocabulary and pet_peeves.

TONE: Match their communication_style. Headlines and previews should escalate concern. No resolution — "But there's more...", "Related: ...".

Output valid JSON only. items and entries same length. Each entry can have "related": [index, index] for 0-based post indices.
"""


class FeedArchitecture(BaseArchitecture):
    """Doom scroller: feed index + 12-20 post pages with cross-links."""

    name = "feed"
    config = ArchitectureConfig(page_count=20, links_per_page_min=2, style="anxiety_feed")

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
        """Build feed: index (feed list) + post_0..post_N with body containing <a href=\"post_X.html\">."""
        n_posts = min(16, max(8, self.config.page_count))
        user = f"""Voice guide:
{voice_guide}

Profile and narrative (excerpt):
{context_str[:10000]}

TASK: Generate a FEED site with {n_posts} posts. Each post is about one of their anxieties/interests (pet_peeves, obsessions).

For each post return:
- title: Headline (their style, escalating)
- preview: 2-3 sentences
- read_more_hook: Why click (e.g. "New evidence suggests...")
- body: HTML with <p>. MUST include at least 2 <a href="post_X.html">...</a> links to OTHER posts (X = 0 to {n_posts - 1}). Use their vocabulary.
- related: [index1, index2] 0-based indices of 2-3 other posts

Output JSON only:
{{
  "index_title": "Short title (their voice)",
  "items": [ {{ "title": "...", "preview": "...", "read_more_hook": "..." }}, ... ],
  "entries": [ {{ "title": "...", "body": "<p>...<a href=\\"post_2.html\\">...</a>...</p>", "related": [1, 3] }}, ... ]
}}
"""

        raw = call_llm(
            FEED_SYSTEM,
            user,
            provider_override=provider,
            model_override=model,
            max_tokens=8192,
            operation="feed_content",
            tracker=tracker,
            calls_per_minute=calls_per_minute,
        )
        data = _extract_json(raw)

        index_title = data.get("index_title", spec.title)
        items = data.get("items", [])
        entries = data.get("entries", [])

        while len(entries) < len(items):
            entries.append({"title": "", "body": "", "related": []})
        entries = entries[: len(items)]
        items = items[: len(entries)]

        graph: dict[str, dict[str, Any]] = {}
        for i, it in enumerate(items):
            it = it.copy() if isinstance(it, dict) else {}
            it["link"] = f"post_{i}.html"
            items[i] = it

        graph["index"] = {"type": "feed", "title": index_title, "items": items}

        for i, ent in enumerate(entries):
            related = ent.get("related", [])
            related_links = [
                {"href": f"post_{j}.html", "title": (entries[j].get("title", f"Post {j + 1}")[:50])}
                for j in related
                if isinstance(j, int) and 0 <= j < len(entries) and j != i
            ][:5]
            graph[f"post_{i}"] = {
                "type": "article",
                "title": ent.get("title", f"Post {i + 1}"),
                "content": ent.get("body", ""),
                "back_link": "index.html",
                "see_also": related_links,
            }
        return graph
