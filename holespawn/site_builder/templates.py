"""
HTML layout templates for multi-page attention-trap sites.
Templates take aesthetic dict (colors, font) and content, return HTML.
"""

import html
from typing import Any


def _escape(s: str) -> str:
    return html.escape(str(s), quote=True) if s else ""


def _aesthetic_defaults(spec: Any) -> dict:
    """Build aesthetic dict from spec (and optional profile)."""
    return {
        "bg_color": getattr(spec, "color_background", "#ecf0f1"),
        "text_color": getattr(spec, "color_primary", "#2c3e50"),
        "link_color": getattr(spec, "color_secondary", "#3498db"),
        "accent_color": getattr(spec, "color_accent", "#e74c3c"),
        "border_color": getattr(spec, "color_secondary", "#3498db") + "40",
        "font": "system-ui, -apple-system, sans-serif",
        "box_bg": getattr(spec, "color_background", "#ecf0f1"),
    }


def infinite_scroll_feed(items: list[dict], spec: Any, title: str = "Feed") -> str:
    """Feed-style infinite scroll layout (doom scroller / attention trap)."""
    a = _aesthetic_defaults(spec)
    feed_items_html = []
    for i, item in enumerate(items):
        prev = _escape(item.get("preview", item.get("body", ""))[:200])
        link = _escape(item.get("link", f"entry_{i}.html"))
        tit = _escape(item.get("title", f"Entry {i + 1}"))
        hook = _escape(item.get("read_more_hook", "Read more"))
        feed_items_html.append(
            f'<div class="feed-item"><h3><a href="{link}">{tit}</a></h3>'
            f'<p class="preview">{prev}...</p>'
            f'<p class="hook"><a href="{link}">{hook}</a></p></div>'
        )
    feed_body = "\n".join(feed_items_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="layout-feed">
  <header class="site-header"><h1>{_escape(title)}</h1></header>
  <main class="feed" id="feed">{feed_body}</main>
  <div class="load-more"><button type="button" onclick="loadMore()">Load more</button></div>
  <script src="app.js"></script>
</body>
</html>"""


def wiki_article_page(
    title: str,
    main_content: str,
    see_also: list[dict],
    spec: Any,
    infobox: str = "",
) -> str:
    """Wikipedia-style article with heavy hyperlinking (deep diver)."""
    a = _aesthetic_defaults(spec)
    see_also_ul = "".join(
        f'<li><a href="{_escape(l.get("href", "#"))}">{_escape(l.get("title", ""))}</a></li>'
        for l in see_also[:8]
    )
    infobox_block = f'<div class="infobox">{infobox}</div>' if infobox else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="layout-wiki">
  <header class="site-header"><h1>{_escape(title)}</h1></header>
  <article>
    {infobox_block}
    <div class="content">{main_content}</div>
    <nav class="see-also"><h3>See also</h3><ul>{see_also_ul}</ul></nav>
  </article>
  <script src="app.js"></script>
</body>
</html>"""


def hub_spoke_page(
    title: str,
    tagline: str,
    cards: list[dict],
    spec: Any,
) -> str:
    """Central hub with topic cards (scanner)."""
    a = _aesthetic_defaults(spec)
    cards_html = []
    for c in cards:
        href = _escape(c.get("href", c.get("id", "#") + ".html"))
        tit = _escape(c.get("title", c.get("id", "")))
        desc = _escape(c.get("description", ""))[:120]
        cards_html.append(
            f'<a class="hub-card" href="{href}"><h3>{tit}</h3><p>{desc}</p></a>'
        )
    cards_body = "\n".join(cards_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="layout-hub">
  <header class="site-header">
    <h1>{_escape(title)}</h1>
    <p class="tagline">{_escape(tagline)}</p>
  </header>
  <main class="hub-grid">{cards_body}</main>
  <script src="app.js"></script>
</body>
</html>"""


def entry_article_page(
    title: str,
    body: str,
    back_link: str,
    spec: Any,
    related_links: list[dict] | None = None,
) -> str:
    """Single entry/article page (linked from feed or hub). Optional Related section for rabbit-hole links."""
    a = _aesthetic_defaults(spec)
    body_html = body if body.strip().startswith("<") else f"<p>{_escape(body)}</p>"
    related = related_links or []
    related_html = ""
    if related:
        rel_items = "".join(
            f'<li><a href="{_escape(l.get("href", "#"))}">{_escape(l.get("title", ""))}</a></li>'
            for l in related[:6]
        )
        related_html = f'<nav class="related"><h3>Related</h3><ul>{rel_items}</ul></nav>'
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
  <article><h1>{_escape(title)}</h1><div class="content">{body_html}</div></article>
  {related_html}
  <script src="app.js"></script>
</body>
</html>"""


def topic_page(
    title: str,
    body: str,
    related_links: list[dict],
    spec: Any,
    back_href: str = "index.html",
) -> str:
    """Topic page (wiki or hub spoke) with related links."""
    rel_html = "".join(
        f'<li><a href="{_escape(l.get("href", "#"))}">{_escape(l.get("title", ""))}</a></li>'
        for l in related_links[:6]
    )
    body_html = body if body.strip().startswith("<") else f"<p>{_escape(body)}</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body class="layout-topic">
  <nav class="back"><a href="{_escape(back_href)}">← Back to hub</a></nav>
  <article><h1>{_escape(title)}</h1><div class="content">{body_html}</div></article>
  <nav class="related"><h3>Related</h3><ul>{rel_html}</ul></nav>
  <script src="app.js"></script>
</body>
</html>"""
