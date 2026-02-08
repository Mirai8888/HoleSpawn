"""
Wiki-style architecture: interconnected articles with heavy hyperlinking (deep_diver / analytical).
"""

import json
import re
from collections.abc import Callable
from typing import Any

from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

from .base import ArchitectureConfig, BaseArchitecture


def _slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.lower()).strip("_") or "page"


def _extract_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    return json.loads(text)


WIKI_SYSTEM = """You generate a Wikipedia-style INTERCONNECTED article for one person. The page must be HEAVILY HYPERLINKED.

CRITICAL: Content MUST include real HTML links in this exact form: <a href="TARGET_PAGE.html">anchor text</a>
- TARGET_PAGE must be one of the available pages (without path, just the filename like alignment_problem.html).
- Minimum 5 links in the body. Prefer 6-8. Each paragraph should link to at least one other concept.
- Use natural anchor text (not "click here"). Match their vocabulary.

TONE: Match their communication_style exactly. Use their vocabulary_sample. Reference their specific_interests.
NO generic mystery tone unless they are cryptic. End with open questions or "See also", not a conclusion.

Output valid JSON only:
{
  "title": "Article title",
  "content": "HTML string with <p> and <a href=\"page.html\">links</a>",
  "see_also": ["topic_slug_1", "topic_slug_2", "topic_slug_3"]
}
"""


class WikiArchitecture(BaseArchitecture):
    """Deep-diver / analytical: 10-15 wiki-style articles with 5-8 links per page."""

    name = "wiki"
    config = ArchitectureConfig(page_count=15, links_per_page_min=5, style="academic_hypertext")

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
        """Build wiki: index (hub) + one article per topic; each article has embedded <a href>."""
        obs = getattr(profile, "obsessions", [])[:6]
        interests = getattr(profile, "specific_interests", [])[:10]
        topics = list(dict.fromkeys(obs + interests))[:12]
        if not topics:
            topics = ["main_topic"]

        # Build list of page filenames for prompts
        slugs = [_slug(t) for t in topics]
        available_pages = [f"{s}.html" for s in slugs]

        # Single LLM call to get full structure: index + all articles with content containing <a href>
        user = f"""Voice guide:
{voice_guide}

Profile and narrative (excerpt):
{context_str[:10000]}

TASK: Generate a WIKI-SYLE site with {len(topics)} interconnected articles.

Available page filenames (use these EXACTLY in hrefs): {", ".join(available_pages)}

Topics to create one article each: {", ".join(topics)}

For EACH topic, return one object in "articles" array:
- title: Article title (use their vocabulary)
- content: HTML with <p> paragraphs. You MUST include at least 5 <a href="SOMEPAGE.html">anchor</a> links per article. Link to OTHER topics from the list. Example: <p>This relates to <a href="{slugs[1] if len(slugs) > 1 else slugs[0]}.html">concept</a>.</p>
- see_also: 3-5 other topic slugs (from the list: {", ".join(slugs)})

Also return:
- index_title: Portal title (in their voice)
- index_tagline: One line, no resolution promise

Output JSON only:
{{
  "index_title": "...",
  "index_tagline": "...",
  "articles": [
    {{ "topic_slug": "{slugs[0]}", "title": "...", "content": "<p>...<a href=\\"...\">...</a>...</p>", "see_also": ["slug2", "slug3"] }},
    ...
  ]
}}
"""

        raw = call_llm(
            WIKI_SYSTEM,
            user,
            provider_override=provider,
            model_override=model,
            max_tokens=8192,
            operation="wiki_content",
            tracker=tracker,
            calls_per_minute=calls_per_minute,
        )
        data = _extract_json(raw)

        index_title = data.get("index_title", spec.title)
        index_tagline = data.get("index_tagline", spec.tagline)
        articles = data.get("articles", [])

        # Build content graph
        graph: dict[str, dict[str, Any]] = {}
        cards = []
        for i, art in enumerate(articles[: len(topics)]):
            slug = (
                art.get("topic_slug", slugs[i]) if i < len(slugs) else slugs[min(i, len(slugs) - 1)]
            )
            title = art.get("title", topics[i] if i < len(topics) else slug)
            body = art.get("content", "")
            see_also = art.get("see_also", [])
            # Ensure .html in see_also hrefs
            related_links = [
                {"href": f"{_slug(s)}.html", "title": s.replace("_", " ").title()}
                for s in see_also[:6]
            ]
            graph[slug] = {
                "type": "article",
                "title": title,
                "content": body,
                "see_also": related_links,
                "back_link": "index.html",
            }
            cards.append(
                {
                    "id": slug,
                    "title": title,
                    "description": f"Explore {title}.",
                    "href": f"{slug}.html",
                }
            )

        graph["index"] = {
            "type": "hub",
            "title": index_title,
            "tagline": index_tagline,
            "cards": cards,
        }
        return graph
