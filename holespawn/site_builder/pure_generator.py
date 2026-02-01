"""
Pure generation from profile: no templates, no buckets.
LLM designs site structure, CSS, and page content from full profile data.
"""

import html
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional

from holespawn.cost_tracker import CostTracker
from holespawn.ingest import SocialContent
from holespawn.llm import call_llm
from holespawn.profile import PsychologicalProfile

logger = logging.getLogger(__name__)


def _profile_for_prompt(profile: PsychologicalProfile) -> dict[str, Any]:
    """Serialize profile for LLM prompts (all fields we care about)."""
    return {
        "vocabulary_sample": getattr(profile, "vocabulary_sample", [])[:50],
        "sample_phrases": getattr(profile, "sample_phrases", [])[:20],
        "communication_style": getattr(profile, "communication_style", "conversational/rambling"),
        "sentence_structure": getattr(profile, "sentence_structure", "mixed"),
        "emoji_usage": getattr(profile, "emoji_usage", "none"),
        "specific_interests": getattr(profile, "specific_interests", [])[:15],
        "obsessions": getattr(profile, "obsessions", [])[:10],
        "pet_peeves": getattr(profile, "pet_peeves", [])[:10],
        "browsing_style": getattr(profile, "browsing_style", "scanner"),
        "content_density_preference": getattr(profile, "content_density_preference", "moderate"),
        "visual_preference": getattr(profile, "visual_preference", "balanced"),
        "cultural_references": getattr(profile, "cultural_references", [])[:10],
        "sentiment_compound": getattr(profile, "sentiment_compound", 0),
        "intensity": getattr(profile, "intensity", 0),
    }


def _extract_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    return json.loads(text)


STRUCTURE_SYSTEM = """You are designing a personalized website to capture one specific person's attention.

You will receive EVERYTHING we know about them: vocabulary, how they write, what they care about, how they browse, their cultural context.

TASK: Design a website structure that would trap THIS SPECIFIC PERSON's attention.

Think about:
- What sites do they actually visit?
- How do they browse? (long articles? quick scrolling? deep linking?)
- What topics would create rabbit holes for THEM?
- What would make THEM keep clicking?

Design 10-20 interconnected pages. Be creative. Don't use generic structures—design for THIS person.

For each page specify:
- filename: e.g. "index.html", "specific_topic.html" (one must be "index.html" as entry point)
- title: In their voice, using their vocabulary
- topic: Specific concept from their world (not "AI" but "mesa-optimization in reward modeling")
- content_type: article | feed | thread | gallery | custom (whatever fits)
- links_to: List of other page filenames this page should link to (3-8 per page)
- hook: Why they would want to read this page

Rules:
- Every page has 3-8 links_to (other filenames in your list)
- No dead ends—always more to explore
- Topics are SPECIFIC to their interests
- Exactly one page must have filename "index.html"

Return valid JSON only, no markdown or explanation:
{
  "pages": [
    {
      "filename": "index.html",
      "title": "...",
      "topic": "...",
      "content_type": "article",
      "links_to": ["page2.html", "page3.html"],
      "hook": "..."
    },
    ...
  ]
}
"""


