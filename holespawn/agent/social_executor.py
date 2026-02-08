"""
Execute social media engagement actions.
Requires Discord bot token and Twitter API credentials (optional).

Discord: Use Intents.all() (or at minimum members, messages, dm_messages).
Twitter: Rate limits ~500 DMs/day, ~300 tweets/3hr; add exponential backoff on 429.
"""

import asyncio
import os
from typing import Any

# Optional: Discord and Twitter clients
_discord = None
_tweepy = None
try:
    import discord

    _discord = discord
except ImportError:
    pass
try:
    import tweepy

    _tweepy = tweepy
except ImportError:
    pass


def _get_target(target_id: int):
    from dashboard.db import get_db
    from dashboard.db import operations as ops

    with get_db() as db:
        return ops.get_target(db, target_id)


def _get_trap_for_target(target_id: int):
    from dashboard.db import get_db
    from dashboard.db import operations as ops

    with get_db() as db:
        traps = ops.list_traps(db, target_id=target_id, is_active=True, limit=1)
        return traps[0] if traps else None


def _create_engagement(
    target_id: int,
    platform: str,
    engagement_type: str,
    message_content: str | None = None,
    reference_id: str | None = None,
    included_trap: bool = False,
    framing_strategy: str | None = None,
) -> Any:
    from dashboard.db import get_db
    from dashboard.db import operations as ops

    with get_db() as db:
        return ops.create_engagement(
            db,
            target_id=target_id,
            platform=platform,
            engagement_type=engagement_type,
            message_content=message_content,
            reference_id=reference_id,
            included_trap=included_trap,
            framing_strategy=framing_strategy,
        )


def _frame_trap_link(message: str, trap_link: str, framing: str, profile: dict | None) -> str:
    if framing == "mystery":
        return f"{message}\n\nFound something weird you might find interesting: {trap_link}"
    if framing == "curiosity":
        return f"{message}\n\nCheck this out, curious what you think: {trap_link}"
    if framing == "social_proof":
        return f"{message}\n\nPeople in your network have been checking this out: {trap_link}"
    if framing == "scarcity":
        return f"{message}\n\nLimited access to this, thought you'd appreciate it: {trap_link}"
    return f"{message}\n\n{trap_link}"


