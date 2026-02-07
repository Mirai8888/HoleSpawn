# C2 Dashboard Documentation

## Overview

The C2 Dashboard is a command and control interface for HoleSpawn operations. It provides:

- **Target management** — Add and profile individuals (Discord, Twitter, text)
- **Trap generation** — Build personalized sites from psychological profiles
- **Campaign orchestration** — Multi-target ops with phased rollout
- **Network intelligence** — Community detection, central nodes, effectiveness patterns
- **Visit tracking** — Session and engagement metrics from deployed traps

## Quick Start

### Installation

```bash
pip install -r requirements.txt
python -m dashboard init-db
```

### Running

```bash
# Start dashboard
python -m dashboard serve

# Start background worker (separate terminal)
python -m dashboard worker
```

Access at: **http://localhost:5000**

### First Login

- **Development:** Any non-empty passphrase works when `DASHBOARD_PASSPHRASE` is not set.
- **Production:** Set `DASHBOARD_PASSPHRASE` or `DASHBOARD_PASSPHRASE_HASH` (bcrypt) in the environment.

## Core Concepts

### Targets

Individuals or accounts being profiled and tracked.

**Workflow:**

1. Create target (identifier + platform).
2. Add raw data (Discord export JSON, tweets, or text) via PATCH `/api/targets/<id>` with `raw_data`.
3. Queue profiling job: `POST /api/targets/<id>/profile`.
4. When the worker finishes, review profile in the dashboard or via `GET /api/targets/<id>/profile`.

### Traps

Personalized psychological trap sites generated from profiles.

**Workflow:**

1. Target must be profiled first.
2. Generate trap: queue a `generate_trap` job (or `POST /api/traps` with `target_id` then run worker). Output is written to `outputs/traps/trap_<target_id>_<timestamp>/`.
3. Deploy trap (manual upload or `POST /api/traps/<id>/deploy` for placeholder URL).
4. Monitor visits and effectiveness via dashboard or `GET /api/traps/<id>/analytics`.

### Campaigns

Multi-target operations with coordinated deployment.

**Workflow:**

1. Create campaign: `POST /api/campaigns`.
2. Add targets: `POST /api/campaigns/<id>/targets` with `target_ids`.
3. Configure orchestration (timing, messaging) in campaign config.
4. Start campaign: `POST /api/campaigns/<id>/start`.
5. Monitor aggregate metrics: `GET /api/campaigns/<id>/status`.

### Networks

Network graphs from profile directories (community detection, central nodes).

**Workflow:**

1. Create network: `POST /api/intel/networks` with `dir_path` pointing to a directory of `behavioral_matrix.json` or `profile.json` files.
2. View graph and communities: `GET /api/intel/networks/<id>`.
3. Use central nodes and influence map for targeting.

## API Reference

### Targets

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/targets` | Create target |
| GET    | `/api/targets` | List targets (optional: `?status=`, `platform=`, `tags=`) |
| GET    | `/api/targets/<id>` | Get target |
| PATCH  | `/api/targets/<id>` | Update target |
| DELETE | `/api/targets/<id>` | Archive target |
| POST   | `/api/targets/<id>/profile` | Queue profiling job |
| POST   | `/api/targets/<id>/scrape` | Queue scrape job |
| GET    | `/api/targets/<id>/profile` | Get profile JSON |
| GET    | `/api/targets/<id>/nlp` | Get NLP metrics |

### Traps

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/traps` | Create trap (requires `target_id`) |
| GET    | `/api/traps` | List traps |
| GET    | `/api/traps/<id>` | Get trap |
| PATCH  | `/api/traps/<id>` | Update trap (e.g. `is_active`, `url`) |
| DELETE | `/api/traps/<id>` | Delete trap |
| POST   | `/api/traps/<id>/deploy` | Queue deploy job |
| GET    | `/api/traps/<id>/visits` | Visit history |
| GET    | `/api/traps/<id>/analytics` | Aggregated analytics |
| GET    | `/api/traps/<id>/effectiveness` | Effectiveness score (0–100) |

