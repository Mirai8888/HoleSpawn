# Discord profile ingestion

HoleSpawn can ingest **Discord user data** (messages, reactions, server affiliations, interaction patterns) to build a psychological profile and generate personalized traps. Discord data is often more psychologically revealing than public Twitter/X: more conversational, less performative, with server affiliations and reaction patterns that reveal tribal psychology and emotional triggers.

## Data collection note

**HoleSpawn does not provide scraping or export tools for Discord.** You must supply the data in the expected format. Discord data can be collected via:

- Browser extensions (e.g. Tampermonkey / Vencord scripts that export messages and metadata)
- Manual copy-paste and formatting
- Any third-party export tool that outputs the structure below

Use only data you are authorized to use. Respect Discord’s Terms of Service and applicable privacy laws.

---

## Expected export format

Provide a **single JSON object** with the following structure. All fields except `messages` are optional; `messages` should contain at least one item with `content` (or `body`).

```json
{
  "user_id": "string",
  "username": "string",
  "messages": [
    {
      "content": "string",
      "timestamp": "ISO8601",
      "channel_id": "string",
      "channel_name": "string",
      "server_id": "string",
      "server_name": "string",
      "reactions": ["emoji1", "emoji2"]
    }
  ],
  "reactions_given": [
    {
      "message_id": "string",
      "emoji": "string",
      "message_content": "string",
      "timestamp": "ISO8601"
    }
  ],
  "servers": [
    {
      "server_id": "string",
      "server_name": "string",
      "join_date": "ISO8601",
      "activity_level": "high|medium|low"
    }
  ],
  "interactions": [
    {
      "user_id": "string",
      "username": "string",
      "interaction_count": 42,
      "channels": ["channel_name1", "channel_name2"]
    }
  ],
  "activity_patterns": {
    "peak_hours": [14, 15, 16],
    "active_days": [0, 1, 2, 3, 4],
    "message_frequency": 5.2
  }
}
```

- **messages**: Required. Each item can have `content` or `body`; both are used as post text. Used for themes, voice, and conversational intimacy.
- **reactions_given**: Messages this user reacted to; `message_content` is used to infer **reaction triggers** (what resonates emotionally).
- **servers**: Used for **tribal affiliations** (community themes / values).
- **interactions**: Used with message volume to infer **community role** (lurker / participant / leader).
- **activity_patterns**: Passed through as **engagement_rhythm** (peak_hours, active_days, message_frequency) for design pacing.

---

## Usage

**Simple (existing pipeline):**
```python
from holespawn.ingest import load_from_discord
from holespawn.profile import build_profile

content = load_from_discord(payload)
profile = build_profile(content)  # Uses analyzer + _extract_discord_signals
```

**Hybrid (NLP + LLM, recommended for Discord):**
```python
from holespawn.ingest import load_from_discord
from holespawn.profile.discord_profile_builder import build_discord_profile

profile = build_discord_profile(
    payload,
    use_nlp=True,   # Linguistic, sentiment, network, topics (no API)
    use_llm=True,  # Psychological synthesis from NLP + samples
    use_local=True,
    local_preset="ollama-llama3",  # or api_base=..., model=...
)
```

**CLI:**
```bash
python -m holespawn.build_site --discord data/sample_discord_export.json
python -m holespawn.build_site --discord export.json --local-model ollama-llama3
```

---

## Profile fields added for Discord

When `content.discord_data` is present, `build_profile(content)` fills:

| Field | Description |
|-------|-------------|
| `tribal_affiliations` | Server names / themes (from `servers`) |
| `reaction_triggers` | Themes from messages they reacted to (from `reactions_given.message_content`) |
| `conversational_intimacy` | `"guarded"` \| `"open"` \| `"vulnerable"` (from message length and vulnerability markers) |
| `community_role` | `"lurker"` \| `"participant"` \| `"leader"` (from message count and interaction totals) |
| `engagement_rhythm` | `activity_patterns` (peak_hours, active_days, message_frequency) |

These are used by the **design system** (aesthetic, pacing, intimacy) and **content generation** (voice, server-themed callbacks, “understands my Discord presence”) for deeper personalization.

---

## Sample data

See `data/sample_discord_export.json` for a minimal realistic example you can use to test the ingestion and profiling pipeline.
