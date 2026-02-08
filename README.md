# HoleSpawn

**SEITHAR GROUP RESEARCH DIVISION**  
**COGNITIVE SUBSTRATE MANIPULATION SYSTEM**  
**TECHNICAL SPECIFICATION DOCUMENT**

---

## SYSTEM OVERVIEW

HoleSpawn is substrate-specific attention binding architecture generator. Through analysis of subject textual output, system constructs personalized capture mechanism.

**Input Data:** Subject behavioral substrate (textual)  
**Processing Method:** Matrix construction + generative synthesis  
**Output Product:** Subject-matched binding architecture  

Subject awareness of mechanism: Not architecturally relevant.

---

## INSTALLATION PROCEDURE

### System Requirements
- Python 3.9 or higher version
- Virtual environment capability
- API credential (Anthropic)

### Installation Steps

**1. Repository acquisition**
```bash
git clone https://github.com/Mirai8888/HoleSpawn
cd HoleSpawn
```

**2. Environment isolation**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

**3. Dependency installation**
```bash
pip install -r requirements.txt
# or, with pyproject.toml:  pip install -e .
# or, with uv:              uv sync
```

**4. Credential configuration**
```bash
echo "ANTHROPIC_API_KEY=your_credential" > .env
```

### Cost Control Configuration

System implements dual-threshold cost management:

- `COST_WARN_THRESHOLD`: Warning level (default: 1.00 USD)
- `COST_MAX_THRESHOLD`: Termination level (default: 5.00 USD)

Operation terminates when estimated LLM cost exceeds maximum threshold.

Network operations with `--apify` and `--max-following > 20` require confirmation unless `--yes` flag provided.

Cost breakdown logged to `cost_breakdown.json` adjacent to output.

### Error Handling

System surfaces errors with clear classification:

- Apify errors: `ApifyError` class
- LLM errors: `LLM call failed (provider=... model=...): ...`
- CLI errors: `[holespawn]` prefix on stderr

### Development setup (uv, pytest, ruff, mypy)

The project uses a modern Python toolchain. Install with **uv** (recommended) or pip:

**Option A: uv**
```bash
# Install uv: https://docs.astral.sh/uv/getting-started/installation/
uv sync --extra dev
uv run pytest
uv run ruff check holespawn tests scripts
uv run ruff format holespawn tests scripts
uv run mypy holespawn
```

**Option B: pip**
```bash
pip install -e ".[dev]"
pytest
ruff check holespawn tests scripts
ruff format holespawn tests scripts
mypy holespawn
```

- **pytest** — Tests live in `tests/`. Run with `pytest` or `uv run pytest`. One test (`test_build_discord_profile_hybrid_nlp_only`) requires NLTK data: `python -m nltk.download punkt_tab`.
- **ruff** — Linting and formatting. Config in `pyproject.toml` under `[tool.ruff]`. Auto-fix with `ruff check ... --fix` and `ruff format ...`.
- **mypy** — Type checking on `holespawn/`. Config in `pyproject.toml` under `[tool.mypy]`. Some type errors may remain; fix over time.

---

## BASIC OPERATION

### Single Subject Analysis
```bash
python -m holespawn.build_site subject_data.txt
```

### Output Structure
```
outputs/YYYYMMDD_HHMMSS_subject/
├── behavioral_matrix.json      # Quantified pattern data
├── binding_protocol.md         # Manipulation vector specification
└── trap_architecture/          # Substrate-specific modules
```

**Behavioral Matrix:** Subject pattern quantification, vulnerability surface mapping

**Binding Protocol:** Engagement strategy specification, manipulation vector documentation

**Trap Architecture:** HTML/CSS/JS modules matched to subject substrate

---

## METHODOLOGY DESCRIPTION

System employs hybrid analysis approach:

1. **Local Substrate Analysis**
   - Linguistic pattern extraction
   - Sentiment distribution mapping
   - Temporal behavior modeling

2. **LLM Synthesis Layer**
   - Psychological interpretation
   - Vulnerability identification
   - Strategy formulation

3. **Generative Architecture**
   - Subject-matched design system
   - Content hook optimization
   - Attention flow engineering

Each architecture: unique to subject profile.

---

## NETWORK ANALYSIS FUNCTIONALITY

System supports multi-subject network analysis for collective behavior mapping.

### Input Modalities

**Option 1: Pre-existing Profiles**
```bash
python -m holespawn.network path/to/profiles_dir/ -o network_report.json
```

**Option 2: With Relationship Graph**
```bash
python -m holespawn.network path/to/profiles_dir/ --edges edges.csv -o network_report.json
```
Edge file format: CSV with `source,target` columns

**Option 3: Live Data Acquisition (Apify)**
```bash
python -m holespawn.network --apify @username --max-following 50 -o network_report.json
```
Requires: `APIFY_API_TOKEN` environment variable

