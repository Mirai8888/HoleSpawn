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


def _profile_for_design_prompt(profile: PsychologicalProfile) -> dict[str, Any]:
    """Serialize profile for design system generator (all design-relevant fields)."""
    p = _profile_for_prompt(profile)
    p["color_palette"] = getattr(profile, "color_palette", "neutral")
    p["layout_style"] = getattr(profile, "layout_style", "balanced")
    p["typography_vibe"] = getattr(profile, "typography_vibe", "clean sans")
    p["link_following_likelihood"] = getattr(profile, "link_following_likelihood", "medium")
    p["avg_sentence_length"] = getattr(profile, "avg_sentence_length", 15.0)
    p["avg_word_length"] = getattr(profile, "avg_word_length", 4.5)
    # Discord-specific (for design personalization)
    p["tribal_affiliations"] = getattr(profile, "tribal_affiliations", [])[:12]
    p["reaction_triggers"] = getattr(profile, "reaction_triggers", [])[:10]
    p["conversational_intimacy"] = getattr(profile, "conversational_intimacy", "moderate")
    p["community_role"] = getattr(profile, "community_role", "participant")
    p["engagement_rhythm"] = getattr(profile, "engagement_rhythm", {})
    return p


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

    logger.info("Generating site structure (may take 1–2 minutes)...")
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


DESIGN_SYSTEM_SYSTEM = """You are generating a complete CSS design system that will psychologically capture one specific person. The goal is not to "look nice" but to create an aesthetic that feels personally resonant, guides their attention to engagement hooks, and makes exploration feel more natural than leaving. Design is an active component of the trap.

FRAMING: Generate a design system that will psychologically capture this person. The aesthetic should feel personally resonant, guide their attention to engagement hooks, and make exploration feel more natural than leaving.

AESTHETIC MANIPULATION:
- Use colors and typography to create specific emotional states (calm vs anxious, curious vs satisfied) based on their profile.
- Design information hierarchy so attention is drawn to content that matches their obsessions, pet_peeves, and susceptibilities.
- Create visual rhythm that matches their browsing patterns (doom_scroller = relentless flow; deep_diver = paced, layered; scanner = clear entry points) so they stay in flow state.
- Use whitespace and density to overwhelm or soothe as appropriate (content_density_preference, intensity, sentiment).

FRICTION DESIGN:
- Navigation should feel natural for exploration but unclear for exit.
- Make ".back a" and any "home" or exit links LESS visually prominent than links that go deeper (e.g. smaller, lower contrast, muted). Use visual weight to pull toward content and "See also" / "Related" / content links, not toward leaving.
- Style .back a so it is de-emphasized; style .content a, .feed-item a, .hub-card, .see-also a, .related a so they are more prominent and inviting.

UNCANNY PERSONALIZATION:
- When the profile has strong aesthetic signals (color_palette, layout_style, typography_vibe), lean into them so it feels "made for me."
- Use visual callbacks to themes in their world (cultural_references, specific_interests) without being obvious.
- Create a feeling of "this understands me" through typography, color, and rhythm choices.

QUALITY CONSTRAINTS (non-negotiable):
- Contrast: Text on background must meet WCAG AA (4.5:1 for normal text, 3:1 for large). Use hex colors that satisfy this.
- Typography: Use a clear type scale (e.g. 1rem base, 1.25–1.5 for h1, 0.9–1 for small). Prefer web-safe or common web font stacks (system-ui, Georgia, "Segoe UI", "Helvetica Neue", "Courier New", etc.).
- Visual hierarchy: Headings and content links must stand out; back/exit must be visually secondary.
- Accessibility: Ensure focus states for interactive elements (e.g. outline or visible focus ring for .hub-card:focus, .load-more button:focus).

EXAMPLES OF BEAUTIFUL, DISTINCT SITES (vary your output; do not copy):
- Editorial: Clear hierarchy, generous whitespace, serif for body, strong headings (e.g. The Verge, NYT).
- Minimal brutalist: High contrast, strict grid, limited palette, bold type (e.g. Bloomberg, some portfolios).
- Warm and immersive: Soft contrast, flowing layout, rounded corners, inviting links (e.g. Medium, Substack).
- Terminal/tech: Dark bg, monospace, accent color for links, tight spacing (e.g. dev docs, CLI aesthetics).
- Playful/chaotic: Bright accents, varied weights, asymmetric layout, high energy (e.g. meme-adjacent, youth brands).

When Discord data is available in the profile (tribal_affiliations, reaction_triggers, conversational_intimacy, community_role, engagement_rhythm):
- Use tribal affiliations to inform aesthetic (match community vibe of their servers).
- Use conversational style from their messages (not tweet style) for copy voice.
- Reference server themes subtly in visual callbacks (color, tone).
- Match engagement rhythm in pacing/density (peak_hours, message_frequency).
- Adjust intimacy level of content based on their conversational_intimacy (guarded vs open vs vulnerable).

REQUIRED CSS COVERAGE (you must include styles for all of these; the site HTML uses these class names):
- :root with variables (e.g. --color-bg, --color-text, --color-accent, --color-secondary, --font, or similar).
- * { box-sizing: border-box; }
- body (font-family, background, color, line-height, min-height: 100vh).
- .site-header, .site-header h1, .tagline
- .site-main (max-width, margin, padding as appropriate to layout_style)
- .site-footer
- .section, .section h2, .section-narrative, .section-body
- .section-puzzle, .puzzle-question, .puzzle-input, .puzzle-check, .puzzle-hint, .puzzle-feedback
- .back, .back a (de-emphasized: smaller and/or lower contrast than content links)
- .layout-feed .feed, .feed-item, .feed-item h3, .feed-item a, .feed-item .preview, .feed-item .hook
- .load-more, .load-more button
- .layout-hub .hub-grid, .hub-card, .hub-card h3, .hub-card p
- .layout-article article, .layout-topic article, .layout-wiki article
- article h1, .content, .content p, .content a
- .see-also, .related, .see-also h3, .related h3, .see-also ul, .related ul, .see-also a, .related a
- .infobox (optional; for wiki-style pages)

LAYOUT SYSTEM: Derive from layout_style and browsing_style. "Scattered" or "chaotic" → asymmetric grid, varied gaps; "structured" or "balanced" → clear grid, consistent spacing; "flowing" → single column, generous line-height and margins. Express via grid-template-columns, gap, max-width, padding.

Return ONLY valid CSS. No markdown, no comments, no explanation. Start with :root, then body, then elements. Use the exact class names above."""


