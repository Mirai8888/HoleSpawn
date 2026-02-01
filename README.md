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

Web UI to browse stored profiles, run agenda search, and view network reports and briefs.

**Run:**
```bash
pip install flask
python -m dashboard.app
```
Then open http://127.0.0.1:5000

- **Profiles:** List all stored profiles (run_id, username, created_at, source). Click **Brief** to open the engagement brief in a modal.
- **Agenda search:** Enter a descriptive query and optional limit; uses the LLM to rank profiles. Results show rank, reason, and link to brief.
- **Network reports:** List stored network analysis runs. Click **Brief** to view the network engagement brief.

DB path: `HOLESPAWN_DB` env or default `outputs/holespawn.sqlite` (relative to project root).

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
