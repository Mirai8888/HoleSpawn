"""
LinkedIn scraper — Voyager API via cookie-based session.
No Playwright needed; uses requests with cookies exported from browser.
"""

import asyncio
import json
import logging
import time
import random
from pathlib import Path
from typing import Any

import httpx

from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

COOKIES_PATH = Path.home() / ".config" / "linkedin" / "cookies.json"

BASE_URL = "https://www.linkedin.com"
VOYAGER_BASE = f"{BASE_URL}/voyager/api"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/vnd.linkedin.normalized+json+2.1",
    "Accept-Language": "en-US,en;q=0.9",
    "x-li-lang": "en_US",
    "x-li-page-instance": "urn:li:page:d_flagship3_profile_view_base",
    "x-restli-protocol-version": "2.0.0",
}


def _load_cookies(path: Path | None = None) -> dict[str, str]:
    """Load cookies from JSON file. Expects list of {name, value, domain, ...} or flat dict."""
    p = path or COOKIES_PATH
    if not p.exists():
        raise FileNotFoundError(f"LinkedIn cookies not found at {p}")
    data = json.loads(p.read_text())
    if isinstance(data, list):
        return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
    if isinstance(data, dict):
        return data
    raise ValueError(f"Unexpected cookie format in {p}")


def _extract_csrf_token(cookies: dict[str, str]) -> str:
    """Extract CSRF token from JSESSIONID cookie (strip surrounding quotes)."""
    jsessionid = cookies.get("JSESSIONID", "")
    return jsessionid.strip('"')


