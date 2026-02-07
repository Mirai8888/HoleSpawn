"""
Render content graph to HTML files with profile-matched aesthetic.
No rigid templates — page structure follows graph type (feed, hub, article).
"""

import html
import json
import re
from pathlib import Path
from typing import Any, Optional

from holespawn.experience import ExperienceSpec
from holespawn.profile import PsychologicalProfile

from .pure_generator import generate_design_system


def _escape(s: str) -> str:
    return html.escape(str(s), quote=True) if s else ""


def _render_feed_index(data: dict, spec: Any) -> str:
    """Render feed-style index (list of items with links)."""
    title = _escape(data.get("title", "Feed"))
    items = data.get("items", [])
    items_html = []
    for i, it in enumerate(items):
        tit = _escape(it.get("title", f"Item {i + 1}"))
        prev = _escape((it.get("preview", it.get("body", ""))[:200]))
        link = _escape(it.get("link", f"post_{i}.html"))
        hook = _escape(it.get("read_more_hook", "Read more"))
        items_html.append(
            f'<div class="feed-item"><h3><a href="{link}">{tit}</a></h3>'
            f'<p class="preview">{prev}...</p>'
            f'<p class="hook"><a href="{link}">{hook}</a></p></div>'
        )
    body = "\n".join(items_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="layout-feed">
  <header class="site-header"><h1>{title}</h1></header>
  <main class="feed" id="feed">{body}</main>
  <div class="load-more"><button type="button" onclick="loadMore()">Load more</button></div>
  <script src="app.js"></script>
</body>
</html>"""


def _render_hub_index(data: dict, spec: Any) -> str:
    """Render hub-style index (cards linking to topic pages)."""
    title = _escape(data.get("title", "Hub"))
    tagline = _escape(data.get("tagline", ""))
    cards = data.get("cards", [])
    cards_html = []
    for c in cards:
        href = _escape(c.get("href", c.get("id", "#") + ".html"))
        tit = _escape(c.get("title", c.get("id", "")))
        desc = _escape(c.get("description", ""))[:120]
        cards_html.append(f'<a class="hub-card" href="{href}"><h3>{tit}</h3><p>{desc}</p></a>')
    cards_body = "\n".join(cards_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="layout-hub">
  <header class="site-header">
    <h1>{title}</h1>
    <p class="tagline">{tagline}</p>
  </header>
  <main class="hub-grid">{cards_body}</main>
  <script src="app.js"></script>
</body>
</html>"""


def _render_article_page(
    title: str,
    content: str,
    back_link: str,
    see_also: list[dict],
    spec: Any,
) -> str:
    """Render single article page (content = HTML with <a>; optional see_also)."""
    content_html = content if content.strip().startswith("<") else f"<p>{_escape(content)}</p>"
    rel_html = ""
    if see_also:
        rel_items = "".join(
            f'<li><a href="{_escape(l.get("href", "#"))}">{_escape(l.get("title", ""))}</a></li>'
            for l in see_also[:8]
        )
        rel_html = f'<nav class="see-also"><h3>See also</h3><ul>{rel_items}</ul></nav>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="layout-article">
  <nav class="back"><a href="{_escape(back_link)}">← Back</a></nav>
  <article>
    <h1>{_escape(title)}</h1>
    <div class="content">{content_html}</div>
    {rel_html}
  </article>
  <script src="app.js"></script>
</body>
</html>"""


def render_pages(
    content_graph: dict[str, dict[str, Any]],
    output_dir: Path,
    profile: PsychologicalProfile,
    spec: ExperienceSpec,
) -> None:
    """
    Write all HTML pages, styles.css, and app.js from content_graph.
    content_graph: dict page_key -> {type, title, content?, items?, cards?, see_also?, back_link?}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Index
    index_data = content_graph.get("index", {})
    index_type = index_data.get("type", "hub")
    if index_type == "feed":
        html_str = _render_feed_index(index_data, spec)
    else:
        html_str = _render_hub_index(index_data, spec)
    (output_dir / "index.html").write_text(html_str, encoding="utf-8")

    # Other pages
    for key, data in content_graph.items():
        if key == "index":
            continue
        page_type = data.get("type", "article")
        title = data.get("title", key)
        content = data.get("content", data.get("body", ""))
        back = data.get("back_link", "index.html")
        see_also = data.get("see_also", [])
        page_html = _render_article_page(title, content, back, see_also, spec)
        filename = f"{key}.html" if not key.endswith(".html") else key
        (output_dir / filename).write_text(page_html, encoding="utf-8")

    # Shared CSS (AI design system — psychological capture from profile + spec)
    css = generate_design_system(profile, spec)
    (output_dir / "styles.css").write_text(css, encoding="utf-8")

    # Shared JS (load more for feed)
    js = """// Dynamic site — load more (if feed_page_N.json exists)
var feedPage = 2;
function loadMore() {
  var btn = document.querySelector('.load-more button');
  if (!btn || btn.getAttribute('data-loading') === 'true') return;
  btn.setAttribute('data-loading', 'true');
  btn.textContent = 'Loading...';
  fetch('feed_page_' + feedPage + '.json')
    .then(function(r) { if (!r.ok) throw new Error('No more'); return r.json(); })
    .then(function(items) {
      var feed = document.getElementById('feed');
      if (!feed) return;
      items.forEach(function(item) {
        var div = document.createElement('div');
        div.className = 'feed-item';
        var title = (item.title || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        var preview = (item.preview || '').substring(0, 200).replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
document.querySelectorAll('.load-more button').forEach(function(btn) { btn.addEventListener('click', loadMore); });
"""
    (output_dir / "app.js").write_text(js, encoding="utf-8")