### Campaigns

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/campaigns` | Create campaign |
| GET    | `/api/campaigns` | List campaigns |
| GET    | `/api/campaigns/<id>` | Get campaign (includes targets) |
| PATCH  | `/api/campaigns/<id>` | Update campaign |
| DELETE | `/api/campaigns/<id>` | Delete campaign |
| POST   | `/api/campaigns/<id>/targets` | Add targets (`target_ids` in body) |
| DELETE | `/api/campaigns/<id>/targets/<target_id>` | Remove target |
| POST   | `/api/campaigns/<id>/start` | Start campaign |
| POST   | `/api/campaigns/<id>/pause` | Pause campaign |
| GET    | `/api/campaigns/<id>/status` | Status and aggregate metrics |

### Intel

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/intel/networks` | List network snapshots |
| POST   | `/api/intel/networks` | Create network (`dir_path`, optional `name`) |
| GET    | `/api/intel/networks/<id>` | Network graph (nodes, edges, communities) |
| GET    | `/api/intel/networks/<id>/communities` | Community detection results |
| GET    | `/api/intel/networks/<id>/central` | Central nodes and influence map |
| GET    | `/api/intel/effectiveness` | Effectiveness-by-architecture patterns |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/jobs` | List jobs (optional: `?status=`, `job_type=`) |
| GET    | `/api/jobs/<id>` | Job status and result |
| POST   | `/api/jobs/<id>/run` | Process one job (run worker inline) |

### Tracking (no auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/track/start` | Record visit start (called by tracker.js) |
| POST   | `/api/track/end` | Record visit end |

## CLI Commands

```bash
python -m dashboard serve              # Start server (default :5000)
python -m dashboard init-db           # Initialize C2 database
python -m dashboard worker            # Start job worker
python -m dashboard import-targets <file>   # Import targets from JSON
python -m dashboard queue-profile <target_id>
python -m dashboard generate-trap <target_id>
python -m dashboard deploy-trap <trap_id>
```

## Job Queue

Background jobs for expensive operations:

| Job type        | Description |
|----------------|-------------|
| `profile`      | Build psychological profile from target `raw_data` (Discord or text). |
| `generate_trap`| Generate trap site from target profile; creates Trap record and files under `outputs/traps/`. |
| `deploy`       | Mark trap as deployed (placeholder URL; wire to Netlify/Vercel as needed). |
| `scrape`       | Stub; add data via API or import. |

Jobs are processed by: `python -m dashboard worker`.

## Visit Tracking

Traps can include `tracker.js`, which sends events to the dashboard:

- Session start/end
- Page views, depth, duration
- Scroll depth, clicks (when implemented in tracker)

Configure the tracker on generated sites:

```html
<script>
  window.HOLESPAWN_TRACKER = { trapId: 1, apiBase: 'http://your-dashboard.com' };
</script>
<script src="http://your-dashboard.com/static/tracker.js"></script>
```

Or use data attributes on the script tag: `data-trap-id`, `data-api-base`.

## Environment Variables

```bash
# Database
DASHBOARD_DB=outputs/c2.sqlite

# Authentication
DASHBOARD_PASSPHRASE=your-secret
# Or bcrypt hash:
# DASHBOARD_PASSPHRASE_HASH=$2b$12$...

# Flask
FLASK_SECRET_KEY=...

# LLM (for profiling)
ANTHROPIC_API_KEY=...
# Or local models:
# LLM_API_BASE=http://localhost:11434/v1
# LLM_MODEL=llama3.1:8b
```

## Security

- Dashboard uses passphrase authentication; all C2 API routes (except `/api/auth/*` and `/api/track/*`) require login.
- All operations are logged to `audit_logs`.
- Set `DASHBOARD_PASSPHRASE` or `DASHBOARD_PASSPHRASE_HASH` in production.

## Tests

```bash
pip install -r requirements.txt pytest
pytest tests/test_c2_dashboard.py -v
```

Tests use a temporary SQLite database (env `DASHBOARD_DB` set by the test module).

## Troubleshooting

**Jobs stuck in `queued`**  
- Ensure the worker is running: `python -m dashboard worker`.

**Profiling fails**  
- Check LLM API keys or local model endpoint.
- Ensure the target has `raw_data` (Discord export with `messages` or text in `raw_data.text`).

**Trap generation fails**  
- Target must be profiled first (`GET /api/targets/<id>/profile` returns data).
- Confirm `profile` is present on the target.

**Visit tracking not working**  
- Ensure `tracker.js` is loaded and `trapId` / `apiBase` are set.
- Verify the dashboard URL is reachable from the trap site (CORS if different origin).
