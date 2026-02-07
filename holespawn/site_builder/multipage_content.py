"""
Generate content for multi-page INFINITE RABBIT HOLE sites.
Self-reinforcing loop: each page introduces more complexity, not answers. No resolution — only deeper questions.
"""

import json
import re
from typing import Any, Optional

from holespawn.context import build_context
from holespawn.cost_tracker import CostTracker
from holespawn.experience import ExperienceSpec
from holespawn.ingest import SocialContent
from holespawn.llm import call_llm
from holespawn.profile import PsychologicalProfile
from holespawn.site_builder.content import _build_voice_guide


def _hook_templates_by_type(browsing_style: str, communication_style: str) -> str:
    """Return hook/ending templates for infinite rabbit hole by profile type."""
    if browsing_style == "doom_scroller":
        return (
            "DOOM SCROLLER — Each entry must END with unresolved tension and links: "
            '"New evidence suggests...", "But there\'s something worse...", "Related: 3 signs experts are underestimating this". '
            'Every entry MUST have "related": [0-based indices of 2-3 other entries]. No closure — only more concerns.'
        )
    if browsing_style == "deep_diver" or communication_style == "analytical/precise":
        return (
            "ANALYTICAL / DEEP DIVER — Each page must END with open questions: "
            '"Actually, this raises another question...", "But wait, there\'s an edge case...". '
            'Every page MUST have 3-5 "related" (topic ids). No "conclusion" — only "Further questions" or "See also".'
        )
    return (
        "HUB / WIKI — Each page must END with exploration hooks: "
        '"See also: [3-5 related topics]", "Further reading on...". '
        'Every topic page MUST have "related": [3-5 other topic ids]. No resolution — only "Implications" or "Further reading".'
    )


MULTIPAGE_SYSTEM = """You are generating content for an INFINITE RABBIT HOLE website tailored to one person.

CRITICAL: This is NOT a puzzle with a solution. NOT an ARG with an ending. It is a self-reinforcing content loop.
- Each page introduces NEW uncertainty/complexity — not answers.
- Heavy interlinking: 3-5 links per page minimum. Links promise insight but deliver more questions.
- No resolution pages — only "Further questions", "See also", "Related", or "Load more".
- Goal: They feel "Oh fuck, I didn't think about THAT" / "Wait, what about..." / "Just one more page..."

Match their communication style, vocabulary, and interests exactly. Hook their anxiety/fascination (obsessions, pet_peeves).

Output valid JSON only, no markdown or explanation.

---

For FEED-style (doom scroller — infinite feed of escalating concerns):
{
  "structure": "feed",
  "index_title": "Short title in their voice (hook their anxiety/fascination)",
  "items": [
    {
      "title": "Headline that triggers their specific concern (in their style)",
      "preview": "2-3 sentences. Escalating concern. Use their vocabulary.",
      "read_more_hook": "Why they must click (e.g. 'New evidence suggests...', 'What they're not telling you...')"
    }
  ],
  "entries": [
    {
      "title": "Same as item or expanded",
      "body": "OPENING: Something they think they understand. BODY: Complication/evidence that breaks that. ENDING: Unresolved tension + 'But there's more...' / 'Related: ...'. Use <p>. No conclusion.",
      "related": [1, 3]
    }
  ]
}
- items and entries same length. Each entry "related" = 0-based indices of 2-3 OTHER entries (so they click through).
- Generate 8-12 items. Each entry ends with MORE questions, not answers. Optional: "feed_batch_2": [more items] for "Load more" (same shape as items/entries).

---

For HUB-style (analytical / scanner / deep diver — interconnected articles or wiki):
{
  "structure": "hub",
  "index_title": "Short title in their voice (edge case / open question)",
  "index_tagline": "One line that pulls them in. No promise of resolution.",
  "cards": [
    { "id": "slug_for_url", "title": "Topic from their interests", "description": "Why click — hint at complexity, not answer." }
  ],
  "topic_pages": [
    {
      "title": "Same as card",
      "body": "OPENING: Familiar concept. BODY: Edge case / tension that challenges it. No conclusion — end with 'Actually, this raises...' or 'See also'. Use <p>. Dense; 2-3 links per paragraph if wiki-style.",
      "related": ["other_topic_id_1", "other_topic_id_2", "other_topic_id_3"]
    }
  ]
}
- cards and topic_pages same length. Each topic "related" = 3-5 other card ids. Minimum 3 links per page.
- For deep_diver: body can include inline links; "see_also" 5-8 topic ids. No "Conclusion" — only "Further reading" or "Implications".
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    return json.loads(text)


def _slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.lower()).strip("_") or "page"


def _feed_batches_from_data(data: dict, num_entries: int = 0) -> list[list[dict]]:
    """Extract feed batches for 'Load more'. First batch = items; optional feed_batch_2 = more items (links cycle to existing entries)."""
    items = data.get("items", [])
    if not items:
        return []
    n = num_entries or len(items)
    batch1 = [it.copy() for it in items]
    for i, it in enumerate(batch1):
        it["link"] = it.get("link", f"entry_{i}.html")
    batches = [batch1]
    batch2_items = data.get("feed_batch_2", data.get("feed_batch_2_items"))
    if batch2_items and isinstance(batch2_items, list):
        batch2 = []
        for j, it in enumerate(batch2_items[:8]):
            row = it.copy() if isinstance(it, dict) else {}
            row["link"] = f"entry_{j % n}.html"
            batch2.append(row)
        if batch2:
            batches.append(batch2)
    return batches


def generate_multipage_content(
    content: SocialContent,
    profile: PsychologicalProfile,
    spec: ExperienceSpec,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tracker: Optional[CostTracker] = None,
    calls_per_minute: int = 20,
) -> dict[str, Any]:
    """
    Generate all page content for a multi-page site (feed or hub).
    Returns dict: {"index": {...}, "entry_0": {...}, ...} for builder.build().
    """
    voice_guide = _build_voice_guide(profile)
    context = build_context(content, profile)
    browsing = getattr(profile, "browsing_style", "scanner")
    comm = getattr(profile, "communication_style", "conversational/rambling")
    interests = getattr(profile, "specific_interests", [])[:10]
    obsessions = getattr(profile, "obsessions", [])[:6]
    pet_peeves = getattr(profile, "pet_peeves", [])[:6]
    hook_templates = _hook_templates_by_type(browsing, comm)

    structure_hint = "feed" if browsing == "doom_scroller" else "hub"
    # Discord context for uncanny personalization (when profile has Discord signals)
    tribal = getattr(profile, "tribal_affiliations", [])[:8]
    reaction_triggers = getattr(profile, "reaction_triggers", [])[:6]
    intimacy = getattr(profile, "conversational_intimacy", "")
    discord_block = ""
    if tribal or reaction_triggers or intimacy:
        discord_block = """
