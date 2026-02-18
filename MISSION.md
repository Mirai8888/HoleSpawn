# MISSION.md — HoleSpawn (穴卵)

**Status:** Operational  
**Last Updated:** 2026-02-11

## Purpose

Cognitive substrate profiling platform. Ingest social media output → construct psychological profiles → map vulnerability surfaces → generate personalized engagement architectures. Network analysis maps communities, bridge nodes, and key-node profiles.

## Current State

### Working
- Core profiling pipeline: ingest → NLP → LLM profile → behavioral matrix → engagement architecture
- SCT integration: algorithmic SCT-001 through SCT-012 vulnerability mapping (`holespawn.sct`)
- Network analysis v2: community detection, bridge identification, node profiling
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

| 2026-02-18 | Dual-substrate upgrade: SCT-008/009 physical substrate techniques integrated |
| 2026-02-18 | Taxonomy v2.0 propagated across all Seithar repos |
| 2026-02-18 | Cross-repo shared config and monitoring hooks added to ecosystem |
