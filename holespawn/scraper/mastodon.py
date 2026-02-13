"""
Mastodon/Fediverse scraper — public toots via ActivityPub API.
No API key required for public content.
"""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def scrape_mastodon_user(
    handle: str, max_items: int = 80
) -> list[dict[str, Any]]:
    """
    Scrape a Mastodon user's public posts.
    Handle format: user@instance.social or just username (defaults to mastodon.social).
    Returns list of dicts with keys: text, type, url, created_at, reblogs_count, favourites_count.
    """
    items = []

    # Parse handle
    handle = handle.strip().lstrip("@")
    if "@" in handle:
        parts = handle.split("@")
        username = parts[0]
        instance = parts[1] if len(parts) > 1 else "mastodon.social"
    else:
        username = handle
        instance = "mastodon.social"

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        try:
            # Look up account ID
            r = await client.get(f"https://{instance}/api/v1/accounts/lookup?acct={username}")
            if r.status_code != 200:
                logger.warning("Mastodon lookup failed for %s@%s: %d", username, instance, r.status_code)
                return items
            account_id = r.json().get("id")

            # Fetch statuses (paginate)
            url = f"https://{instance}/api/v1/accounts/{account_id}/statuses?limit=40&exclude_replies=false"
            for _ in range(2):  # 2 pages max
                r = await client.get(url)
                if r.status_code != 200:
                    break
                statuses = r.json()
                if not statuses:
                    break

                for status in statuses:
                    content = status.get("content", "")
                    # Strip HTML
                    text = re.sub(r"<[^>]+>", " ", content).strip()
                    text = re.sub(r"\s+", " ", text)
                    if text and len(text) > 5:
                        items.append({
                            "text": text,
                            "full_text": text,
                            "type": "reblog" if status.get("reblog") else "toot",
                            "url": status.get("url", ""),
                            "created_at": status.get("created_at", ""),
                            "reblogs_count": status.get("reblogs_count", 0),
                            "favourites_count": status.get("favourites_count", 0),
                        })

                # Pagination via Link header
                link = r.headers.get("link", "")
                next_match = re.search(r'<([^>]+)>;\s*rel="next"', link)
                if next_match:
                    url = next_match.group(1)
                else:
                    break

        except Exception as e:
            logger.warning("Mastodon scrape failed for %s@%s: %s", username, instance, e)

    logger.info("Mastodon @%s@%s: %d items scraped", username, instance, len(items))
    return items[:max_items]
