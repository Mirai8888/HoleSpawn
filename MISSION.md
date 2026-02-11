# MISSION.md

## Project: HoleSpawn (穴卵)
## Status: Operational

### What This Does
Cognitive substrate analysis: profiles individuals' psychological vulnerabilities from social media (Twitter/X), generates behavioral matrices, binding protocols (approach strategies), and personalized trap architectures. Network analysis maps inner circles, communities, bridge nodes, and key-node profiles. Aligns conceptually with susceptibility-screening and narrative-targeting mechanisms (see `docs/RESEARCH_CONTEXT.md`); models them for defensive visibility.

### Current State
- Core profiling pipeline works (ingest → NLP → LLM profile → site generation).
- Network analysis v2: community detection, bridge identification, node profiling, vulnerability mapping.
- Recording daemon (Phase 2): scheduled snapshots of Twitter handles into timestamped JSON + SQLite index.
- Rust TUI: profile browser, network graph, side-by-side comparison, live build monitor, run-pipeline flow.
- Self-hosted scraper (holespawn/scraper/): Playwright-based replacement for Apify (in repo; integration state TBD).
- Apify dump import path exists (holespawn/ingest/apify_dump_import.py) for salvaging existing Apify data.
- Output cleanup: scripts/clean_outputs.py enforces binding_protocol.md, dedupes by username, removes temp profiles dir and repo-wide temp files.

### Active Work
- SCT integration complete (2026-02-11). Next: delivery channel integration, CLI --sct flag.

### Queued
1. HoleSpawn scraper — replace Apify with self-hosted Playwright scraper (spec: holespawn_scraper_spec.md); currently not working, do not block on it.
2. ~~Salvage Apify data~~ — done.
3. ~~Phase 3: Temporal NLP~~ — done (see Completed).
4. ~~Phase 4: Cohort analysis~~ — inner-circle aggregation plumbing done (see Completed); network integration + LLM synthesis TBD.
5. ~~Phase 5: TUI integration~~ — Recording tab done (see Completed); Trends tab (sparklines, drift) TBD.
6. **Delivery system** — v1 done: profile + binding protocol → LLM message → file/stdout (see Completed). Queued: live channels (Twitter/Discord/email), cohort delivery.
7. Rust TUI refinements per holespawn_tui_spec.md.

### Completed
- **SCT Integration** (2026-02-11): `holespawn.sct` module — algorithmic SCT-001 through SCT-012 vulnerability mapping from behavioral matrices (no LLM), LLM-enhanced engagement optimization, standalone vulnerability report generator with heatmap. Integrated into engagement.py via `sct_enhance=True`. Tests: `tests/test_sct.py`.
- **Delivery system v1** (2026-02-10): `holespawn.delivery` — generate one tailored message from existing run (behavioral_matrix + binding_protocol) via LLM; deliver to `file` or `stdout`. CLI: `python -m holespawn.delivery --output-dir outputs/... --channel file --out delivery_out`. Design: `docs/DELIVERY_DESIGN.md`. Live send (Twitter/Discord/email) not implemented; channel stubs return text only.
- **Phase 5: Recording tab** (2026-02-10): TUI tab [5] Recording shows subjects from recordings.db (subject_id, last_timestamp, snapshot_count, record_count). Data from `python -m holespawn.temporal --list-subjects`; refreshed when entering tab. Python CLI extended with `--list-subjects` (JSON to stdout). Rust: `View::Recording`, `data/recordings.rs` (fetch_recordings_summary), `ui/recording.rs`.
- **Phase 4: Cohort analysis plumbing** (2026-02-10): `holespawn.temporal.cohort` — `build_cohort_results(recordings_dir, subject_ids, ...)` (per-subject series + signatures) and `aggregate_cohort(cohort_results)` (cohort-level time series + drift signature). No LLM; ready for inner-circle wiring from network analysis and later Claude summarization. Tests: `tests/test_temporal_cohort.py`.
- **Phase 3: Temporal NLP** (2026-02-10): `holespawn.temporal` — `list_recordings`, `list_subjects`, `build_series` (VADER + theme extraction per snapshot), `compute_signature` (sentiment shift, vocabulary drift, topic drift). CLI: `python -m holespawn.temporal --subject @handle [--recordings-dir recordings] [--output trends.json]`. Added `list_subjects()` for TUI Recording tab. Tests: `tests/test_temporal.py`.
- Output cleanup: TUI scanner requires binding_protocol.md (or binding.md), dedupes by username, skips temp "profiles" dir.
- `scripts/clean_outputs.py`: require binding_protocol.md per profile, remove duplicates (keep newest per username), remove outputs/profiles, repo-wide temp cleanup (__pycache__, .pytest_cache, logs, .cache, *.pyc).
- `outputs/CLEANUP.bat` removed (replaced by Python script).

### Known Issues
- None recorded. Apify dependency still in use until self-hosted scraper is fully integrated.

### Dependencies
- Python 3.x, Claude API (LLM). Apify for Twitter scraping (being replaced). VADER + NLTK, NetworkX. Rust toolchain for TUI. Optional: SQLite (recording, db store).

### Last Updated
2026-02-10 — Phase 5 Recording tab added to TUI; temporal CLI --list-subjects; push.
