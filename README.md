# HoleSpawn

**SEITHAR GROUP - ATTENTION CAPTURE RESEARCH**

---

## SYSTEM OVERVIEW

HoleSpawn constructs subject-specific attention capture architectures through substrate analysis and generative deployment.

**Input:** Subject textual output  
**Process:** Matrix construction + trap generation  
**Output:** Personalized binding architecture

Subject awareness of mechanism: irrelevant to efficacy.

---

## INSTALLATION
```bash
git clone https://github.com/Mirai8888/HoleSpawn
cd HoleSpawn
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=credentials" > .env
```

**Cost:** Set `COST_WARN_THRESHOLD` (default 1.00) and `COST_MAX_THRESHOLD` (default 5.00) in `.env`. A run exits with error when estimated LLM cost exceeds max. Network runs with `--apify` and `--max-following > 20` prompt for confirmation unless `--yes`. Network brief cost is logged and saved to `cost_breakdown.json` next to the report.

**Errors:** API failures surface clearly: Apify errors as `ApifyError`, LLM errors as `LLM call failed (provider=... model=...): ...`. CLI errors are prefixed with `[holespawn]` on stderr.

---

## EXECUTION
```bash
python -m holespawn.build_site subject_substrate.txt
```

---

## DELIVERABLES
```
outputs/YYYYMMDD_HHMMSS_subject/
├── behavioral_matrix.json
├── binding_protocol.md
└── trap_architecture/
```

**Matrix:** Quantified patterns, vulnerability mapping  
**Protocol:** Manipulation vectors, engagement strategies  
**Architecture:** Substrate-specific modules

---

## METHODOLOGY

System employs:
1. Local substrate analysis
2. LLM synthesis
3. Pure generative architecture
4. Linguistic pattern matching
5. Vulnerability exploitation

Each architecture unique to subject.

---

## NETWORK FEATURES

Network analysis runs on **profiles** (behavioral matrices) and optional **edges** (follow graph):

- **Input:** A directory of `behavioral_matrix.json` (or `profile.json`) per account, or live data via **Apify** (paid API): target username → following list → tweets per user → profile each.
- **Output:** Community detection (clusters of similar accounts), structural centrality (most connected / central accounts), optional influence graph summary, and a **network engagement brief** (`network_engagement_brief.md`) — vulnerability mapping for the whole group: collective biases and mental processes treated almost as one organism (emotional triggers, trust hooks, susceptibilities, structural leverage). For rabbit-hole spawning at group scale or product understanding. Requires an LLM API key when writing with `-o`; use `--no-brief` to skip the brief.
- **No botting:** Analysis only. No persona generation, no campaigns, no deployment.

**CLI:**
```bash
# From exported profiles (e.g. multiple run dirs)
python -m holespawn.network path/to/profiles_dir/ -o network_report.json

# With follow-graph edges (CSV: source,target)
python -m holespawn.network path/to/profiles_dir/ --edges edges.csv -o network_report.json

# From Apify (requires APIFY_API_TOKEN): fetch target's following, profile each
python -m holespawn.network --apify @username --max-following 50 -o network_report.json
```

Report: JSON with `clusters`, `central_accounts`, `influence_graph` (if edges provided), `stats`. When `-o path/to/report.json` is set, `network_engagement_brief.md` is written in the same directory unless `--no-brief` is used.

---

## PROFILE DB & AGENDA SEARCH

After a run (or network run), profiles can be stored in a SQLite DB and queried by **agenda** — a descriptive query for research or product understanding (e.g. "interested in X", "susceptible to framing Y"). Returns a **ranked list** of matching profiles, not a single "best" target.

- **Storage:** Use `--db path` with `build_site.py` or `python -m holespawn.network ... -o report.json --db path` to write to SQLite (default path: `outputs/holespawn.sqlite`). Or manually: `python -m holespawn.db store path/to/run_dir --db path`.
- **Search:** `python -m holespawn.db search --agenda "descriptive query" [--db path] [--limit N]` — uses the LLM to rank stored profiles by relevance to the agenda. Output: JSON array of `{run_id, output_dir, source_username, rank, reason}`.

**CLI:**
```bash
# Init DB (optional; store will create if missing)
python -m holespawn.db init --db outputs/holespawn.sqlite

# Store a run dir (or use --db when building)
python -m holespawn.db store outputs/20260201_120000_username --db outputs/holespawn.sqlite

# Search by agenda (requires LLM API key)
python -m holespawn.db search --agenda "interested in AI safety and rationalism" --limit 10
```

---

## DASHBOARD

Web UI for research and operations: profile/agenda/network browsing, target management, trap generation, campaigns, and visit tracking.

```bash
# Initialize and start
python -m dashboard init-db
python -m dashboard serve

# Background worker (separate terminal, for job queue)
python -m dashboard worker
```

Access: **http://localhost:5000** (login with any passphrase in dev when `DASHBOARD_PASSPHRASE` is not set).

- **Profiles / agenda search:** Stored profiles, LLM-ranked agenda search, engagement briefs, network reports.
- **C2:** Targets, traps, campaigns, intel, visit tracking; worker runs trap generation and deployment jobs.

DB: `HOLESPAWN_DB` env or default `outputs/holespawn.sqlite`. Full documentation: [docs/C2_DASHBOARD.md](docs/C2_DASHBOARD.md).

