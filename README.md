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