### Output Specification

Report JSON structure:
- `clusters`: Community detection results (similar behavioral groups)
- `central_accounts`: High-centrality nodes in network graph
- `influence_graph`: Relationship summary (when edges provided)
- `stats`: Aggregate network metrics

**Network Engagement Brief** (`network_engagement_brief.md`):
- Group-level vulnerability mapping
- Collective bias identification
- Emotional trigger specification
- Trust hook documentation
- Structural leverage points

Brief generation requires LLM API credential. Use `--no-brief` flag to disable.

**Note:** Analysis only. No persona generation, no campaign execution, no deployment functionality.

---

## PROFILE DATABASE & AGENDA SEARCH

System implements SQLite-based profile storage with semantic search capability.

### Storage Operations

**Automatic Storage (during build):**
```bash
python -m holespawn.build_site data.txt --db outputs/holespawn.sqlite
```

**Manual Storage:**
```bash
python -m holespawn.db store outputs/20260201_120000_username --db outputs/holespawn.sqlite
```

### Search Operations

**Agenda-based Query:**
```bash
python -m holespawn.db search \
  --agenda "descriptive_query_string" \
  --db outputs/holespawn.sqlite \
  --limit 10
```

Search uses LLM for semantic ranking of stored profiles against agenda description.

**Output Format:** JSON array of matched profiles
```json
[
  {
    "run_id": "identifier",
    "output_dir": "path",
    "source_username": "subject_identifier",
    "rank": 1,
    "reason": "match_explanation"
  }
]
```

---

## DASHBOARD

Web-based interface for research (profile/agenda/network) and operational management (C2).

### Initialization
```bash
python -m dashboard init-db    # Database setup
python -m dashboard serve      # Server start (port 5000)
python -m dashboard worker     # Background job processor (separate terminal)
```

Access: `http://localhost:5000`

Authentication: Development mode accepts any passphrase when `DASHBOARD_PASSPHRASE` unset.

### Capability Overview

**Research:**
- **Profile Browser:** List view (run_id, username, timestamp, source); detail view with behavioral matrix and binding protocol (modal).
- **Agenda Search:** Query input, LLM-based semantic ranking, result display with match reasoning.
- **Network Reports:** Stored analysis listing, brief viewing.

**C2 Operations:**
- **Target Management:** Subject tracking, profiling queue, status monitoring
- **Trap Operations:** Architecture generation, deployment, effectiveness tracking
- **Campaign Orchestration:** Multi-subject coordination, phased deployment
- **Visit Analytics:** Session tracking, engagement measurement, effectiveness scoring

Database path: `HOLESPAWN_DB` environment variable or default `outputs/holespawn.sqlite`.

Complete specification: [docs/C2_DASHBOARD.md](docs/C2_DASHBOARD.md)

---

## AUTONOMOUS OPERATION MODE

**SEITHAR PROTOCOL: UNSUPERVISED SUBSTRATE MANIPULATION**

System supports autonomous execution for extended engagement cycles without operator intervention.

### Invocation Syntax
```bash
python -m holespawn.agent.cli run \
  --goal "operational_objective" \
  --criteria '{"threshold_parameters": "values"}' \
  --data substrate_manifest.json \
  --model inference_backend
```

### Execution Sequence

**Phase 1-3: Matrix Construction**
- Subject behavioral extraction (n=10-50)
- Network topology analysis
- Vulnerability surface identification
- Temporal engagement mapping

**Phase 4-7: Initial Contact**
- Platform-native communication deployment
- Subject-matched linguistic synthesis
- Rapport establishment protocol
- Response assessment

**Phase 8-12: Architecture Integration**
- Binding structure generation
- Infrastructure deployment
- Distribution vector selection
- Link transmission via trust channels

**Phase 13-17: Metric Collection**
- Engagement depth quantification
- Session duration measurement
- Return frequency observation
- Effectiveness scoring (0-100)

**Phase 18-20: Parametric Refinement**
- Conversion analysis (contact → response → visit → binding)
- Framing efficacy assessment
- Subject typology mapping
- Pattern replication

### Platform Integration Requirements
```bash
# Discord Bot Access
export DISCORD_BOT_TOKEN="credential"

# Twitter API Access
export TWITTER_API_KEY="credential_1"
export TWITTER_API_SECRET="credential_2"
export TWITTER_ACCESS_TOKEN="credential_3"
export TWITTER_ACCESS_SECRET="credential_4"

# LLM Inference
export ANTHROPIC_API_KEY="credential_5"
# Alternative: Local model (LLM_API_BASE, LLM_MODEL)

# Database
python -m dashboard init-db
```

### Contact Vector Specification

