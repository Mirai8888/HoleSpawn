"""
Record one run: for each subject in config, fetch live data (Twitter or Discord),
write JSON snapshots, update SQLite index.
"""

import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from holespawn.ingest.apify_twitter import fetch_twitter_apify_raw

from .config import load_subjects


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _init_index(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            file_path TEXT NOT NULL,
            source_type TEXT NOT NULL,
            record_count INTEGER NOT NULL,
            UNIQUE(subject_id, timestamp)
        )
        """
    )
    conn.commit()
    conn.close()


def _insert_record(db_path: Path, subject_id: str, timestamp: str, file_path: str, source_type: str, record_count: int) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO recordings (subject_id, timestamp, file_path, source_type, record_count) VALUES (?, ?, ?, ?, ?)",
        (subject_id, timestamp, file_path, source_type, record_count),
    )
    conn.commit()
    conn.close()


def _record_twitter(handle: str, recordings_root: Path, db_path: Path, max_tweets: int = 500) -> bool:
    """Fetch Twitter via scraper, write raw JSON, index. Returns True if recorded."""
    raw = fetch_twitter_apify_raw(handle, max_tweets=max_tweets)
    if raw is None:
        return False
    subject_id = handle if handle.startswith("@") else f"@{handle}"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    subdir = recordings_root / "twitter" / subject_id
    _ensure_dir(subdir)
    file_path = subdir / f"{timestamp}.json"
    def _json_default(o):  # noqa: B008
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=None, default=_json_default)
    rel_path = str(file_path.relative_to(recordings_root))
    _insert_record(db_path, subject_id, timestamp, rel_path, "twitter", len(raw))
    return True


def _record_discord(server: str, recordings_root: Path, db_path: Path, max_messages_per_channel: int = 500) -> bool:
    """
    Fetch recent messages from a Discord server via bot account, write raw JSON, index.
    Requires DISCORD_BOT_TOKEN and that the bot is a member of the server.

    server: guild ID (recommended) or guild name (fallback match).
    """
    import logging

    logger = logging.getLogger(__name__)
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.warning("DISCORD_BOT_TOKEN not set; cannot record Discord server %s", server)
        return False

    try:
        import discord
    except ImportError as e:
        logger.warning("discord.py not installed; cannot record Discord server %s: %s", server, e)
        return False

    async def _fetch_server_snapshot(server_identifier: str) -> dict | None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True

        client: discord.Client = discord.Client(intents=intents)  # type: ignore[assignment]
        snapshot: dict = {"server_id": None, "server_name": None, "messages": []}

        @client.event
        async def on_ready() -> None:  # type: ignore[override]
            try:
                guild = None
                for g in client.guilds:
                    if str(g.id) == server_identifier or g.name == server_identifier:
                        guild = g
                        break
                if guild is None:
                    logger.warning("Bot is not in Discord server %s; skipping", server_identifier)
                    await client.close()
                    return
                snapshot["server_id"] = str(guild.id)
                snapshot["server_name"] = guild.name

                for channel in guild.text_channels:
                    try:
                        async for msg in channel.history(limit=max_messages_per_channel):
                            try:
                                snapshot["messages"].append(
                                    {
                                        "message_id": str(msg.id),
                                        "user_id": str(msg.author.id),
                                        "username": str(msg.author),
                                        "content": msg.content,
                                        "timestamp": msg.created_at.isoformat(),
                                        "channel_id": str(channel.id),
                                        "channel_name": channel.name,
                                        "server_id": str(guild.id),
                                        "server_name": guild.name,
                                    }
                                )
                            except Exception:
                                continue
                    except Exception:
                        continue
            finally:
                await client.close()

        try:
            await client.start(token)
        except Exception as e:
            logger.warning("Discord client error while recording server %s: %s", server_identifier, e)
            return None
        return snapshot if snapshot.get("messages") else None

    def _run_fetch(server_identifier: str) -> dict | None:
        try:
            return asyncio.run(_fetch_server_snapshot(server_identifier))
        except RuntimeError:
            # Event loop already running (unlikely for CLI); create a new loop.
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_fetch_server_snapshot(server_identifier))
            finally:
                loop.close()

    snapshot = _run_fetch(server)
    if not snapshot or not snapshot.get("messages"):
        return False

    server_id = str(snapshot.get("server_id") or server)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    subdir = recordings_root / "discord" / server_id
    _ensure_dir(subdir)
    file_path = subdir / f"{timestamp}.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    rel_path = str(file_path.relative_to(recordings_root))
    record_count = len(snapshot.get("messages") or [])
    _insert_record(db_path, server_id, timestamp, rel_path, "discord", record_count)
    logger.info("Recorded Discord server %s (%s) with %d messages", server_id, snapshot.get("server_name"), record_count)
    return True


def record_all(
    config_path: str | Path | None = None,
    recordings_dir: str | Path | None = None,
    max_tweets_per_user: int = 500,
) -> dict[str, int]:
    """
    Load subjects, record each (Twitter via scraper, Discord stubbed). Returns counts: recorded, skipped, failed.
    """
    import logging
    logger = logging.getLogger(__name__)

    root = Path(recordings_dir or "recordings")
    db_path = root / "recordings.db"
    _ensure_dir(root)
    _init_index(db_path)

    subjects = load_subjects(config_path)
    if not subjects:
        logger.warning("No subjects in config (subjects.yaml). Nothing to record.")
        return {"recorded": 0, "skipped": 0, "failed": 0}

    recorded = 0
    failed = 0
    for s in subjects:
        source = s.get("source", "twitter")
        if source == "twitter":
            handle = s.get("handle", "")
            if _record_twitter(handle, root, db_path, max_tweets=max_tweets_per_user):
                recorded += 1
                logger.info("Recorded @%s", handle.lstrip("@"))
            else:
                failed += 1
                logger.warning("Failed to record @%s (no data or scraper error)", handle.lstrip("@"))
        elif source == "discord":
            if _record_discord(s.get("server", ""), root, db_path):
                recorded += 1
            else:
                failed += 1
                logger.warning("Discord recording not implemented; skipped server %s", s.get("server"))

    return {"recorded": recorded, "skipped": 0, "failed": failed}
