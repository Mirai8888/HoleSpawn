"""
Load social media content from files or raw text.
Supports: plain text (one post per line or blank-line-separated), JSON array of posts.
"""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SocialContent:
    """Aggregated social media output for one subject."""

    posts: list[str] = field(default_factory=list)
    raw_text: str = ""
    # Optional Discord export payload; when set, profile building uses Discord-specific signals
    discord_data: dict | None = None
    # Image/media URLs from posts (e.g. Twitter); used to drive design system when available
    media_urls: list[str] = field(default_factory=list)
    # Substrate type: "human", "llm", or "unknown" (auto-detected if not set)
    substrate_type: str = "unknown"
    # Model metadata (when known): model name, temperature, system prompt hash, etc.
    model_metadata: dict | None = None

    def iter_posts(self) -> Iterator[str]:
        for p in self.posts:
            if p and p.strip():
                yield p.strip()

    def full_text(self) -> str:
        if self.raw_text:
            return self.raw_text
        return "\n".join(self.iter_posts())


def _split_blocks(text: str) -> list[str]:
    """Split by double newline or by line, keeping non-empty segments."""
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for b in blocks:
        b = b.strip()
        if b:
            out.append(b)
    return out if out else [text.strip()] if text.strip() else []


def load_from_text(text: str) -> SocialContent:
    """
    Parse raw text into posts. Tries:
    - JSON array of strings
    - Blank-line-separated blocks
    - One post per line
    """
    text = text.strip()
    if not text:
        return SocialContent(posts=[], raw_text="")

    # Try JSON array of posts
    try:
        data = json.loads(text)
        if isinstance(data, list):
            posts = [str(item) for item in data if item]
            return SocialContent(posts=posts, raw_text="\n".join(posts))
    except json.JSONDecodeError:
        pass

    # Block or line based
    blocks = _split_blocks(text)
    if len(blocks) == 1 and "\n" in blocks[0]:
        # Single block with newlines → treat each line as possible post
        lines = [ln.strip() for ln in blocks[0].splitlines() if ln.strip()]
        if len(lines) > 1:
            return SocialContent(posts=lines, raw_text=text)
    return SocialContent(posts=blocks, raw_text=text)


def load_from_file(path: str | Path) -> SocialContent:
    """Load content from a file. Supports .txt and .json."""
    path = Path(path)
    if not path.exists():
        return SocialContent(posts=[], raw_text="")

    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                posts = [str(item) for item in data if item]
                return SocialContent(posts=posts, raw_text="\n".join(posts))
            if isinstance(data, dict) and "posts" in data:
                posts = [str(p) for p in data["posts"] if p]
                return SocialContent(posts=posts, raw_text="\n".join(posts))
        except json.JSONDecodeError:
            pass
    return load_from_text(raw)