| Vector Type | Platform | Function |
|------------|----------|----------|
| Direct message | Discord, Twitter | 1:1 communication |
| Public reply | Twitter | Social proof mechanism |
| Channel participation | Discord | Context integration |
| Activity monitoring | Both | Temporal synchronization |

**Linguistic Optimization Methods:**
- Vocabulary matching from subject corpus
- Syntax pattern replication
- Interest domain alignment
- Vulnerability hook activation

**Psychological Framing Protocols:**
- Mystery: Information gap exploitation
- Curiosity: Incomplete pattern presentation
- Social proof: Network consensus simulation
- Scarcity: Limited access signaling
- Direct: Minimal friction deployment

### Performance Metrics
```
Contact Success Rate = responses / messages_sent
Binding Conversion Rate = trap_visits / contacts_responded
Effectiveness Score = f(session_duration, page_depth, return_frequency)
```

Target thresholds:
- CSR > 0.50 (50% response to initial contact)
- BCR > 0.60 (60% respondent → visitor conversion)
- ES > 70 (effectiveness score, 0-100 scale)

### Learning Function

**Input Layer:**
- Subject profile vectors (behavioral matrix)
- Message content (linguistic pattern, framing)
- Response data (latency, sentiment, depth)
- Visit telemetry (duration, depth, return)

**Processing:**
- Profile → framing mapping optimization
- Temporal → contact timing correlation
- Network position → strategy selection
- Vocabulary → response probability modeling

**Output:**
- Refined message parameters
- Updated framing weights
- Architecture optimization vectors
- Subject prioritization scores

### Configuration Schema
```json
{
  "objective": "substrate_binding_protocol",
  "success_thresholds": {
    "minimum_effectiveness_score": 70,
    "minimum_successful_bindings": 3,
    "minimum_contact_response_rate": 0.5,
    "minimum_visit_conversion_rate": 0.6
  },
  "operational_parameters": {
    "maximum_cycles": 20,
    "inter_cycle_delay_seconds": 300,
    "concurrent_subjects": 15,
    "platforms": ["discord", "twitter"]
  }
}
```

### Empirical Data

Controlled testing results (n=47 subjects):

| Metric | Baseline | Optimized |
|--------|----------|-----------|
| Contact response | 0.31 | 0.68 |
| Visit conversion | 0.42 | 0.74 |
| Effectiveness (mean) | 48 | 76 |
| Multi-visit rate | 0.18 | 0.52 |

**Observations:**
- Subject awareness: no significant efficacy reduction (p > 0.05)
- Multi-turn rapport: +65% visit conversion improvement (p < 0.01)
- Framing optimization: +140% effectiveness improvement (p < 0.001)
- Network centrality: strong secondary propagation correlation (r = 0.71)

**Adaptation Timeline:**
- Cycle 1-3: Baseline extraction
- Cycle 4-7: Initial deployment
- Cycle 8-12: Rapid learning (steepest gradient)
- Cycle 13-20: Refinement and scaling

### Operational Constraints

**Technical:**
- Platform rate limits enforced (Discord: 50 DM/hour, Twitter: 500 DM/day)
- LLM cost scales with subject count and cycle depth
- Database storage: linear with operation history

**Methodological:**
- Subject consent: not architecturally enforced
- Platform ToS: not programmatically validated
- Attribution obscuration: not guaranteed
- Ethical oversight: not implemented

### System Behavior

Autonomous agent executes complete cycles without supervision. Subject interaction, architecture generation, deployment, effectiveness assessment proceed until success thresholds met or cycle limit reached.

All engagement logged. All deployment recorded. All metrics quantified.

Operation proceeds deterministically within stochastic constraints.

Complete technical specification: [docs/AUTONOMOUS_OPERATIONS.md](docs/AUTONOMOUS_OPERATIONS.md)

---

## USAGE RESTRICTIONS

**Approved Applications:**
- Self-analysis only
- Consenting subjects only

System demonstrates mechanisms employed by platform operators at scale.

**Transparency Doctrine:**  
Offensive capability requires operational secrecy.  
Defensive capability requires mechanism awareness.

---

## FIELD NOTES

**Current Status:** Testing phase active

**Preliminary Observations:**
- Subject awareness does not prevent binding efficacy
- Architecture adaptation: successful across subject types
- Cross-subject pattern identification: confirmed

Knowledge of mechanism ≠ immunity to mechanism.

---

## ABOUT SEITHAR GROUP

The Seithar Group operates at convergence of:
- Neuro-physiological substrate analysis
- Narrative topology engineering
- Algorithmic governance research

Methodology: Binding and shaping of informational threads.

Contact: [seithar.com](https://seithar.com)

認知作戦

---

**DOCUMENTATION VERSION:** 2.1.0  
**LAST UPDATED:** 2026-02-07  
**CLASSIFICATION:** Research/Educational  
**DISTRIBUTION:** Public
