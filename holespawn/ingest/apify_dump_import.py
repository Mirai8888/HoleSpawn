"""
Import local Apify dump files (apify_dump/run_*_SUCCEEDED.json) and turn them
into per-handle text corpora + a simple score index, so they can be used as
HoleSpawn profile inputs without calling Apify again.

CLI (default behavior):

  python -m holespawn.ingest.apify_dump_import

This will:
  - Scan ./apify_dump for run_*_SUCCEEDED.json files.
  - Group tweets by author handle (author.userName / author.username / author.screen_name).
  - Extract tweet text using the same heuristics as fetch_twitter_apify().
  - Write one file per handle under data/apify_handles/<handle>.txt
    (one tweet per line).
  - Write data/apify_handles/index.json with basic metrics per handle:
      { "handle": "...", "tweet_count": N, "engagement": M }
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from .apify_twitter import _item_to_text


APIFY_DUMP_DIR = Path("apify_dump")
OUTPUT_ROOT = Path("data") / "apify_handles"


def _author_handle(item: dict[str, Any]) -> str | None:
    """Extract an author handle from a tweet item."""
    author = item.get("author") or item.get("user") or {}
    if not isinstance(author, dict):
        return None
    for key in ("userName", "username", "screen_name", "screenName"):
        v = author.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip().lstrip("@")
    # Fallback: from URL, if present
    url = (author.get("url") or author.get("twitterUrl") or "") or ""
    if isinstance(url, str) and url:
        # e.g. https://twitter.com/handle or https://x.com/handle
        for prefix in ("https://twitter.com/", "https://x.com/"):
            if url.startswith(prefix):
                rest = url[len(prefix) :]
                handle = rest.split("/", 1)[0]
                if handle:
                    return handle.strip().lstrip("@")
    return None


def _engagement(item: dict[str, Any]) -> int:
    """Rough engagement score for one tweet."""
    fields = ("retweetCount", "replyCount", "likeCount", "quoteCount", "viewCount")
    score = 0
    for f in fields:
        v = item.get(f)
        try:
            score += int(v or 0)
        except (TypeError, ValueError):
            continue
    return score


@dataclass
class HandleAggregate:
    handle: str
    tweet_count: int = 0
    engagement: int = 0


def collect_from_dump(
    dump_dir: Path = APIFY_DUMP_DIR,
) -> tuple[dict[str, list[str]], dict[str, HandleAggregate]]:
    """
    Walk apify_dump/ and aggregate tweets per handle.

    Returns:
      - texts_by_handle: {handle: [tweet_text, ...]}
      - stats_by_handle: {handle: HandleAggregate}
    """
    texts_by_handle: dict[str, list[str]] = defaultdict(list)
    stats_by_handle: dict[str, HandleAggregate] = {}

    if not dump_dir.is_dir():
        return {}, {}

    for path in sorted(dump_dir.glob("run_*_SUCCEEDED.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            handle = _author_handle(item)
            if not handle:
                continue
            text = _item_to_text(item).strip()
            if not text:
                continue
            texts_by_handle[handle].append(text.replace("\r\n", "\n").replace("\r", "\n"))
            agg = stats_by_handle.get(handle)
            if agg is None:
                agg = HandleAggregate(handle=handle, tweet_count=0, engagement=0)
                stats_by_handle[handle] = agg
            agg.tweet_count += 1
            agg.engagement += _engagement(item)

    return texts_by_handle, stats_by_handle


def write_handle_corpora(
    texts_by_handle: dict[str, list[str]],
    stats_by_handle: dict[str, HandleAggregate],
    output_root: Path = OUTPUT_ROOT,
) -> Path:
    """
    Write per-handle text files and an index.json.

    Returns:
      Path to index.json.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []
    for handle, texts in sorted(texts_by_handle.items(), key=lambda kv: -len(kv[1])):
        safe = handle.replace("/", "_")
        dst = output_root / f"{safe}.txt"
        dst.write_text("\n".join(texts), encoding="utf-8")
        agg = stats_by_handle.get(handle) or HandleAggregate(handle=handle)
        index.append(asdict(agg))
    index_path = output_root / "index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index_path


def main(argv: Iterable[str] | None = None) -> None:
    # Simple, no-arg CLI for now: just process everything under apify_dump.
    texts_by_handle, stats_by_handle = collect_from_dump(APIFY_DUMP_DIR)
    if not texts_by_handle:
        print("No Apify dump data found under apify_dump/", flush=True)
        return
    index_path = write_handle_corpora(texts_by_handle, stats_by_handle, OUTPUT_ROOT)
    print(f"Wrote {len(texts_by_handle)} handle corpora to {OUTPUT_ROOT}")
    print(f"Index: {index_path}")


if __name__ == "__main__":  # pragma: no cover
    main()

