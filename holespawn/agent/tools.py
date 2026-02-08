"""
Agent tool definitions for LLM function calling.
Profiling, trap ops, and social engagement.
"""

# Core ops: profile, trap, deploy, effectiveness, network, status
FUNCTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "profile_target",
            "description": "Generate psychological profile for a target from their raw data (Discord/Twitter)",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {
                        "type": "integer",
                        "description": "Target ID (must have raw_data)",
                    },
                    "use_nlp": {"type": "boolean", "default": True},
                    "use_llm": {"type": "boolean", "default": True},
                },
                "required": ["target_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_trap",
            "description": "Generate personalized trap site for a profiled target",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "integer", "description": "Target ID (must be profiled)"},
                },
                "required": ["target_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_trap",
            "description": "Deploy a trap (mark live, get URL)",
            "parameters": {
                "type": "object",
                "properties": {
                    "trap_id": {"type": "integer"},
                    "url": {"type": "string", "description": "Deployed URL if known"},
                },
                "required": ["trap_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trap_effectiveness",
            "description": "Get effectiveness score (0-100) for a trap",
            "parameters": {
                "type": "object",
                "properties": {"trap_id": {"type": "integer"}},
                "required": ["trap_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_network",
            "description": "Build network graph from profiles directory (community detection, central nodes)",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Path to directory of profile/behavioral_matrix JSONs",
                    },
                    "name": {"type": "string", "description": "Network name"},
                },
                "required": ["dir_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_operation_status",
            "description": "Get overall operation status: targets, traps, jobs, engagements",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SOCIAL_ENGAGEMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_discord_dm",
            "description": "Send direct message on Discord to a target, with messaging optimized for their psychological profile",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "integer", "description": "Target ID (must be profiled)"},
                    "message": {
                        "type": "string",
                        "description": "Message content (sent via Discord bot)",
                    },
                    "include_trap_link": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include link to their personalized trap",
                    },
                    "framing": {
                        "type": "string",
                        "enum": ["mystery", "curiosity", "direct", "social_proof", "scarcity"],
                        "description": "How to frame the trap link (if included)",
                    },
                },
                "required": ["target_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_twitter_dm",
            "description": "Send direct message on X/Twitter to a target",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "integer", "description": "Target ID (must be profiled)"},
                    "message": {"type": "string", "description": "Message content"},
                    "include_trap_link": {"type": "boolean", "default": False},
                    "framing": {
                        "type": "string",
                        "enum": ["mystery", "curiosity", "direct", "social_proof", "scarcity"],
                    },
                },
                "required": ["target_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_to_tweet",
            "description": "Reply to a target's tweet with profile-optimized message",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "integer", "description": "Target ID"},
                    "tweet_id": {"type": "string", "description": "ID of tweet to reply to"},
                    "reply": {"type": "string", "description": "Reply content (280 char limit)"},
                },
                "required": ["target_id", "tweet_id", "reply"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_in_discord_channel",
            "description": "Post message in Discord channel (public engagement)",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "Discord channel ID"},
                    "message": {"type": "string", "description": "Message content"},
                    "reply_to_message_id": {
                        "type": "string",
                        "description": "Optional: ID of message to reply to",
                    },
                },
                "required": ["channel_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_profile_optimized_message",
            "description": "Generate a message optimized for target's psychological profile (use before sending)",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "integer", "description": "Target ID (must be profiled)"},
                    "intent": {
                        "type": "string",
                        "description": "What you want to achieve (e.g. build rapport, introduce trap, create curiosity)",
                    },
                    "context": {
                        "type": "string",
                        "description": "Conversation context or what triggered this message",
                    },
                    "include_trap_link": {"type": "boolean", "default": False},
                },
                "required": ["target_id", "intent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "monitor_target_activity",
            "description": "Get recent activity from a target (recent tweets, Discord messages) to inform engagement timing",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "integer", "description": "Target ID"},
                    "platform": {"type": "string", "enum": ["discord", "twitter", "both"]},
                    "lookback_hours": {
                        "type": "integer",
                        "default": 24,
                        "description": "How far back to look for activity",
                    },
                },
                "required": ["target_id", "platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "track_engagement_response",
            "description": "Track if target responded to your message/post (for learning what works)",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "integer"},
                    "engagement_type": {"type": "string", "enum": ["dm", "reply", "channel_post"]},
                    "message_id": {"type": "string", "description": "ID of message you sent"},
                },
                "required": ["target_id", "engagement_type", "message_id"],
            },
        },
    },
]

ALL_AGENT_TOOLS = FUNCTION_TOOLS + SOCIAL_ENGAGEMENT_TOOLS