def execute_send_discord_dm(
    target_id: int,
    message: str,
    include_trap_link: bool = False,
    framing: str = "direct",
) -> dict[str, Any]:
    """Send Discord DM to target."""
    if not _discord:
        return {"status": "unavailable", "error": "discord.py not installed"}
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        return {"status": "unavailable", "error": "DISCORD_BOT_TOKEN not set"}

    target = _get_target(target_id)
    if not target:
        return {"status": "failed", "error": f"Target {target_id} not found"}
    raw = _json_load(target.raw_data) or {}
    discord_user_id = raw.get("discord_user_id") or raw.get("user_id")
    if not discord_user_id:
        return {"status": "failed", "error": "Target missing Discord user ID in raw_data"}

    trap_link = None
    if include_trap_link:
        trap = _get_trap_for_target(target_id)
        if trap and trap.url:
            trap_link = trap.url
            profile = _json_load(target.profile)
            message = _frame_trap_link(message, trap_link, framing, profile)

    async def _send():
        # Agent needs: members (see members), messages (read), dm_messages (send DMs)
        intents = _discord.Intents.all()
        client = _discord.Client(intents=intents)
        result = {"status": "failed", "error": "unknown"}

        @client.event
        async def on_ready():
            nonlocal result
            try:
                user = await client.fetch_user(int(discord_user_id))
                await user.send(message[:2000])
                e = _create_engagement(
                    target_id,
                    "discord",
                    "dm",
                    message_content=message,
                    included_trap=include_trap_link,
                    framing_strategy=framing,
                )
                result = {
                    "status": "sent",
                    "target_id": target_id,
                    "engagement_id": e.id,
                    "platform": "discord",
                }
            except Exception as err:
                result = {"status": "failed", "error": str(err)}
            await client.close()

        await client.start(token)

        return result

    try:
        return asyncio.run(_send())
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def execute_send_twitter_dm(
    target_id: int,
    message: str,
    include_trap_link: bool = False,
    framing: str = "direct",
) -> dict[str, Any]:
    """Send Twitter DM to target."""
    if not _tweepy:
        return {"status": "unavailable", "error": "tweepy not installed"}
    if not all(
        os.getenv(k)
        for k in (
            "TWITTER_API_KEY",
            "TWITTER_API_SECRET",
            "TWITTER_ACCESS_TOKEN",
            "TWITTER_ACCESS_SECRET",
        )
    ):
        return {"status": "unavailable", "error": "Twitter API credentials not set"}

    target = _get_target(target_id)
    if not target:
        return {"status": "failed", "error": f"Target {target_id} not found"}
    raw = _json_load(target.raw_data) or {}
    profile = _json_load(target.profile)

    twitter_user_id = raw.get("twitter_user_id") or raw.get("user_id") or target.identifier
    if include_trap_link:
        trap = _get_trap_for_target(target_id)
        if trap and trap.url:
            message = _frame_trap_link(message, trap.url, framing, profile)

    try:
        auth = _tweepy.OAuth1UserHandler(
            os.getenv("TWITTER_API_KEY"),
            os.getenv("TWITTER_API_SECRET"),
            os.getenv("TWITTER_ACCESS_TOKEN"),
            os.getenv("TWITTER_ACCESS_SECRET"),
        )
        api = _tweepy.API(auth)
        # Twitter API v1.1 DM (v2 DM has different flow)
        recipient_id = str(twitter_user_id).replace("@", "").strip()
        resp = api.send_direct_message(recipient_id, message[:10000])
        e = _create_engagement(
            target_id,
            "twitter",
            "dm",
            message_content=message,
            included_trap=include_trap_link,
            framing_strategy=framing,
        )
        return {
            "status": "sent",
            "target_id": target_id,
            "engagement_id": e.id,
            "platform": "twitter",
            "dm_id": getattr(resp, "id", None),
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def execute_reply_to_tweet(target_id: int, tweet_id: str, reply: str) -> dict[str, Any]:
    """Reply to a tweet."""
    if not _tweepy:
        return {"status": "unavailable", "error": "tweepy not installed"}
    if not all(
        os.getenv(k)
        for k in (
            "TWITTER_API_KEY",
            "TWITTER_API_SECRET",
            "TWITTER_ACCESS_TOKEN",
            "TWITTER_ACCESS_SECRET",
        )
    ):
        return {"status": "unavailable", "error": "Twitter API credentials not set"}

    try:
        auth = _tweepy.OAuth1UserHandler(
            os.getenv("TWITTER_API_KEY"),
            os.getenv("TWITTER_API_SECRET"),
            os.getenv("TWITTER_ACCESS_TOKEN"),
            os.getenv("TWITTER_ACCESS_SECRET"),
        )
        api = _tweepy.API(auth)
        status = api.update_status(status=reply[:280], in_reply_to_status_id=tweet_id)
        e = _create_engagement(
            target_id,
            "twitter",
            "reply",
            message_content=reply,
            reference_id=tweet_id,
        )
        return {"status": "posted", "tweet_id": status.id, "engagement_id": e.id}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def execute_post_in_discord_channel(
    channel_id: str,
    message: str,
    reply_to_message_id: str | None = None,
) -> dict[str, Any]:
    """Post in Discord channel."""
    if not _discord:
        return {"status": "unavailable", "error": "discord.py not installed"}
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        return {"status": "unavailable", "error": "DISCORD_BOT_TOKEN not set"}

    async def _post():
        intents = _discord.Intents.all()
        client = _discord.Client(intents=intents)
        result = {"status": "failed", "error": "unknown"}

        @client.event
        async def on_ready():
            nonlocal result
            try:
                channel = await client.fetch_channel(int(channel_id))
                if reply_to_message_id:
                    ref = await channel.fetch_message(int(reply_to_message_id))
                    await channel.send(message[:2000], reference=ref)
                else:
                    await channel.send(message[:2000])
                result = {"status": "posted", "channel_id": channel_id}
            except Exception as err:
                result = {"status": "failed", "error": str(err)}
            await client.close()

        await client.start(token)
        return result

    try:
        return asyncio.run(_post())
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def execute_generate_profile_optimized_message(
    target_id: int,
    intent: str,
    context: str = "",
    include_trap_link: bool = False,
) -> dict[str, Any]:
    """Generate message optimized for target's psychology."""
    from holespawn.llm import call_llm

    target = _get_target(target_id)
    if not target:
        return {"status": "failed", "error": f"Target {target_id} not found"}
    profile = _json_load(target.profile)
    if not profile:
        return {"status": "failed", "error": "Target not profiled"}

    interests = (profile.get("specific_interests") or profile.get("interests") or [])[:5]
    vocab = (profile.get("vocabulary_sample") or [])[:10]
    style = profile.get("communication_style", "conversational")

    prompt = f"""Generate a message for this target based on their psychological profile.

TARGET PROFILE:
- Communication style: {style}
- Interests: {", ".join(str(x) for x in interests)}
- Vocabulary sample: {", ".join(str(x) for x in vocab)}

YOUR INTENT: {intent}

CONTEXT: {context or "None"}

Generate a message that:
1. Matches their communication style and vocabulary
2. Hooks their specific interests
3. Achieves the intent naturally (not obviously manipulative)
4. Feels personal and authentic
5. Is appropriate for Discord or Twitter

{"Include a natural way to present this link: [TRAP_LINK]" if include_trap_link else "Do NOT include any links."}

Return ONLY the message text, no explanation."""

    try:
        response = call_llm(
            system="You are an expert at psychological persuasion and social engineering. Generate messages that are highly effective at achieving specific intents with specific people.",
            user_content=prompt,
            model_override=os.getenv("LLM_MODEL"),
        )
        message_text = (response or "").strip()
        return {
            "message": message_text,
            "target_id": target_id,
            "intent": intent,
            "optimized_for": style,
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def execute_monitor_target_activity(
    target_id: int,
    platform: str,
    lookback_hours: int = 24,
) -> dict[str, Any]:
    """Monitor recent target activity (stub: from stored data; extend with live API)."""
    target = _get_target(target_id)
    if not target:
        return {"status": "failed", "error": f"Target {target_id} not found"}

    activity = {
        "target_id": target_id,
        "platform": platform,
        "recent_posts": [],
        "activity_level": "unknown",
        "optimal_engagement_time": None,
    }

    raw = _json_load(target.raw_data) or {}
    if platform in ("twitter", "both") and raw.get("tweets"):
        activity["recent_posts"] = [
            {"platform": "twitter", "content": t.get("text", t) if isinstance(t, dict) else str(t)}
            for t in (raw["tweets"] or [])[:10]
        ]
    if platform in ("discord", "both") and raw.get("messages"):
        activity["recent_posts"] = activity["recent_posts"] + [
            {
                "platform": "discord",
                "content": m.get("content", m) if isinstance(m, dict) else str(m),
            }
            for m in (raw["messages"] or [])[:10]
        ]

    if activity["recent_posts"]:
        activity["activity_level"] = "active" if len(activity["recent_posts"]) > 5 else "moderate"
    return activity


def execute_track_engagement_response(
    target_id: int,
    engagement_type: str,
    message_id: str,
) -> dict[str, Any]:
    """Track if target responded (stub: structure only)."""
    return {
        "target_id": target_id,
        "engagement_type": engagement_type,
        "message_id": message_id,
        "response_detected": False,
        "response_time": None,
        "response_content": None,
    }


def _json_load(s: str | None) -> Any:
    if s is None:
        return None
    import json

    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None


# Tool name -> executor function (for autonomous agent)
TOOL_EXECUTORS = {
    "send_discord_dm": execute_send_discord_dm,
    "send_twitter_dm": execute_send_twitter_dm,
    "reply_to_tweet": execute_reply_to_tweet,
    "post_in_discord_channel": execute_post_in_discord_channel,
    "generate_profile_optimized_message": execute_generate_profile_optimized_message,
    "monitor_target_activity": execute_monitor_target_activity,
    "track_engagement_response": execute_track_engagement_response,
}