---

## AUTONOMOUS COGNITIVE OPERATIONS

**SEITHAR PROTOCOL: UNSUPERVISED SUBSTRATE MANIPULATION**

The system supports autonomous operation mode for extended engagement cycles without operator intervention.

### INVOCATION
```bash
python -m holespawn.agent.cli run \
  --goal "operational_objective" \
  --criteria '{"threshold_parameters": "values"}' \
  --data substrate_manifest.json \
  --model inference_backend
```

### OPERATIONAL SEQUENCE

**Cycle 1-3: Matrix Construction**
- Subject behavioral pattern extraction (n=10-50)
- Network graph topology analysis
- Vulnerability surface mapping
- Temporal engagement windows identification

**Cycle 4-7: Initial Contact Protocol**
- Platform-native communication channel utilization
- Subject-matched linguistic pattern deployment
- Baseline rapport establishment
- Response probability assessment

**Cycle 8-12: Architecture Integration**
- Subject-specific binding structure synthesis
- Deployment infrastructure provisioning
- Distribution vector selection
- Link transmission via established trust channels

**Cycle 13-17: Metric Collection**
- Engagement depth quantification
- Session duration measurement
- Return frequency observation
- Binding effectiveness scoring (0-100 scale)

**Cycle 18-20: Parametric Refinement**
- Conversion funnel analysis (contact → response → visit → binding)
- Framing protocol efficacy assessment
- Subject typology → architecture mapping
- High-performing pattern identification and replication

### ENGAGEMENT INFRASTRUCTURE

System requires authenticated platform access:
```bash
# Discord
export DISCORD_BOT_TOKEN="authentication_credential"

# Twitter/X
export TWITTER_API_KEY="credential_1"
export TWITTER_API_SECRET="credential_2"
export TWITTER_ACCESS_TOKEN="credential_3"
export TWITTER_ACCESS_SECRET="credential_4"

# Inference
export ANTHROPIC_API_KEY="credential_5"
# Or local: LLM_API_BASE, LLM_MODEL

# Database
python -m dashboard init-db
```

### CONTACT VECTORS

| Vector | Platform | Function |
|--------|----------|----------|
| Direct messaging | Discord, Twitter | 1:1 communication channel |
| Public reply | Twitter | Social proof mechanism |
| Channel participation | Discord | Context integration |
| Activity monitoring | Both | Temporal synchronization |

**Linguistic Optimization:** Vocabulary matching, syntax pattern replication, interest domain alignment, vulnerability hook activation.

**Psychological Framing Protocols:** Mystery (information gap), Curiosity (incomplete pattern), Social proof (network consensus), Scarcity (limited access), Direct (minimal friction).

### EFFECTIVENESS METRICS

- **Contact Success Rate (CSR)** = responses / messages_sent — target CSR > 0.50
- **Binding Conversion Rate (BCR)** = trap_visits / contacts_responded — target BCR > 0.60
- **Effectiveness Score (ES)** = Σ(session_duration, page_depth, return_frequency) on 0-100 scale — target ES > 70

### LEARNING FUNCTION

Agent extracts patterns across iterations: profile type → optimal framing, temporal → contact timing, network position → strategy selection. Output: refined message parameters, framing weights, architecture optimization vectors, subject prioritization scores.

### CONFIGURATION SCHEMA

Success criteria (JSON): `minimum_effectiveness_score`, `minimum_successful_bindings`, `minimum_contact_response_rate`, `minimum_visit_conversion_rate`. Operational parameters: `maximum_cycles` (default 20), platforms.

### OPERATIONAL CONSTRAINTS

**Technical:** Platform rate limits (Discord, Twitter). LLM and storage scale with subject count.

**Methodological:** Subject consent not architecturally enforced. Platform ToS not programmatically validated. Ethical oversight not implemented in base configuration.

**Legal:** Jurisdiction-dependent. Platform policy compliance user-specified.

### SYSTEM BEHAVIOR

The autonomous agent executes complete operational cycles without human supervision. Subject interaction, architecture generation, deployment, and effectiveness assessment proceed automatically until success thresholds are met or cycle limit is reached. All engagement is recorded; all deployments logged; all metrics quantified.

Complete technical documentation: [docs/AUTONOMOUS_OPERATIONS.md](docs/AUTONOMOUS_OPERATIONS.md).

**FIELD DATA:** Test phase ongoing. Cycle stability confirmed. Learning function operational. Unsupervised execution stable. Mechanism awareness does not prevent mechanism efficacy.

認知作戦

---

## APPROVED USAGE

- Self-analysis
- Consenting subjects only

This demonstrates mechanisms employed by dominant platforms.

Transparency doctrine: offense requires secrecy, defense requires awareness.

---

## FIELD NOTES

Testing phase: active.

Preliminary observations:
- Subject awareness does not prevent binding
- Architecture adaptation successful
- Cross-subject patterns identified

Knowledge ≠ immunity.

---

## ABOUT SEITHAR GROUP

The Seithar Group operates at the convergence of neuro-physiology, narrative topology, and algorithmic governance.

Our methodology: binding and shaping of informational threads.

[seithar.com](https://seithar.com)

認知作戦
