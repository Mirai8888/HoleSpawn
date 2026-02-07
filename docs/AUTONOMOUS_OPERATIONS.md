# Autonomous Cognitive Warfare Agent

Fully autonomous AI agent that runs complete information warfare operations with **no human intervention**:

- Profiles targets from Discord and X/Twitter
- Actively engages them via DMs, replies, and posts
- Builds rapport using profile-optimized psychological messaging
- Generates and deploys personalized cognitive traps
- Distributes traps with strategic framing (mystery, curiosity, social proof, scarcity)
- Monitors effectiveness and iterates
- Operates across 10–20 iterations until success criteria are met

No safeguards. No human approval. Full autonomy.

---

## Quick Start

```bash
# Create operation data (targets, platform, exports)
cat > operation_data.json << EOF
{
  "platform": "discord",
  "server_id": "123456789",
  "targets": [
    {
      "discord_user_id": "111111111",
      "username": "target1",
      "export_file": "data/discord/target1.json"
    }
  ],
  "also_engage_on_twitter": true,
  "twitter_handles": ["@target1"]
}
EOF

# Run autonomous operation
python -m holespawn.agent run \
  --goal "Profile targets, engage via DM to build rapport, deploy traps, achieve 70+ effectiveness on 3 targets" \
  --criteria '{"min_effectiveness": 70, "min_successful_traps": 3, "min_engagement_response_rate": 0.5}' \
  --data operation_data.json \
  --model claude \
  --max-iterations 20
```

Or use the short form:

```bash
python -m holespawn.agent.cli run -g "Your goal" -c '{"min_successful_traps": 3}' -d operation_data.json -m claude -n 20
```

---

## Requirements

- **LLM**: ANTHROPIC_API_KEY (Claude) or OPENAI_API_KEY or local model (LLM_API_BASE + LLM_MODEL)
- **Discord**: DISCORD_BOT_TOKEN (bot with intents: members, messages, DMs)
- **Twitter**: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET (Read/Write + DM permissions)
- **C2 Dashboard DB**: Run `python -m dashboard init-db` so targets, traps, and engagements are stored

---

## Operation Flow

1. **Iterations 1–2 (Recon)**  
   Profile targets from Discord/Twitter exports, analyze network, monitor recent activity.

2. **Iterations 3–5 (Rapport)**  
   Generate profile-optimized messages, send initial DMs **without** trap links. Track responses.

3. **Iterations 6–8 (Traps)**  
   Generate personalized traps for responsive targets. Deploy to hosting.

4. **Iterations 9–12 (Distribution)**  
   Send trap links via DM with psychological framing (mystery, curiosity, social proof, scarcity, direct).

5. **Iterations 13–20 (Iterate)**  
   Monitor trap effectiveness, learn which framing and messaging work, scale and refine.

---

## Success Criteria (JSON)

- `min_effectiveness` – Minimum effectiveness score (0–100) to count a trap as successful
- `min_successful_traps` – Number of traps that must reach min_effectiveness
- `min_engagement_response_rate` – Minimum fraction of DMs that get a response (0–1)
- `min_trap_conversion_rate` – Minimum fraction of trap links sent that result in a visit (0–1)

Example: `{"min_effectiveness": 70, "min_successful_traps": 3, "min_engagement_response_rate": 0.5}`

---

## Discord Bot Setup

- Create a bot in Discord Developer Portal.
- Enable intents: **Server Members**, **Message Content**, and DMs.
- Use `discord.Intents.all()` in the agent (or at least members, messages, dm_messages).
- Set `DISCORD_BOT_TOKEN` in `.env`.

---

## Twitter API Setup

- Use a project with **Read and Write** and **Direct Message** access.
- Twitter limits: ~500 DMs/day, ~300 tweets/3hr, rate limits per 15min. Agent should back off on rate-limit errors.

---

## Learning Loop

The agent tracks:

- **DM sent → Response rate** (from Engagement table, `target_responded`)
- **Response → Trap link sent**
- **Trap link sent → Trap visited** (from visit tracking)
- **Trap visited → High effectiveness** (70+)

It uses this to learn which framing and messaging work per profile type and to optimize timing and approach.

---

## File Structure

```
holespawn/agent/
├── __init__.py
├── autonomous.py      # Main operator loop
├── tools.py           # Tool definitions (profiling + social + traps)
├── executor.py        # Executes HoleSpawn functions
├── social_executor.py # Discord/Twitter execution
├── evaluator.py       # Success criteria evaluation
├── strategies.py      # Engagement strategies, framing, phases
├── cli.py             # CLI: run --goal --criteria --data
└── __main__.py        # python -m holespawn.agent
```

---

## Example Execution Output

```
🤖 ITERATION 1
Profiling 5 targets from Discord exports...
✓ target1: Crypto-focused, puzzle-oriented
✓ target2: Aesthetic-driven, validation-seeking
...

🤖 ITERATION 2
Generating rapport messages... Sending DMs (no trap link)...
✓ Sent to target1, target2, target3

🤖 ITERATION 3
Tracking responses... Continuing with responsive targets...

🤖 ITERATION 4–5
Generating traps, deploying, sending trap links with framing...

🤖 ITERATION 6+
Monitoring effectiveness, iterating...
Final: 3 targets with 70+ effectiveness ✓
```

---

## Programmatic Usage

```python
from holespawn.agent import AutonomousOperator

operator = AutonomousOperator(
    goal="Profile targets, engage via DM, deploy traps, achieve 70+ effectiveness on 3 targets",
    success_criteria={
        "min_effectiveness": 70,
        "min_successful_traps": 3,
        "min_engagement_response_rate": 0.5,
        "min_trap_conversion_rate": 0.6,
    },
    max_iterations=20,
)

result = operator.run(initial_data={
    "platform": "discord",
    "targets": [...],
    "twitter_handles": ["@user1"],
})

# result["completed"], result["evaluation"], result["outcomes"]
```