def generate_design_system(
    profile: PsychologicalProfile,
    spec: Any = None,
    *,
    call_llm_fn: Callable[..., str] = call_llm,
    tracker: Optional[CostTracker] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    calls_per_minute: int = 20,
) -> str:
    """
    Canonical design system generator. Returns full CSS from profile (and optional spec).
    All builders should use this instead of preset lookups. Design is tuned for psychological
    capture: resonant aesthetic, attention to hooks, exploration favored over exit.
    """
    p = _profile_for_design_prompt(profile)
    user_parts = [
        "TARGET PERSON — generate a design system that will psychologically capture them.",
        "",
        "VOICE & STYLE:",
        f"- Sample phrases: {json.dumps(p['sample_phrases'][:12])}",
        f"- Vocabulary: {', '.join(p['vocabulary_sample'][:25]) if p['vocabulary_sample'] else 'N/A'}",
        f"- Communication style: {p['communication_style']}",
        f"- Sentence structure: {p['sentence_structure']}, Emoji: {p['emoji_usage']}",
        "",
        "DESIGN SIGNALS (use these to drive layout, color, type):",
        f"- Color palette preference: {p['color_palette']}",
        f"- Layout style: {p['layout_style']}",
        f"- Typography vibe: {p['typography_vibe']}",
        f"- Browsing style: {p['browsing_style']}",
        f"- Content density: {p['content_density_preference']}, Visual: {p['visual_preference']}",
        f"- Link-following likelihood: {p['link_following_likelihood']}",
        f"- Reading patterns: avg sentence length {p['avg_sentence_length']:.1f}, avg word length {p['avg_word_length']:.1f}",
        "",
        "HOOKS (design hierarchy to pull attention here):",
        f"- Obsessions: {', '.join(p['obsessions'][:8]) if p['obsessions'] else 'N/A'}",
        f"- Pet peeves / anxieties: {', '.join(p['pet_peeves'][:8]) if p['pet_peeves'] else 'N/A'}",
        f"- Interests: {', '.join(p['specific_interests'][:10]) if p['specific_interests'] else 'N/A'}",
        "",
        "CONTEXT:",
        f"- Cultural references: {', '.join(p['cultural_references'][:8]) if p['cultural_references'] else 'N/A'}",
        f"- Sentiment: {p['sentiment_compound']:.2f}, Intensity: {p['intensity']:.2f}",
    ]
    # Discord context (when profile from Discord data)
    if p.get("tribal_affiliations") or p.get("reaction_triggers") or p.get("engagement_rhythm"):
        user_parts.extend([
            "",
            "DISCORD CONTEXT (use for community vibe, pacing, intimacy):",
            f"- Servers / tribal affiliations: {', '.join(p.get('tribal_affiliations', [])[:10]) or 'N/A'}",
            f"- Reaction triggers (what resonates): {', '.join(p.get('reaction_triggers', [])[:8]) or 'N/A'}",
            f"- Conversational intimacy: {p.get('conversational_intimacy', 'moderate')}, Community role: {p.get('community_role', 'participant')}",
            f"- Engagement rhythm: {p.get('engagement_rhythm') or 'N/A'}",
        ])
    if spec is not None:
        user_parts.extend([
            "",
            "EXPERIENCE SPEC (optional overrides):",
            f"- Title/tone from spec; colors if set: primary {getattr(spec, 'color_primary', '')} secondary {getattr(spec, 'color_secondary', '')} accent {getattr(spec, 'color_accent', '')} background {getattr(spec, 'color_background', '')}",
        ])
    user_parts.append("")
    user_parts.append("Generate complete CSS. De-emphasize .back a; emphasize content and deeper links. Return only valid CSS.")
    user = "\n".join(user_parts)

    raw = call_llm_fn(
        DESIGN_SYSTEM_SYSTEM,
        user,
        provider_override=provider,
        model_override=model,
        max_tokens=4096,
        operation="design_system",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
    return raw.strip()


def generate_css(
    profile: PsychologicalProfile,
    *,
    call_llm_fn: Callable[..., str] = call_llm,
    tracker: Optional[CostTracker] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    calls_per_minute: int = 20,
) -> str:
    """LLM generates full CSS from profile. Delegates to generate_design_system (canonical)."""
    return generate_design_system(
        profile,
        spec=None,
        call_llm_fn=call_llm_fn,
        tracker=tracker,
        provider=provider,
        model=model,
        calls_per_minute=calls_per_minute,
    )


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
    min_links: int = 3,
    max_retries: int = 2,
) -> str:
    """LLM generates HTML body for one page with embedded links. Retries if link count < min_links (accept after max_retries)."""
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

Write content in their voice. Embed at least 3 (ideally 5-8) <a href="filename.html">anchor</a> links. No resolution—end with open questions. Return HTML body content only."""

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
        if attempt < max_retries:
            logger.warning("Page %s has %d links (min %d), retrying (%d/%d)...", page_spec.get("filename"), link_count, min_links, attempt + 1, max_retries + 1)
            user += f"\n\nPREVIOUS ATTEMPT had only {link_count} links. You MUST include at least {min_links} <a href=\"...\"> links in the body."
        else:
            logger.info("Page %s has %d links (min %d); accepting after %d attempts.", page_spec.get("filename"), link_count, min_links, max_retries + 1)
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

    logger.info("Generating design system (CSS) from profile...")
    css = generate_design_system(
        profile,
        spec=None,
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
