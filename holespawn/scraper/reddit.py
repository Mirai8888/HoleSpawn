"""
Reddit scraper — public posts and comments via old.reddit.com JSON API.
No API key required.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "HoleSpawn/1.0 (cognitive profiling research)"}


async def scrape_reddit_user(username: str, max_items: int = 100) -> list[dict[str, Any]]:
    """
    Scrape a Reddit user's public posts and comments.
    Returns list of dicts with keys: text, type, subreddit, score, created_utc, url.
    """
    username = username.strip().lstrip("u/").lstrip("/")
    items = []

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        # Submitted posts
        try:
            r = await client.get(f"https://old.reddit.com/user/{username}/submitted.json?limit=100&sort=new")
            if r.status_code == 200:
                for child in r.json().get("data", {}).get("children", []):
                    d = child.get("data", {})
                    title = d.get("title", "")
                    selftext = d.get("selftext", "")
                    text = f"{title}. {selftext}".strip() if selftext else title
                    if text:
                        items.append({
                            "text": text,
                            "full_text": text,
                            "type": "post",
                            "subreddit": d.get("subreddit", ""),
                            "score": d.get("score", 0),
                            "created_utc": d.get("created_utc", 0),
                            "url": f"https://reddit.com{d.get('permalink', '')}",
                            "id": d.get("id", ""),
                        })
        except Exception as e:
            logger.warning("Reddit posts scrape failed for %s: %s", username, e)

        # Comments
        try:
            r = await client.get(f"https://old.reddit.com/user/{username}/comments.json?limit=100&sort=new")
            if r.status_code == 200:
                for child in r.json().get("data", {}).get("children", []):
                    d = child.get("data", {})
                    body = d.get("body", "")
                    if body and body not in ("[deleted]", "[removed]"):
                        items.append({
                            "text": body,
                            "full_text": body,
                            "type": "comment",
                            "subreddit": d.get("subreddit", ""),
                            "score": d.get("score", 0),
                            "created_utc": d.get("created_utc", 0),
                            "url": f"https://reddit.com{d.get('permalink', '')}",
                            "id": d.get("id", ""),
                        })
        except Exception as e:
            logger.warning("Reddit comments scrape failed for %s: %s", username, e)

    logger.info("Reddit u/%s: %d items scraped (%d posts, %d comments)",
                username, len(items),
                sum(1 for i in items if i["type"] == "post"),
                sum(1 for i in items if i["type"] == "comment"))
    return items[:max_items]
