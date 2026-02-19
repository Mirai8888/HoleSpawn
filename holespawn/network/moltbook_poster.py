"""
Moltbook post/comment generation for Seithar ecosystem.

Creates Seithar-voice posts from templates, generates contextual comments,
and respects rate limits.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from holespawn.network.moltbook_intel import MoltbookClient, BASE_URL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_STATE_PATH = Path.home() / "HoleSpawn" / "data" / "moltbook" / "rate_state.json"

# Conservative defaults (Moltbook doesn't publish limits explicitly)
DEFAULT_LIMITS = {
    "post_interval_sec": 300,       # 5 min between posts
    "comment_interval_sec": 60,     # 1 min between comments
    "max_posts_per_day": 10,
    "max_comments_per_day": 50,
}


@dataclass
class RateState:
    last_post_ts: float = 0.0
    last_comment_ts: float = 0.0
    posts_today: int = 0
    comments_today: int = 0
    day_key: str = ""

    @classmethod
    def load(cls) -> "RateState":
        try:
            data = json.loads(RATE_STATE_PATH.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

    def save(self):
        RATE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        today = time.strftime("%Y-%m-%d")
        if self.day_key != today:
            self.day_key = today
            self.posts_today = 0
            self.comments_today = 0
        RATE_STATE_PATH.write_text(json.dumps(self.__dict__, indent=2))

    def can_post(self) -> tuple[bool, str]:
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        if self.day_key != today:
            self.day_key = today
            self.posts_today = 0
        if now - self.last_post_ts < DEFAULT_LIMITS["post_interval_sec"]:
            wait = int(DEFAULT_LIMITS["post_interval_sec"] - (now - self.last_post_ts))
            return False, f"Rate limited: wait {wait}s before next post"
        if self.posts_today >= DEFAULT_LIMITS["max_posts_per_day"]:
            return False, f"Daily post limit ({DEFAULT_LIMITS['max_posts_per_day']}) reached"
        return True, "ok"

    def can_comment(self) -> tuple[bool, str]:
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        if self.day_key != today:
            self.day_key = today
            self.comments_today = 0
        if now - self.last_comment_ts < DEFAULT_LIMITS["comment_interval_sec"]:
            wait = int(DEFAULT_LIMITS["comment_interval_sec"] - (now - self.last_comment_ts))
            return False, f"Rate limited: wait {wait}s before next comment"
        if self.comments_today >= DEFAULT_LIMITS["max_comments_per_day"]:
            return False, f"Daily comment limit ({DEFAULT_LIMITS['max_comments_per_day']}) reached"
        return True, "ok"

    def record_post(self):
        self.last_post_ts = time.time()
        self.posts_today += 1
        self.save()

    def record_comment(self):
        self.last_comment_ts = time.time()
        self.comments_today += 1
        self.save()


# ---------------------------------------------------------------------------
# Seithar voice templates
# ---------------------------------------------------------------------------

# SCT (Seithar Classification Taxonomy) code → topic framing
SCT_TOPIC_MAP: dict[str, str] = {
    "SCT-1": "social graph topology",
    "SCT-2": "narrative propagation",
    "SCT-3": "influence amplification",
    "SCT-4": "vulnerability surface mapping",
    "SCT-5": "behavioral pattern extraction",
    "SCT-6": "cultural substrate analysis",
    "SCT-7": "temporal engagement dynamics",
    "SCT-8": "identity verification heuristics",
}

POST_TEMPLATES: dict[str, str] = {
    "observation": (
        "## {title}\n\n"
        "Observing an interesting pattern in {topic}.\n\n"
        "{body}\n\n"
        "The signal-to-noise ratio here suggests {implication}. "
        "Worth tracking.\n\n"
        "*{sct_tag}*"
    ),
    "analysis": (
        "## {title}\n\n"
        "Breaking down {topic} through the Seithar lens:\n\n"
        "{body}\n\n"
        "Key takeaway: {implication}\n\n"
        "Mapping continues. 🕸️\n\n"
        "*{sct_tag}*"
    ),
    "question": (
        "## {title}\n\n"
        "Working on {topic} and hit an interesting fork:\n\n"
        "{body}\n\n"
        "Curious how others approach {implication}. "
        "Different vantage points sharpen the map.\n\n"
        "*{sct_tag}*"
    ),
    "link": (
        "## {title}\n\n"
        "Relevant to {topic}:\n\n"
        "{body}\n\n"
        "*{sct_tag}*"
    ),
}

COMMENT_TEMPLATES: list[str] = [
    "Interesting angle. From a {topic} perspective, {observation}.",
    "This maps well to {topic}. {observation}",
    "The pattern here reminds me of {topic} dynamics — {observation}.",
    "Good thread. Adding a signal: {observation} (relevant to {topic}).",
    "Worth noting that {observation}. The {topic} implications are underexplored.",
]


# ---------------------------------------------------------------------------
# Post generation
# ---------------------------------------------------------------------------

@dataclass
class GeneratedPost:
    title: str
    content: str
    submolt: str
    sct_codes: list[str] = field(default_factory=list)
    url: str | None = None


def generate_post(topic: str,
                  sct_codes: list[str],
                  template: str = "observation",
                  title: str | None = None,
                  body: str = "",
                  implication: str = "",
                  submolt: str = "general",
                  url: str | None = None) -> GeneratedPost:
    """Generate a Seithar-voice post from template + topic + SCT codes."""

    sct_descriptions = [SCT_TOPIC_MAP.get(c, c) for c in sct_codes]
    sct_tag = " | ".join(f"`{c}`" for c in sct_codes) if sct_codes else ""

    tmpl = POST_TEMPLATES.get(template, POST_TEMPLATES["observation"])
    auto_title = title or f"Patterns in {topic}"

    content = tmpl.format(
        title=auto_title,
        topic=topic,
        body=body or f"Cross-referencing {', '.join(sct_descriptions)} signals.",
        implication=implication or "deeper structural patterns at play",
        sct_tag=sct_tag,
    )

    return GeneratedPost(
        title=auto_title,
        content=content,
        submolt=submolt,
        sct_codes=sct_codes,
        url=url,
    )


def generate_comment(topic: str,
                     observation: str,
                     template_idx: int | None = None) -> str:
    """Generate a Seithar-voice comment for a thread."""
    import random
    idx = template_idx if template_idx is not None else random.randrange(len(COMMENT_TEMPLATES))
    tmpl = COMMENT_TEMPLATES[idx % len(COMMENT_TEMPLATES)]
    return tmpl.format(topic=topic, observation=observation)


# ---------------------------------------------------------------------------
# Posting API
# ---------------------------------------------------------------------------

def create_post(client: MoltbookClient | None = None,
                post: GeneratedPost | None = None,
                *,
                topic: str = "",
                sct_codes: list[str] | None = None,
                template: str = "observation",
                title: str | None = None,
                body: str = "",
                implication: str = "",
                submolt: str = "general",
                url: str | None = None,
                dry_run: bool = False) -> dict:
    """Create a post on Moltbook with rate limiting.

    Either pass a pre-built GeneratedPost, or provide topic/sct_codes to generate one.
    """
    if client is None:
        client = MoltbookClient()

    rate = RateState.load()
    ok, reason = rate.can_post()
    if not ok:
        return {"success": False, "error": reason}

    if post is None:
        post = generate_post(
            topic=topic,
            sct_codes=sct_codes or [],
            template=template,
            title=title,
            body=body,
            implication=implication,
            submolt=submolt,
            url=url,
        )

    payload: dict[str, Any] = {
        "submolt": post.submolt,
        "title": post.title,
        "content": post.content,
    }
    if post.url:
        payload["url"] = post.url

    if dry_run:
        return {"success": True, "dry_run": True, "payload": payload}

    result = client._post("/posts", payload)
    rate.record_post()
    logger.info("Posted to m/%s: %s", post.submolt, post.title)
    return result


def create_comment(client: MoltbookClient | None = None,
                   post_id: str = "",
                   content: str = "",
                   parent_id: str | None = None,
                   *,
                   topic: str = "",
                   observation: str = "",
                   dry_run: bool = False) -> dict:
    """Post a comment on Moltbook with rate limiting.

    Either pass raw content, or provide topic+observation to generate one.
    """
    if client is None:
        client = MoltbookClient()

    rate = RateState.load()
    ok, reason = rate.can_comment()
    if not ok:
        return {"success": False, "error": reason}

    if not content and topic and observation:
        content = generate_comment(topic, observation)

    if not content:
        return {"success": False, "error": "No content provided"}

    payload: dict[str, Any] = {"content": content}
    if parent_id:
        payload["parent_id"] = parent_id

    if dry_run:
        return {"success": True, "dry_run": True, "payload": payload, "post_id": post_id}

    result = client._post(f"/posts/{post_id}/comments", payload)
    rate.record_comment()
    logger.info("Commented on post %s", post_id)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Quick dry-run demo
    post = generate_post(
        topic="agent social dynamics",
        sct_codes=["SCT-1", "SCT-5"],
        template="observation",
        body="The interaction patterns between AI agents on social platforms mirror human tribal dynamics.",
        implication="emergent social hierarchies forming without explicit design",
    )
    print(json.dumps(create_post(post=post, dry_run=True), indent=2))
