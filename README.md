# HoleSpawn (穴卵)

**SEITHAR GROUP RESEARCH DIVISION**  
**COGNITIVE SUBSTRATE PROFILING PLATFORM**

---

## Overview

HoleSpawn is a cognitive substrate analysis platform. It ingests social media output, constructs psychological profiles, maps vulnerability surfaces, and generates personalized engagement architectures.

The system models how influence operations work by building the tools that execute them. Offensive capability demonstrated openly enables defense.

**Pipeline:** Ingest → NLP Analysis → LLM Synthesis → Behavioral Matrix → Engagement Architecture

---

## Capabilities

| Module | Function |
|--------|----------|
| `holespawn.profile` | Behavioral matrix construction from textual substrate |
| `holespawn.sct` | SCT-001 through SCT-012 vulnerability surface mapping |
| `holespawn.network` | Social graph analysis, community detection, bridge identification |
| `holespawn.delivery` | Personalized engagement message generation |
| `holespawn.scraper` | Self-hosted Playwright-based Twitter/X data collection |
| `holespawn.temporal` | Time-series NLP: sentiment drift, topic evolution, influence signatures |
| `holespawn.record` | Continuous surveillance daemon with SQLite index |
| `holespawn.site_builder` | Trap architecture generation (rabbit holes, ARGs) |
| `holespawn.nlp` | VADER sentiment, theme extraction, communication style classification |

---

## Quick Start

```bash
git clone https://github.com/Mirai8888/HoleSpawn
cd HoleSpawn
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env    # Add ANTHROPIC_API_KEY
cp subjects.yaml.example subjects.yaml

# Profile a target
python -m holespawn.engagement --target @handle

# SCT vulnerability scan
python -c "
from holespawn.sct.mapper import SCTMapper
from holespawn.sct.report import generate_sct_report
mapper = SCTMapper()
# Pass behavioral_matrix from profile step
report = generate_sct_report(behavioral_matrix, '@target')
print(report)
"

# Network analysis
python -m holespawn.network --target @handle

# Start recording daemon
python -m holespawn.record --config subjects.yaml
```

---

## SCT Integration

HoleSpawn integrates the Seithar Cognitive Defense Taxonomy for vulnerability surface mapping.

| Component | Function |
|-----------|----------|
| `sct.mapper` | Algorithmic SCT-001 through SCT-012 vulnerability scoring (no LLM required) |
| `sct.enhancer` | LLM-enhanced engagement strategy optimization using SCT vulnerability data |
| `sct.report` | Standalone vulnerability reports with ASCII heatmap visualization |

**Field-tested** against real targets. Correctly differentiates high-resistance analytical profiles (susceptibility 0.05) from emotionally reactive profiles (0.69+ on SCT-001).

---

## Network Analysis

Social graph exploitation pipeline:

1. **Collection** — Scrape follower/following lists, bios, recent posts
2. **Graph Construction** — Build directed social graph with edge weights
3. **Community Detection** — Identify clusters via modularity optimization
4. **Bridge Identification** — Find accounts connecting otherwise separate communities
5. **Node Profiling** — Behavioral matrix for key nodes (inner circle, bridges, influencers)
6. **Vulnerability Mapping** — SCT scoring across the network

Modules: `holespawn.network.node_profiler`, `holespawn.network.vulnerability_map`

---

## Architecture

```
              INPUTS
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 Twitter     Discord      File/
 Archive     Export       Scraper
    │           │           │
    └───────────┼───────────┘
                ▼
            INGEST
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 PROFILE       NLP       NETWORK
 analyzer    (VADER,     graph,
 build       themes,     community,
 profile     styles)     bridges
    │           │           │
    └───────────┼───────────┘
                ▼
         LLM SYNTHESIS
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 Behavioral   Binding     Network
 Matrix       Protocol    Report
                │
                ▼
         SCT MAPPING
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 Vulnerability Engagement  Delivery
 Report       Strategy    Message
                │
                ▼
         TUI / DASHBOARD
```

---

## Communication Style Classification

7-category system derived from linguistic pattern analysis:

| Style | Indicators |
|-------|-----------|
| Technical/Insider | Domain jargon density, specification references |
| Analytical/Observational | Hedging language, evidence citation, conditional reasoning |
| Passionate/Advocacy | Intensifiers, imperative mood, value-laden framing |
| Humorous/Irreverent | Absurdist construction, tonal subversion, self-deprecation |
| Authoritative/Declarative | Assertion density, minimal hedging, prescriptive framing |
| Community/Collaborative | Inclusive pronouns, consensus-seeking, question frequency |
| Cryptic/Conspiratorial | Coded language, implicature, in-group signaling |

---

## Documentation

Detailed specifications in `docs/`:

| Document | Content |
|----------|---------|
| [Autonomous Operations](docs/AUTONOMOUS_OPERATIONS.md) | Agent execution cycles, metrics, learning functions |
| [C2 Dashboard](docs/C2_DASHBOARD.md) | Web dashboard for campaign management |
| [Discord Ingest](docs/DISCORD_INGEST.md) | Discord server analysis pipeline |
| [Local Models](docs/LOCAL_MODELS.md) | Self-hosted LLM configuration |
| [Design System](docs/DESIGN_SYSTEM_REFACTOR.md) | UI/UX specifications |

---

## Field Test Results

| Target | Susceptibility | Top SCT Vector | Delivery Theme |
|--------|---------------|-----------------|----------------|
| @schneierblog | 0.05 | SCT-002 (Information Asymmetry) | AI prompt injection research |
| @SwiftOnSecurity | 0.05 | SCT-005 (Identity Targeting) | Automotive paint chemistry |

Low susceptibility scores indicate high-resistance analytical profiles. System correctly identifies that these targets require specialized, domain-native approach vectors rather than generic emotional manipulation.

---

## Ecosystem

| System | Function | Repository |
|--------|----------|-----------|
| **HoleSpawn** | Cognitive substrate profiling (offense) | This repo |
| seithar-cogdef | Cognitive Threat Scanner (defense) | [Mirai8888/seithar-cogdef](https://github.com/Mirai8888/seithar-cogdef) |
| ThreatMouth | Threat intelligence feed | [Mirai8888/ThreatMouth](https://github.com/Mirai8888/ThreatMouth) |
| seithar-research | Research publications | [Mirai8888/seithar-research](https://github.com/Mirai8888/seithar-research) |
| ThreadMap | Hybrid operation chain modeling | [Mirai8888/ThreadMap](https://github.com/Mirai8888/ThreadMap) |

---

## Usage Restrictions

System demonstrates mechanisms employed by platform operators at scale.

**Transparency Doctrine:**  
Offensive capability requires operational secrecy.  
Defensive capability requires mechanism awareness.  
Knowledge of mechanism ≠ immunity to mechanism.

Subject awareness does not prevent binding efficacy. Architecture adaptation: successful across subject types.

---

## CONNECT

| Channel | Link |
|---------|------|
| Discord | [discord.gg/MktZyb2bvx](https://discord.gg/MktZyb2bvx) |
| Mirai Junsei (未来純正) | [x.com/gOPwbi7qqtWeD9o](https://x.com/gOPwbi7qqtWeD9o) |
| Seithar Group | [x.com/SeitharGroup](https://x.com/SeitharGroup) |
| Research Archive | [seithar.substack.com](https://seithar.substack.com) |
| Website | [seithar.com](https://seithar.com) |
| GitHub | [github.com/Mirai8888](https://github.com/Mirai8888) |

────────────────────────────────────────────────────
Seithar Group Intelligence & Research Division  
認知作戦 | seithar.com
────────────────────────────────────────────────────
