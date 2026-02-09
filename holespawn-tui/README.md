# HoleSpawn TUI (穴卵端末)

Terminal UI for HoleSpawn cognitive profiling and network analysis output. View behavioral matrices, binding protocols, and network data in the terminal.

## Build

```bash
cargo build --release
```

## Run

```bash
# Scan default outputs/ directory
cargo run

# Or specify output directory
cargo run -- /path/to/holespawn/outputs
```

## Usage

- **j / Down** — Next profile
- **k / Up** — Previous profile
- **Enter** — Full profile view
- **b** — Binding protocol (binding_protocol.md)
- **n** — Network view (network_analysis.json summary)
- **c** — Compare (placeholder)
- **?** — Help
- **q** — Quit
- **Esc** — Back to browser

## Input

The TUI reads HoleSpawn output directories. Each subdirectory named `YYYYMMDD_HHMMSS_username` is treated as one profile. It loads:

- `behavioral_matrix.json` — psychological profile
- `binding_protocol.md` — engagement brief
- `network_analysis.json` — graph data (when present)

The TUI does not run the Python pipeline; run `python -m holespawn.build_site @user` (or with `--network`) first, then point the TUI at the output directory.
