"""
Multi-page "attention trap" site builder.
Generates interconnected pages based on profile browsing_style.
"""

import html
import json
import re
from pathlib import Path
from typing import Any, Optional

from holespawn.experience import ExperienceSpec
from holespawn.profile import PsychologicalProfile

from .templates import (
    _aesthetic_defaults,
    entry_article_page,
    hub_spoke_page,
    infinite_scroll_feed,
    topic_page,
    wiki_article_page,
)


def _slug(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s.lower()).strip("_") or "page"


class MultiPageSiteBuilder:
    """Build multi-page hyperlinked sites from profile + spec + page content."""

    def __init__(self, profile: PsychologicalProfile, spec: ExperienceSpec):
        self.profile = profile
        self.spec = spec

    def build(
        self,
        output_dir: Path,
        page_content: dict[str, Any],
    ) -> None:
        """
        Write all HTML pages, styles.css, and app.js to output_dir.
        page_content: dict from generate_multipage_content() e.g.
          {"index": {"type": "feed", "title": "...", "items": [...]}, "entry_0": {...}, ...}
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Index
        index_data = page_content.get("index", {})
        index_type = index_data.get("type", "hub")
        if index_type == "feed":
            feed_items = index_data.get("items", [])
            feed_batches = index_data.get("feed_batches", [])
            if feed_batches:
                feed_items = feed_batches[0]
            html_str = infinite_scroll_feed(
                feed_items,
                self.spec,
                title=index_data.get("title", self.spec.title),
            )
            (output_dir / "index.html").write_text(html_str, encoding="utf-8")
            for batch_idx, batch in enumerate(feed_batches[1:], start=2):
                (output_dir / f"feed_page_{batch_idx}.json").write_text(
                    json.dumps(batch), encoding="utf-8"
                )
        elif index_type == "hub":
            html_str = hub_spoke_page(
                index_data.get("title", self.spec.title),
                index_data.get("tagline", self.spec.tagline),
                index_data.get("cards", []),
                self.spec,
            )
        else:
            html_str = hub_spoke_page(
                self.spec.title,
                self.spec.tagline,
                index_data.get("cards", [{"id": "start", "title": "Start", "description": "Begin here."}]),
                self.spec,
            )
        (output_dir / "index.html").write_text(html_str, encoding="utf-8")

        # Entry / topic pages
        for key, data in page_content.items():
            if key == "index":
                continue
            page_type = data.get("type", "article")
            title = data.get("title", key)
            body = data.get("body", data.get("content", ""))
            if page_type == "article" or "entry" in key:
                back = data.get("back_link", "index.html")
                related = data.get("related_links", [])
                html_str = entry_article_page(title, body, back, self.spec, related_links=related)
            elif page_type == "topic" or "topic" in key:
                related = data.get("related_links", data.get("see_also", []))
                html_str = topic_page(title, body, related, self.spec)
            else:
                main_content = data.get("main_content", body)
                see_also = data.get("see_also", [])
                infobox = data.get("infobox", "")
                html_str = wiki_article_page(
                    title,
                    main_content if main_content.strip().startswith("<") else f"<p>{html.escape(main_content)}</p>",
                    see_also,
                    self.spec,
                    infobox=infobox,
                )
            filename = f"{key}.html" if not key.endswith(".html") else key
            (output_dir / filename).write_text(html_str, encoding="utf-8")

        # Shared CSS (multi-page aware)
        self._write_css(output_dir)
        # Shared JS (minimal for multi-page)
        self._write_js(output_dir)

    def _write_css(self, output_dir: Path) -> None:
        """Write styles.css with spec colors and multi-page layout rules."""
        s = self.spec
        css = f"""/* Multi-page attention trap theme */