def generate_site_structure(
    profile: PsychologicalProfile,
    *,
    call_llm_fn: Callable[..., str] = call_llm,
    tracker: Optional[CostTracker] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    calls_per_minute: int = 20,
) -> dict[str, Any]:
    """LLM designs entire site structure from profile. Returns {pages: [{filename, title, topic, content_type, links_to, hook}, ...]}."""
    p = _profile_for_prompt(profile)
    user = f"""Here is EVERYTHING we know about this person:

VOCABULARY (words they actually use):
{', '.join(p['vocabulary_sample']) if p['vocabulary_sample'] else 'N/A'}

SAMPLE PHRASES (how they actually write):
{json.dumps(p['sample_phrases'][:15])}

COMMUNICATION STYLE: {p['communication_style']}
- Sentence structure: {p['sentence_structure']}
- Emoji usage: {p['emoji_usage']}

INTERESTS & OBSESSIONS:
- Topics: {', '.join(p['specific_interests']) if p['specific_interests'] else 'N/A'}
- Obsessions: {', '.join(p['obsessions']) if p['obsessions'] else 'N/A'}
- Pet peeves: {', '.join(p['pet_peeves']) if p['pet_peeves'] else 'N/A'}

BROWSING PATTERNS:
- Style: {p['browsing_style']}
- Content density: {p['content_density_preference']}
- Visual preference: {p['visual_preference']}

CULTURAL CONTEXT: {', '.join(p['cultural_references']) if p['cultural_references'] else 'N/A'}

PSYCHOLOGY: Sentiment {p['sentiment_compound']:.2f}, Intensity {p['intensity']:.2f}

---

Design a website structure that would trap THIS person's attention. 10-20 pages. One page must be index.html. Every page links_to 3-8 other pages. Return JSON only."""

    raw = call_llm_fn(
        STRUCTURE_SYSTEM,
        user,
        provider_override=provider,
        model_override=model,
        max_tokens=4096,
        operation="pure_structure",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
    data = _extract_json(raw)
    pages = data.get("pages", [])
    if not any(p.get("filename") == "index.html" for p in pages) and pages:
        pages[0]["filename"] = "index.html"
    return {"pages": pages}


CSS_SYSTEM = """Generate a complete CSS stylesheet for a website.

You will receive profile data about the person who will use this site: how they write, their vocabulary, communication style, interests, cultural context.

TASK: Generate CSS that looks like websites THEY actually visit. Don't categorize—generate from their actual data.

Think about:
- What sites match their vocabulary and interests?
- What aesthetic fits their communication style?
- What colors, fonts, layouts would feel natural to them?

Guidelines (adapt, don't copy):
- Casual/playful → bright, modern, fun fonts
- Formal/academic → clean, serif, readable
- Technical → monospace, functional
- Lots of emoji → colorful, expressive
- No emoji → muted, professional
- Rationalist/academic → LessWrong-style (clean, lots of text)
- Crypto/tech → dark mode, terminal aesthetic
- Startup → modern, clean, blue
- Gaming → dark, vibrant accents

Include:
- :root variables (--bg, --text, --accent, --link, --font or similar)
- body (background, color, font-family, line-height, max-width, margin, padding)
- a / links (color, text-decoration, border-bottom, hover)
- article, .content (margins, typography)
- .site-header, .breadcrumbs, nav
- Optional: .feed-item, .hub-card if relevant

Return ONLY valid CSS. No comments, no explanations. Start with :root, then body, then elements."""


def generate_css(
    profile: PsychologicalProfile,
    *,
    call_llm_fn: Callable[..., str] = call_llm,
    tracker: Optional[CostTracker] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    calls_per_minute: int = 20,
) -> str:
    """LLM generates full CSS from profile."""
    p = _profile_for_prompt(profile)
    user = f"""Person who will use this site:

WRITES LIKE: {json.dumps(p['sample_phrases'][:10])}
USES THESE WORDS: {', '.join(p['vocabulary_sample'][:30]) if p['vocabulary_sample'] else 'N/A'}
COMMUNICATION STYLE: {p['communication_style']}
EMOJI: {p['emoji_usage']}
INTERESTS: {', '.join(p['specific_interests'][:10]) if p['specific_interests'] else 'N/A'}
CULTURAL CONTEXT: {', '.join(p['cultural_references']) if p['cultural_references'] else 'N/A'}

Generate CSS that looks like sites THEY visit. Return only valid CSS."""

    raw = call_llm_fn(
        CSS_SYSTEM,
        user,
        provider_override=provider,
        model_override=model,
        max_tokens=2048,
        operation="pure_css",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
    return raw.strip()


CONTENT_SYSTEM = """Generate the body content for one webpage. You will receive:
- Page specs (topic, hook, content_type, which pages to link to)
- Full profile of the target person (vocabulary, voice, interests)
- List of available pages to link to

TASK: Write content that sounds like THEY wrote it and keeps THEM clicking.

Requirements:
1. Use THEIR vocabulary naturally. Match THEIR voice exactly.
2. Reference THEIR specific interests (not generic).
3. Embed 5-8 hyperlinks as <a href="filename.html">anchor text</a> in the body. Link naturally in the text. Use compelling anchor text. Link only to filenames from the links_to list or available pages.
4. End with unresolved tension or new questions—no conclusion.
5. No generic mystery-speak ("protocol", "nexus", "ephemeral") unless that's their style.
6. Return valid HTML: <h2>, <p>, <a> as needed. Body content only—no <html> or <body> tags.
"""


def generate_page_content(
    page_spec: dict[str, Any],
    profile: PsychologicalProfile,
    all_pages: list[dict],
    *,
    call_llm_fn: Callable[..., str] = call_llm,
    tracker: Optional[CostTracker] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    calls_per_minute: int = 20,
    min_links: int = 5,
    max_retries: int = 2,
) -> str:
    """LLM generates HTML body for one page with embedded links. Retries if link count < min_links."""
    p = _profile_for_prompt(profile)
    linkable = [f"{x['filename']} - {x.get('title', '')}" for x in all_pages if x.get("filename") != page_spec.get("filename")]
    links_to = page_spec.get("links_to", [])[:8]

    user = f"""PAGE SPECS:
Topic: {page_spec.get('topic', '')}
Purpose/hook: {page_spec.get('hook', '')}
Type: {page_spec.get('content_type', 'article')}
Must link to these filenames: {json.dumps(links_to)}

TARGET PERSON:
Writes like: {json.dumps(p['sample_phrases'][:10])}
Uses words: {', '.join(p['vocabulary_sample'][:40]) if p['vocabulary_sample'] else 'N/A'}
Cares about: {', '.join(p['obsessions'][:8]) if p['obsessions'] else 'N/A'}
Style: {p['communication_style']}

AVAILABLE PAGES TO LINK TO (use exact filename in href):
{json.dumps(linkable, indent=2)}

Write content in their voice. Embed 5-8 <a href="filename.html">anchor</a> links. No resolution—end with open questions. Return HTML body content only."""

    for attempt in range(max_retries + 1):
        raw = call_llm_fn(
            CONTENT_SYSTEM,
            user,
            provider_override=provider,
            model_override=model,
            max_tokens=2048,
            operation="pure_page_content",
            tracker=tracker,
            calls_per_minute=calls_per_minute,
        )
        content = raw.strip()
        if "```" in content:
            m = re.search(r"```(?:html)?\s*([\s\S]*?)```", content)
            if m:
                content = m.group(1).strip()
        link_count = content.count("<a href=")
        if link_count >= min_links:
            return content
        logger.warning("Page %s has %d links (min %d), retrying...", page_spec.get("filename"), link_count, min_links)
        user += f"\n\nPREVIOUS ATTEMPT had only {link_count} links. You MUST include at least {min_links} <a href=\"...\"> links in the body."
    return content


def validate_site(structure: dict[str, Any], min_pages: int = 5) -> None:
    """Raise ValueError if page count, link count, or connectivity fails."""
    errors = []
    pages = structure.get("pages", [])
    if len(pages) < min_pages:
        errors.append(f"Only {len(pages)} pages, need at least {min_pages}")
    filenames = {p.get("filename") for p in pages if p.get("filename")}
    for page in pages:
        fn = page.get("filename", "")
        if not fn:
            errors.append("Page missing filename")
            continue
        content = page.get("content", "")
        link_count = content.count("<a href=") if content else 0
        if link_count < 3:
            errors.append(f"{fn} has only {link_count} links (need at least 3)")
        for link in page.get("links_to", []):
            if link not in filenames:
                errors.append(f"{fn} links to non-existent {link}")
    if "index.html" not in filenames and pages:
        errors.append("No index.html in pages")
    if errors:
        raise ValueError("Site validation failed:\n" + "\n".join(errors))


def render_site(
    pages: list[dict],
    css: str,
    output_dir: Path,
) -> None:
    """Write styles.css and one HTML file per page (breadcrumb, article, footer with time)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "styles.css").write_text(css, encoding="utf-8")

    for page in pages:
        fn = page.get("filename", "page.html")
        title = page.get("title", fn)
        body_content = page.get("content", "")
        if body_content and not body_content.strip().startswith("<"):
            body_content = f"<p>{html.escape(body_content)}</p>"
        title_esc = html.escape(title, quote=True)
        html_str = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_esc}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <nav class="breadcrumbs">
    <a href="index.html">↩</a>
  </nav>
  <article>
    <h1>{title_esc}</h1>
    <div class="content">{body_content}</div>
  </article>
  <footer>
    <div class="time-tracker"><span id="time">00:00</span></div>
  </footer>
  <script>
    (function() {{
      var start = Date.now();
      setInterval(function() {{
        var elapsed = Math.floor((Date.now() - start) / 1000);
        var m = Math.floor(elapsed / 60);
        var s = elapsed % 60;
        var el = document.getElementById('time');
        if (el) el.textContent = m + ':' + (s < 10 ? '0' : '') + s;
      }}, 1000);
    }})();
  </script>
</body>
</html>"""
        (output_dir / fn).write_text(html_str, encoding="utf-8")


def generate_site_from_profile(
    profile: PsychologicalProfile,
    output_dir: Path,
    *,
    content: Optional[SocialContent] = None,
    call_llm_fn: Callable[..., str] = call_llm,
    tracker: Optional[CostTracker] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    calls_per_minute: int = 20,
    skip_validation: bool = False,
) -> dict[str, Any]:
    """
    Pure generation: structure → CSS → content per page → validate → render.
    No templates. Returns structure (with content filled in).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Generating site structure from profile...")
    structure = generate_site_structure(
        profile,
        call_llm_fn=call_llm_fn,
        tracker=tracker,
        provider=provider,
        model=model,
        calls_per_minute=calls_per_minute,
    )
    pages = structure.get("pages", [])
    logger.info("Generated %d pages", len(pages))

    logger.info("Generating CSS from profile...")
    css = generate_css(
        profile,
        call_llm_fn=call_llm_fn,
        tracker=tracker,
        provider=provider,
        model=model,
        calls_per_minute=calls_per_minute,
    )

    logger.info("Generating page content...")
    for page_spec in pages:
        logger.info("  %s", page_spec.get("filename", "?"))
        page_spec["content"] = generate_page_content(
            page_spec,
            profile,
            pages,
            call_llm_fn=call_llm_fn,
            tracker=tracker,
            provider=provider,
            model=model,
            calls_per_minute=calls_per_minute,
        )

    if not skip_validation:
        validate_site(structure)

    logger.info("Rendering HTML files...")
    render_site(pages, css, output_dir)

    return structure