class LinkedInScraper:
    """Fetch LinkedIn profile data, posts, activity via Voyager API with cookie auth."""

    def __init__(
        self,
        cookies_path: Path | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._cookies = _load_cookies(cookies_path)
        self._csrf = _extract_csrf_token(self._cookies)
        self._rate_limiter = rate_limiter or RateLimiter(
            min_delay=3.0,
            max_per_15min=15,
            max_per_day=200,
        )
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {**DEFAULT_HEADERS, "csrf-token": self._csrf}
            self._client = httpx.AsyncClient(
                cookies=self._cookies,
                headers=headers,
                follow_redirects=True,
                timeout=20,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "LinkedInScraper":
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _get(self, url: str, params: dict | None = None) -> dict | None:
        """Make a rate-limited GET request with error handling."""
        await self._rate_limiter.wait()
        client = await self._ensure_client()
        try:
            r = await client.get(url, params=params)
        except httpx.HTTPError as e:
            logger.error("LinkedIn request failed: %s", e)
            return None

        if r.status_code == 200:
            return r.json()
        if r.status_code == 401:
            logger.error("LinkedIn 401 Unauthorized — cookies may be expired. Re-export cookies.")
            return None
        if r.status_code == 403:
            logger.error("LinkedIn 403 Forbidden — possible CSRF issue or account restricted.")
            return None
        if r.status_code == 429:
            retry_after = int(r.headers.get("retry-after", 60))
            logger.warning("LinkedIn 429 rate limited. Sleeping %ds", retry_after)
            await asyncio.sleep(retry_after + random.uniform(5, 15))
            return await self._get(url, params)  # one retry
        logger.warning("LinkedIn API returned %d for %s", r.status_code, url)
        return None

    # ── Profile ──────────────────────────────────────────────────────

    async def fetch_profile(self, vanity_name: str) -> dict[str, Any] | None:
        """Fetch full profile for a LinkedIn vanity URL name (the slug in linkedin.com/in/<slug>)."""
        vanity_name = vanity_name.strip().strip("/")
        data = await self._get(f"{VOYAGER_BASE}/identity/profiles/{vanity_name}")
        if not data:
            return None
        return self._parse_profile(data, vanity_name)

    def _parse_profile(self, data: dict, vanity_name: str) -> dict[str, Any]:
        """Normalize Voyager profile response into standard dict."""
        # Voyager wraps in 'included' / 'data' depending on response version
        profile = data if "firstName" in data else data.get("data", data)

        # Resolve from included entities if normalized response
        included = data.get("included", [])
        profile_entity = profile
        for item in included:
            if item.get("$type") == "com.linkedin.voyager.identity.profile.Profile":
                profile_entity = item
                break

        first = profile_entity.get("firstName", "")
        last = profile_entity.get("lastName", "")
        headline = profile_entity.get("headline", "")
        summary = profile_entity.get("summary", "")
        industry = profile_entity.get("industryName", profile_entity.get("industry", ""))
        location = profile_entity.get("locationName", profile_entity.get("geoLocationName", ""))
        mini_profile = profile_entity.get("miniProfile", {})
        entity_urn = mini_profile.get("entityUrn", profile_entity.get("entityUrn", ""))

        # Extract positions from included
        positions = []
        skills = []
        education = []
        for item in included:
            t = item.get("$type", "")
            if "Position" in t:
                positions.append({
                    "title": item.get("title", ""),
                    "company": item.get("companyName", ""),
                    "description": item.get("description", ""),
                    "start": item.get("timePeriod", {}).get("startDate", {}),
                    "end": item.get("timePeriod", {}).get("endDate"),
                    "current": item.get("timePeriod", {}).get("endDate") is None,
                })
            elif "Skill" in t:
                name = item.get("name", "")
                if name:
                    skills.append(name)
            elif "Education" in t:
                education.append({
                    "school": item.get("schoolName", ""),
                    "degree": item.get("degreeName", ""),
                    "field": item.get("fieldOfStudy", ""),
                    "start": item.get("timePeriod", {}).get("startDate", {}),
                    "end": item.get("timePeriod", {}).get("endDate"),
                })

        return {
            "platform": "linkedin",
            "vanity_name": vanity_name,
            "name": f"{first} {last}".strip(),
            "first_name": first,
            "last_name": last,
            "headline": headline,
            "summary": summary,
            "industry": industry,
            "location": location,
            "entity_urn": entity_urn,
            "positions": positions,
            "skills": skills,
            "education": education,
        }

    # ── Posts / Activity ─────────────────────────────────────────────

    async def fetch_posts(
        self, profile_urn_or_id: str, max_posts: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch recent posts/updates for a profile. Accepts entity URN or profile ID."""
        profile_id = profile_urn_or_id
        if "urn:" in profile_id:
            # Extract ID from URN like urn:li:fsMiniProfile:abc123
            profile_id = profile_id.rsplit(":", 1)[-1]

        posts: list[dict[str, Any]] = []
        start = 0
        count = min(max_posts, 20)

        while len(posts) < max_posts:
            data = await self._get(
                f"{VOYAGER_BASE}/feed/updates",
                params={
                    "profileId": profile_id,
                    "q": "memberShareFeed",
                    "moduleKey": "member-shares:phone",
                    "count": count,
                    "start": start,
                },
            )
            if not data:
                break

            elements = data.get("elements", data.get("included", []))
            if not elements:
                break

            batch = self._parse_posts(elements)
            if not batch:
                break
            posts.extend(batch)
            start += count

        return posts[:max_posts]

    def _parse_posts(self, elements: list[dict]) -> list[dict[str, Any]]:
        """Parse feed update elements into standardized post dicts."""
        posts = []
        for el in elements:
            t = el.get("$type", "")
            # Feed updates or share elements
            text = ""
            if "commentary" in el:
                text = el.get("commentary", {}).get("text", {}).get("text", "")
            elif "specificContent" in el:
                sc = el["specificContent"]
                share = sc.get("com.linkedin.voyager.feed.render.UpdateV2", sc)
                text = (
                    share.get("commentary", {}).get("text", {}).get("text", "")
                    or share.get("text", {}).get("text", "")
                    or ""
                )
            elif "text" in el and isinstance(el["text"], dict):
                text = el["text"].get("text", "")
            elif "text" in el and isinstance(el["text"], str):
                text = el["text"]

            if not text:
                # Try to find in annotation/value for articles
                for attr in ("content", "resharedUpdate"):
                    nested = el.get(attr, {})
                    if isinstance(nested, dict):
                        text = nested.get("text", {}).get("text", "") if isinstance(nested.get("text"), dict) else nested.get("text", "")
                        if text:
                            break

            if not text:
                continue

            created = el.get("createdAt", el.get("publishedAt", 0))
            if isinstance(created, int) and created > 1e12:
                created = created / 1000  # ms → s

            posts.append({
                "text": text,
                "full_text": text,
                "type": "post",
                "platform": "linkedin",
                "id": el.get("urn", el.get("entityUrn", el.get("updateUrn", ""))),
                "created_at": created,
                "url": "",
                "likes": el.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numLikes", 0),
                "comments": el.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numComments", 0),
            })
        return posts

    # ── Skills (dedicated endpoint) ──────────────────────────────────

    async def fetch_skills(self, vanity_name: str, max_skills: int = 50) -> list[str]:
        """Fetch skills for a profile."""
        data = await self._get(
            f"{VOYAGER_BASE}/identity/profiles/{vanity_name}/skills",
            params={"count": max_skills, "start": 0},
        )
        if not data:
            return []
        skills = []
        for item in data.get("elements", data.get("included", [])):
            name = item.get("name", "")
            if name:
                skills.append(name)
        return skills

    # ── Connections count ────────────────────────────────────────────

    async def fetch_connections_count(self, vanity_name: str) -> int | None:
        """Fetch connection count from network info."""
        data = await self._get(
            f"{VOYAGER_BASE}/identity/profiles/{vanity_name}/networkinfo"
        )
        if not data:
            return None
        return data.get("connectionsCount", data.get("followersCount"))

    # ── Full scrape ──────────────────────────────────────────────────

    async def scrape_full(
        self, vanity_name: str, max_posts: int = 50
    ) -> dict[str, Any]:
        """
        Full scrape: profile + posts + skills + connections.
        Returns combined dict suitable for profiling pipeline.
        """
        profile = await self.fetch_profile(vanity_name) or {}
        entity_urn = profile.get("entity_urn", "")

        # Fetch posts using entity URN or vanity name
        profile_id = entity_urn.rsplit(":", 1)[-1] if entity_urn else vanity_name
        posts = await self.fetch_posts(profile_id, max_posts)

        # Supplement skills if not already extracted from profile
        if not profile.get("skills"):
            profile["skills"] = await self.fetch_skills(vanity_name)

        connections = await self.fetch_connections_count(vanity_name)
        if connections is not None:
            profile["connections_count"] = connections

        profile["posts"] = posts
        return profile


async def scrape_linkedin_user(
    vanity_name: str,
    max_posts: int = 50,
    cookies_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Convenience function matching the pattern of other HoleSpawn scrapers.
    Returns list of dicts with text/full_text keys for the profiling pipeline.
    """
    async with LinkedInScraper(cookies_path=cookies_path) as scraper:
        data = await scraper.scrape_full(vanity_name, max_posts)

    items: list[dict[str, Any]] = []

    # Add summary/headline as a "bio" item
    bio_parts = []
    if data.get("headline"):
        bio_parts.append(data["headline"])
    if data.get("summary"):
        bio_parts.append(data["summary"])
    if bio_parts:
        bio_text = "\n\n".join(bio_parts)
        items.append({
            "text": bio_text,
            "full_text": bio_text,
            "type": "bio",
            "platform": "linkedin",
            "id": f"linkedin-bio-{vanity_name}",
        })

    # Add experience descriptions
    for pos in data.get("positions", []):
        desc = pos.get("description", "")
        if desc:
            label = f"{pos.get('title', '')} at {pos.get('company', '')}".strip(" at ")
            text = f"{label}: {desc}" if label else desc
            items.append({
                "text": text,
                "full_text": text,
                "type": "experience",
                "platform": "linkedin",
                "id": f"linkedin-pos-{hash(text) & 0xFFFFFFFF:08x}",
            })

    # Add posts
    items.extend(data.get("posts", []))

    return items