:root {{
  --color-primary: {s.color_primary};
  --color-secondary: {s.color_secondary};
  --color-background: {s.color_background};
  --color-accent: {s.color_accent};
  --font-sans: system-ui, -apple-system, sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: var(--font-sans);
  background: var(--color-background);
  color: var(--color-primary);
  line-height: 1.6;
  min-height: 100vh;
}}
.site-header {{
  padding: 1.5rem 1rem;
  border-bottom: 1px solid var(--color-secondary);
}}
.site-header h1 {{ margin: 0; font-size: 1.5rem; }}
.tagline {{ margin: 0.25rem 0 0; font-size: 0.95rem; color: var(--color-secondary); }}
.back {{ padding: 1rem; }}
.back a {{ color: var(--color-secondary); text-decoration: none; }}
.back a:hover {{ text-decoration: underline; }}
/* Feed layout */
.layout-feed .feed {{ max-width: 600px; margin: 0 auto; padding: 1rem; }}
.feed-item {{ margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--color-secondary); }}
.feed-item h3 {{ margin: 0 0 0.5rem 0; }}
.feed-item a {{ color: var(--color-secondary); text-decoration: none; }}
.feed-item a:hover {{ text-decoration: underline; }}
.feed-item .preview {{ margin: 0.5rem 0; color: var(--color-primary); opacity: 0.9; }}
.feed-item .hook {{ margin: 0.5rem 0 0; }}
.load-more {{ text-align: center; padding: 2rem; }}
.load-more button {{ padding: 0.75rem 1.5rem; background: var(--color-accent); color: var(--color-background); border: none; cursor: pointer; font-size: 1rem; }}
/* Hub layout */
.layout-hub .hub-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1.5rem; padding: 1.5rem; max-width: 1000px; margin: 0 auto; }}
.hub-card {{ display: block; padding: 1.25rem; background: var(--color-background); border: 1px solid var(--color-secondary); border-radius: 6px; color: var(--color-primary); text-decoration: none; }}
.hub-card:hover {{ border-color: var(--color-accent); }}
.hub-card h3 {{ margin: 0 0 0.5rem 0; }}
.hub-card p {{ margin: 0; font-size: 0.9rem; color: var(--color-secondary); }}
/* Article / topic */
.layout-article article, .layout-topic article {{ max-width: 720px; margin: 0 auto; padding: 1.5rem 1rem; }}
.layout-wiki article {{ max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }}
article h1 {{ margin: 0 0 1rem 0; font-size: 1.75rem; }}
.content {{ margin-top: 0.5rem; }}
.content p {{ margin: 0.75rem 0; }}
.content a {{ color: var(--color-secondary); text-decoration: none; border-bottom: 1px dotted var(--color-secondary); }}
.content a:hover {{ border-bottom-style: solid; }}
.infobox {{ float: right; width: 260px; margin: 0 0 1rem 1rem; padding: 1rem; background: var(--color-background); border: 1px solid var(--color-secondary); }}
.see-also, .related {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--color-secondary); }}
.see-also ul, .related ul {{ list-style: none; padding: 0; }}
.see-also li, .related li {{ margin: 0.5rem 0; }}
.see-also a, .related a {{ color: var(--color-secondary); text-decoration: none; }}
"""
        (output_dir / "styles.css").write_text(css, encoding="utf-8")

    def _write_js(self, output_dir: Path) -> None:
        """app.js: infinite scroll / load more (fetches feed_page_N.json and appends)."""
        js = """// Infinite rabbit hole — load more feed pages
var feedPage = 2;
function loadMore() {
  var btn = document.querySelector('.load-more button');
  if (!btn || btn.getAttribute('data-loading') === 'true') return;
  btn.setAttribute('data-loading', 'true');
  btn.textContent = 'Loading...';
  fetch('feed_page_' + feedPage + '.json')
    .then(function(r) {
      if (!r.ok) throw new Error('No more');
      return r.json();
    })
    .then(function(items) {
      var feed = document.getElementById('feed');
      if (!feed) return;
      items.forEach(function(item) {
        var div = document.createElement('div');
        div.className = 'feed-item';
        var title = (item.title || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        var preview = (item.preview || item.body || '').substring(0, 200).replace(/</g, '&lt;').replace(/>/g, '&gt;');
        var hook = (item.read_more_hook || 'Read more').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        var link = (item.link || '#').replace(/"/g, '&quot;');
        div.innerHTML = '<h3><a href="' + link + '">' + title + '</a></h3><p class="preview">' + preview + '...</p><p class="hook"><a href="' + link + '">' + hook + '</a></p>';
        feed.appendChild(div);
      });
      feedPage++;
      btn.textContent = 'Load more';
      btn.removeAttribute('data-loading');
    })
    .catch(function() {
      if (btn) { btn.textContent = 'Load more'; btn.removeAttribute('data-loading'); }
      var wrap = document.querySelector('.load-more');
      if (wrap) wrap.style.display = 'none';
    });
}
document.querySelectorAll('.load-more button').forEach(function(btn) {
  btn.addEventListener('click', loadMore);
});
"""
        (output_dir / "app.js").write_text(js, encoding="utf-8")


def should_build_multipage(profile: PsychologicalProfile) -> bool:
    """Decide if this profile gets a multi-page infinite rabbit hole site."""
    style = getattr(profile, "browsing_style", "scanner")
    comm = getattr(profile, "communication_style", "")
    interests = getattr(profile, "specific_interests", []) or []
    return (
        style in ("doom_scroller", "deep_diver", "thread_reader")
        or comm == "analytical/precise"
        or len(interests) >= 4
    )
