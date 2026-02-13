"""
Substack scraper — publication posts via public API.
No API key required.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def scrape_substack(publication: str, max_items: int = 30) -> list[dict[str, Any]]:
    """
    Scrape a Substack publication's posts.
    Publication can be: 'handle', 'handle.substack.com', or full URL.
    Returns list of dicts with keys: text, title, subtitle, url, created_at, likes.
    """
    # Normalize publication name
    pub = publication.strip()
    pub = pub.replace("https://", "").replace("http://", "")
    pub = pub.replace(".substack.com", "").rstrip("/")
    if "/" in pub:
        pub = pub.split("/")[0]

    items = []

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        try:
            r = await client.get(f"https://{pub}.substack.com/api/v1/posts?limit={max_items}")
            if r.status_code == 200:
                for post in r.json():
                    title = post.get("title", "")
                    subtitle = post.get("subtitle", "")
                    body = post.get("truncated_body_text", "") or post.get("description", "")
                    text = f"{title}. {subtitle}. {body}".strip()
                    if text:
                        items.append({
                            "text": text[:1000],
                            "full_text": text,
                            "title": title,
                            "subtitle": subtitle,
                            "type": "article",
                            "url": post.get("canonical_url", ""),
                            "created_at": post.get("post_date", ""),
                            "likes": post.get("reactions", {}).get("❤", 0) if isinstance(post.get("reactions"), dict) else 0,
                        })
        except Exception as e:
            logger.warning("Substack scrape failed for %s: %s", pub, e)

    logger.info("Substack %s: %d items scraped", pub, len(items))
    return items[:max_items]