Discord context (if available — use for deeper personalization; content should feel like it understands their Discord presence, not just public persona):
- Servers / community themes: """ + (", ".join(tribal) if tribal else "N/A") + """
- Themes they react to emotionally: """ + (", ".join(reaction_triggers) if reaction_triggers else "N/A") + """
- Conversational intimacy: """ + (intimacy or "N/A") + """. Mirror their actual conversational patterns from messages. Reference server-specific context subtly. Use language/references from their community.
"""
    user_content = f"""Voice guide:
{voice_guide}

Profile summary and narrative:
{context[:12000]}
{discord_block}
INFINITE RABBIT HOLE — no resolution, only deeper questions.

Their profile:
- Browsing style: {browsing}. Communication style: {comm}.
- Anxiety triggers / pet peeves: {', '.join(pet_peeves) if pet_peeves else 'N/A'}
- Obsessions: {', '.join(obsessions)}. Specific interests: {', '.join(interests)}

Hook/ending rules for this type:
{hook_templates}

Generate a multi-page site as JSON. Use structure "{structure_hint}".
- Every page/entry: start with something familiar, introduce complexity/edge case, END with unresolved tension + links. NO conclusions.
- Minimum 3-5 links per page (related entries or topics). Links promise clarity but deliver more questions.
- Match their voice exactly. Reference their obsessions and interests in every item. They should feel "Just one more page..."

Output the JSON only."""

    raw = call_llm(
        MULTIPAGE_SYSTEM,
        user_content,
        provider_override=provider,
        model_override=model,
        max_tokens=4096,
        operation="multipage_content",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
    data = _extract_json(raw)

    result: dict[str, Any] = {}
    struct = data.get("structure", "hub")

    if struct == "feed":
        items = data.get("items", [])
        entries = data.get("entries", [])
        index_title = data.get("index_title", spec.title)
        while len(entries) < len(items):
            entries.append({"title": items[len(entries)].get("title", ""), "body": "", "related": []})
        items = items[: len(entries)]
        for i in range(len(items)):
            it = items[i].copy() if isinstance(items[i], dict) else {}
            it["link"] = f"entry_{i}.html"
            items[i] = it
        result["index"] = {
            "type": "feed",
            "title": index_title,
            "items": items,
            "feed_batches": _feed_batches_from_data(data, len(entries)),
        }
        for i, ent in enumerate(entries[: len(items)]):
            related_indices = ent.get("related", [])
            related_links = [
                {"href": f"entry_{j}.html", "title": entries[j].get("title", f"Entry {j + 1}")[:50]}
                for j in related_indices
                if isinstance(j, int) and 0 <= j < len(entries) and j != i
            ][:5]
            result[f"entry_{i}"] = {
                "type": "article",
                "title": ent.get("title", f"Entry {i + 1}"),
                "body": ent.get("body", ""),
                "back_link": "index.html",
                "related_links": related_links,
            }
    else:
        cards = data.get("cards", [])
        topic_pages = data.get("topic_pages", [])
        index_title = data.get("index_title", spec.title)
        index_tagline = data.get("index_tagline", spec.tagline)
        while len(topic_pages) < len(cards):
            topic_pages.append({"title": "", "body": "", "related": []})
        cards = cards[: len(topic_pages)]
        for j, c in enumerate(cards):
            c["href"] = f"{_slug(c.get('id', f'topic_{j}'))}.html"
            c["title"] = c.get("title", f"Topic {j + 1}")
            c["description"] = c.get("description", "")
        result["index"] = {
            "type": "hub",
            "title": index_title,
            "tagline": index_tagline,
            "cards": cards,
        }
        for j, tp in enumerate(topic_pages[: len(cards)]):
            slug = _slug(cards[j].get("id", f"topic_{j}"))
            related = tp.get("related", [])
            related_links = [
                {"href": f"{_slug(r)}.html", "title": r.replace("_", " ").title()}
                for r in related[:6]
            ]
            result[slug] = {
                "type": "topic",
                "title": tp.get("title", cards[j].get("title", slug)),
                "body": tp.get("body", ""),
                "related_links": related_links,
                "back_link": "index.html",
            }

    return result
