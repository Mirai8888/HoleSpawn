# HoleSpawn (穴卵)

**Cognitive Substrate Profiling Platform — Seithar Group**

Ingests social media output, constructs psychological profiles, maps vulnerability surfaces, and generates personalized engagement architectures.

## Architecture

```
Social media ingest → NLP pipeline → LLM profiling → Behavioral matrix → Engagement architecture
```

## Features

- **Profiling pipeline** — Communication style analysis, theme extraction, vulnerability mapping
- **SCT integration** — Maps to Seithar Cognitive Threat taxonomy (SCT-001 through SCT-012)
- **Network analysis** — Community detection, bridge identification, key-node profiling
- **Delivery system** — Profile + binding protocol → personalized messaging
- **Recording daemon** — Scheduled social media snapshots with temporal analysis
- **Rust TUI** — Terminal interface for profile browsing, network graphs, comparisons

## Quick Start

```bash
pip install -e .
cp .env.example .env  # Add API keys
cp subjects.yaml.example subjects.yaml  # Configure targets
python -m holespawn
```

## Dependencies

Python 3.9+, Anthropic API, VADER/NLTK, NetworkX, Playwright, SQLite. Rust toolchain for TUI.

## Related

- [seithar-cogdef](https://github.com/Mirai8888/seithar-cogdef) — Cognitive defense (defensive counterpart)
- [ThreatMouth](https://github.com/Mirai8888/ThreatMouth) — Threat intelligence bot
- [seithar-research](https://github.com/Mirai8888/seithar-research) — Research publications

---

Seithar Group Research Division | 認知作戦 | [seithar.com](https://seithar.com)
