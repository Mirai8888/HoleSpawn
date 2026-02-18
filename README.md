# HoleSpawn (穴卵)

**Cognitive Substrate Profiling Platform**

Ingests social media output, constructs psychological profiles, maps vulnerability surfaces, and generates personalized engagement architectures.

## Architecture

```
Social media ingest → NLP pipeline → LLM profiling → Behavioral matrix → Engagement architecture
```

## Features

- **Profiling pipeline** -- Communication style analysis, theme extraction, vulnerability mapping
- **SCT integration** -- Maps to Seithar Cognitive Threat taxonomy (SCT-001 through SCT-012)
- **Network analysis** -- Community detection, bridge identification, key-node profiling
- **Delivery system** -- Profile + binding protocol = personalized messaging
- **Recording daemon** -- Scheduled social media snapshots with temporal analysis
- **Rust TUI** -- Terminal interface for profile browsing, network graphs, comparisons

## Install

```bash
git clone https://github.com/Mirai8888/HoleSpawn.git
cd HoleSpawn
pip install -e .
```

## Configuration

```bash
cp .env.example .env          # API keys (Anthropic, etc.)
cp subjects.yaml.example subjects.yaml  # Target configuration
```

## Usage

```bash
# Profile a target
python -m holespawn profile --target <username>

# Network analysis
python -m holespawn network --community <name>

# Run tests
pytest tests/
```

## Requirements

- Python 3.9+
- Anthropic API key (for LLM profiling)
- Playwright (for browser-based scraping)
- Rust toolchain (optional, for TUI)

## Project Structure

```
holespawn/
  scraper/     Social media ingestion (Twitter, Reddit, Discord, etc.)
  nlp/         Text analysis and feature extraction
  profiler/    LLM-powered psychological profiling
  delivery/    Engagement architecture generation
  network/     Community detection and graph analysis
  recording/   Temporal snapshot daemon
  c2/          Dashboard and management
dashboard/     Web dashboard (Flask)
holespawn-tui/ Terminal interface (Rust)
```

## Related

- [seithar](https://github.com/Mirai8888/seithar) -- Unified Seithar platform
- [seithar-cogdef](https://github.com/Mirai8888/seithar-cogdef) -- Cognitive defense (defensive counterpart)
- [ThreatMouth](https://github.com/Mirai8888/ThreatMouth) -- Threat intelligence bot

## License

MIT

---

Seithar Group Research Division | seithar.com
