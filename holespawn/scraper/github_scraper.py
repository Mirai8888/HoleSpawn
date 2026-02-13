"""
GitHub scraper — repo descriptions, issue comments, commit messages, README excerpts.
No API key required (rate-limited to 60 req/hr unauthenticated).
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "HoleSpawn/1.0",
}


async def scrape_github_user(username: str, max_items: int = 50, token: str = None) -> list[dict[str, Any]]:
    """
    Scrape a GitHub user's public activity.
    Returns list of dicts with keys: text, type, repo, url, created_at.
    Optionally pass a PAT for higher rate limits.
    """
    username = username.strip().lstrip("@")
    items = []
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(headers=headers, timeout=15) as client:
        # Repos — descriptions
        try:
            r = await client.get(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=30")
            if r.status_code == 200:
                for repo in r.json():
                    desc = repo.get("description", "")
                    name = repo.get("name", "")
                    if desc:
                        items.append({
                            "text": f"{name}: {desc}",
                            "full_text": f"{name}: {desc}",
                            "type": "repo_description",
                            "repo": repo.get("full_name", ""),
                            "url": repo.get("html_url", ""),
                            "created_at": repo.get("updated_at", ""),
                        })
        except Exception as e:
            logger.warning("GitHub repos failed for %s: %s", username, e)

        # Public events — issue comments, PR comments, commit messages
        try:
            r = await client.get(f"https://api.github.com/users/{username}/events/public?per_page=50")
            if r.status_code == 200:
                for event in r.json():
                    payload = event.get("payload", {})
                    repo_name = event.get("repo", {}).get("name", "")
                    created = event.get("created_at", "")

                    # Issue/PR comments
                    comment = payload.get("comment", {})
                    if comment.get("body"):
                        items.append({
                            "text": comment["body"][:500],
                            "full_text": comment["body"],
                            "type": "comment",
                            "repo": repo_name,
                            "url": comment.get("html_url", ""),
                            "created_at": created,
                        })

                    # Issue bodies
                    issue = payload.get("issue", {})
                    if issue.get("body") and event.get("type") == "IssuesEvent":
                        items.append({
                            "text": issue["body"][:500],
                            "full_text": issue["body"],
                            "type": "issue",
                            "repo": repo_name,
                            "url": issue.get("html_url", ""),
                            "created_at": created,
                        })

                    # Commit messages
                    for commit in payload.get("commits", []):
                        msg = commit.get("message", "")
                        if msg and len(msg) > 10:
                            items.append({
                                "text": msg[:300],
                                "full_text": msg,
                                "type": "commit",
                                "repo": repo_name,
                                "url": "",
                                "created_at": created,
                            })
        except Exception as e:
            logger.warning("GitHub events failed for %s: %s", username, e)

    logger.info("GitHub @%s: %d items scraped", username, len(items))
    return items[:max_items]
