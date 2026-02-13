"""
Hacker News scraper — submissions and comments via Algolia API.
No API key required.
"""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def scrape_hn_user(username: str, max_items: int = 50) -> list[dict[str, Any]]:
    """
    Scrape a HN user's public submissions and comments.
    Returns list of dicts with keys: text, type, score, url, created_at.
    """
    username = username.strip()
    items = []

    async with httpx.AsyncClient(timeout=15) as client:
        # Stories
        try:
            r = await client.get(
                f"https://hn.algolia.com/api/v1/search?tags=author_{username},story&hitsPerPage=30"
            )
            if r.status_code == 200:
                for hit in r.json().get("hits", []):
                    title = hit.get("title", "")
                    if title:
                        items.append({
                            "text": title,
                            "full_text": title,
                            "type": "story",
                            "score": hit.get("points", 0),
                            "url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                            "created_at": hit.get("created_at", ""),
                        })
        except Exception as e:
            logger.warning("HN stories failed for %s: %s", username, e)

        # Comments
        try:
            r = await client.get(
                f"https://hn.algolia.com/api/v1/search?tags=author_{username},comment&hitsPerPage=50"
            )
            if r.status_code == 200:
                for hit in r.json().get("hits", []):
                    text = hit.get("comment_text", "")
                    if text:
                        clean = re.sub(r"<[^>]+>", " ", text).strip()
                        clean = re.sub(r"\s+", " ", clean)
                        if clean and len(clean) > 10:
                            items.append({
                                "text": clean[:500],
                                "full_text": clean,
                                "type": "comment",
                                "score": hit.get("points", 0),
                                "url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                                "created_at": hit.get("created_at", ""),
                            })
        except Exception as e:
            logger.warning("HN comments failed for %s: %s", username, e)

    logger.info("HN %s: %d items scraped", username, len(items))
    return items[:max_items]
