# MISSION.md — HoleSpawn (穴卵)

**Status:** Operational  
**Last Updated:** 2026-02-19

## Purpose

Cognitive substrate profiling platform. Ingest social media output → construct psychological profiles → map vulnerability surfaces → generate personalized engagement architectures. Network analysis maps communities, bridge nodes, and key-node profiles.

## Architecture

### Seithar Unified Pipeline (`seithar/`)

The `seithar` package is the orchestration layer wrapping all Seithar ecosystem repos into a single importable pipeline:

```
Profile → Scan → Plan → Arm → Deploy → Measure → Evolve
```

```python
from seithar import SeitharPipeline
pipeline = SeitharPipeline()
results = pipeline.run("target_handle")
```

**Package structure:**
- `seithar/__init__.py` — Entry point, exports `SeitharPipeline`
- `seithar/pipeline.py` — `SeitharPipeline` orchestrator class
- `seithar/taxonomy.py` — **Single source of truth** for SCT-001 through SCT-012 (dataclass-based)
- `seithar/stages/profile.py` — Wraps holespawn.scraper, network, profile
- `seithar/stages/scan.py` — Wraps seithar-cogdef scanner (local patterns + LLM)
- `seithar/stages/plan.py` — Wraps ThreadMap chain modeling
- `seithar/stages/arm.py` — Payload generation via holespawn.generator
- `seithar/stages/deploy.py` — Delivery via holespawn.delivery + moltbook
- `seithar/stages/measure.py` — Wraps influence_flow + temporal analysis
- `seithar/stages/evolve.py` — Feedback loop, taxonomy weight updates

**Design principles:**
- `seithar/` wraps existing modules — does not move or break them
- `holespawn/` continues to work independently
- External repos (cogdef, ThreadMap, autoprompt) imported when available, graceful fallback otherwise
- Each stage returns a typed dataclass; pipeline captures errors without halting

## Current State

### Working
- Core profiling pipeline: ingest → NLP → LLM profile → behavioral matrix → engagement architecture
- SCT integration: algorithmic SCT-001 through SCT-012 vulnerability mapping (`holespawn.sct`)
- Network analysis v2: community detection, bridge identification, node profiling
- Network analytical engine v3: graph_builder (weighted/temporal digraphs), influence_flow (seeding/amplification/bridges/composite scores), vulnerability (fragmentation/SPOFs/cohesion/attack surfaces), temporal (snapshot diff/community evolution/trends), content_overlay (topic mapping/belief clustering/narrative divergence/sentiment flow)
- Network operational engine v4: NetworkEngine orchestration (OperationalNode profiles with role classification, influence path finding with bottleneck detection, operation planning with amplification chains, gatekeeper detection, snapshot comparison). CLI: `python3 -m holespawn.network engine {analyze,paths,plan,compare}`
- NLP pipeline: 200+ stopwords, 7 communication style categories, improved theme extraction
- Delivery system v1: profile + binding protocol → LLM message → file/stdout
- Recording daemon: scheduled Twitter snapshots into timestamped JSON + SQLite index
- Temporal NLP: VADER + theme extraction per time window, influence signatures
- Cohort analysis plumbing: per-subject series + cohort aggregation
- Rust TUI: profile browser, network graph, comparison, recording tab
- Self-hosted scraper: Playwright-based Twitter collection (in repo)

### Active
- Deep network scrape of @gOPwbi7qqtWeD9o (Mirai Junsei) with D3.js visualization
- Scraper integration: convenience `from_twitter(username)` function
- Delivery channel integration, CLI `--sct` flag

- Community Archive integration: CommunityArchiveSource adapter ingests 17M+ tweets from community-archive.org Supabase API into graph_builder format. Self-quote filtering in influence_flow adopted from memetic-lineage. Conversation tree reconstruction with O(1) adjacency maps.

### Queued
1. Live delivery channels (Twitter DM, Discord, email)
2. Cohort delivery (inner-circle aggregate engagement)
3. TUI Trends tab (sparklines, drift visualization)
4. TUI alerting (Discord webhook for anomaly detection)

## Recent Changes

| Date | Change |
|------|--------|
| 2026-02-11 | NLP overhaul: 7 comm styles, 200+ stopwords, numeric filtering |
| 2026-02-11 | SCT module: mapper, enhancer, report generator (812 lines) |
| 2026-02-11 | Field tests FT-001 (@schneierblog) + FT-002 (@SwiftOnSecurity) |
| 2026-02-11 | Bug fixes: interest threshold, delivery type error, style misclassification |
| 2026-02-11 | README rewrite: cleaner structure, moved spec details to docs/ |
| 2026-02-10 | Delivery system v1, recording tab, temporal NLP, cohort plumbing |

## Dependencies

Python 3.9+, Anthropic API, VADER/NLTK, NetworkX, Playwright, SQLite. Rust toolchain for TUI.

| 2026-02-18 | Network analytical engine v3: graph_builder, influence_flow, vulnerability, temporal, content_overlay |
| 2026-02-18 | Dual-substrate upgrade: SCT-008/009 physical substrate techniques integrated |
| 2026-02-18 | Taxonomy v2.0 propagated across all Seithar repos |
| 2026-02-18 | Cross-repo shared config and monitoring hooks added to ecosystem |
| 2026-02-19 | Seithar unified pipeline package created (seithar/) — 7-stage orchestration layer |
| 2026-02-19 | Canonical SCT taxonomy as dataclasses in seithar/taxonomy.py (single source of truth) |
| 2026-02-19 | 18 pipeline tests passing (tests/test_pipeline.py) |
| 2026-02-19 | Community Archive adapter: CommunityArchiveSource in network/, self-quote filtering in influence_flow, conversation tree reconstruction |
| 2026-02-19 | NetworkEngine v4: operational orchestration layer — node profiling, influence paths, operation planning, snapshot diffing, gatekeeper detection |
| 2026-02-19 | Engine CLI: `python3 -m holespawn.network engine {analyze,paths,plan,compare}` |
| 2026-02-19 | 27 engine tests + all existing tests passing (197+ total) |
