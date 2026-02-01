# HoleSpawn

**An artistic tool that ingests Twitter/X output and generates a personalized "rabbit hole" or ARG experience—including a full website tailored to their psychological profile.**

For entertainment and art only. Use only with **your own data** or with **explicit consent** from the subject.

---

## Concept

1. **Ingest** — Twitter/X only: **Twitter archive ZIP** (recommended) or **Apify scraper** (optional) or a text file.
2. **Profile** — The system analyzes language to build a psychological/behavioral profile: themes, sentiment, rhythm, emotional tone.
3. **Personalize** — The experience is **based on their personal profile**: aesthetic, tone, puzzles vs narrative.
4. **Spawn** — A full website (HTML/CSS/JS) with narrative sections, optional puzzles, and theme-matched aesthetics—ready to deploy. Plus an **engagement brief** (vulnerability map, DM ideas, orchestration plan).

---

## Setup

```bash
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set at least one LLM key:

```bash
set ANTHROPIC_API_KEY=your_key    # Windows
# or: set OPENAI_API_KEY=your_key
# or: set GOOGLE_API_KEY=your_key
```

**Optional:** `config.yaml` in the project root controls LLM provider/model, cost thresholds, output directory, and rate limits. Run once to generate a default `config.yaml` if missing.

---

## Data ingestion (Twitter/X only)

### 1. Twitter archive upload (primary / recommended)

Download your Twitter/X archive from **X Settings → Your account → Download an archive**. You get a ZIP file. Use it as the data source:

```bash
python -m holespawn.build_site --twitter-archive path/to/twitter-archive.zip -o output
```

- The tool parses **data/tweets.js** (and **data/tweets-part0.js**, **tweets-part1.js**, etc.) inside the ZIP.
- It handles the `window.YTD.tweets.part0 = ` wrapper and extracts **full_text** (and created_at/engagement are available in the format; we use full_text for profile building).
- No API key required. Works offline.

### 2. Apify Twitter scraper (optional / backup)

If you prefer not to use an archive, you can use Apify to fetch tweets by username. This requires an **Apify** account and **APIFY_API_TOKEN** (paid/addon).

1. Sign up at [apify.com](https://apify.com), get your API token.
2. Put it in `.env` as `APIFY_API_TOKEN=your_token` or set in the environment.
3. Run:

```bash
python -m holespawn.build_site --twitter-username @username -o output
```

- Uses Apify actor **u6ppkMWAx2E2MpEuF** (Twitter Scraper).
- If `APIFY_API_TOKEN` is not set, the command fails with a clear message; use `--twitter-archive` or a text file instead.

### 3. Text file

One post/tweet per line or blank-line-separated blocks:

```bash
python -m holespawn.build_site data/posts.txt -o output
```

Example files in `data/examples/`: `tech_optimist.txt`, `doomer.txt`, `shitposter.txt` for testing.

---

## Build a full personalized website

Single pipeline: **ingest → profile → AI spec → site → optional deploy**.

```bash
# Twitter archive (recommended)
python -m holespawn.build_site --twitter-archive archive.zip -o output

# Apify (optional, requires APIFY_API_TOKEN)
python -m holespawn.build_site --twitter-username @user -o output

# Text file
python -m holespawn.build_site data/sample_posts.txt -o output
```

- **Output**: With `-o output` you get `index.html`, `styles.css`, `app.js`, **`engagement_brief.md`** (unless `--no-engagement`), **`metadata.json`**, **`profile.json`**, and **`cost_breakdown.json`**. Without `-o`, output goes to **`outputs/YYYY-MM-DD_HHMMSS_username/`** (with a `site/` subfolder for the HTML/CSS/JS). Deploy the site folder to any static host.
- **Cost**: Token usage and estimated cost are printed at the end and saved in `cost_breakdown.json`. Use **`--dry-run`** to preview without making LLM calls.

### Engagement brief

Each build generates **`engagement_brief.md`** in the output folder. It includes:

- **Vulnerability map (social-engineering lens)** — Emotional triggers, trust hooks, resistance points, susceptibilities.
- **DM / interaction ideas** — Concrete angles for opening or deepening contact.
- **Orchestration plan** — Phased rollout (introduce, deepen, land).

Use for art and ARG design only; consent and ethics apply.

### Dry run (no LLM calls)

Preview what would be generated and see an estimated cost:

```bash
python -m holespawn.build_site --twitter-archive archive.zip --dry-run
```

### Deploy

```bash
python -m holespawn.build_site --twitter-archive archive.zip -o output --deploy
```

- If **Netlify CLI** is installed, runs `netlify deploy --dir=output`. Otherwise prints instructions (Netlify Drop, GitHub Pages).

### Other flags

- **`--config my_config.yaml`** — Use a custom config file.
- **`--no-cache`** — Disable profile caching (re-analyze every time).
- **`-v` / `--verbose`** — Debug logging.
- **`--quiet`** — Minimal output (errors only).

---

## Real-time rabbit hole (streaming)

**Template-based (no API key):**
```bash
python -m holespawn.demo
```

**AI-based (personalized style from profile):**
```bash
python -m holespawn.demo --ai
```
Requires an AI API key. Streams fragments; style and tone follow the profile.

---

## API usage

**Full website (Twitter archive):**
```python
from holespawn.ingest import load_from_twitter_archive, SocialContent
from holespawn.profile import build_profile
from holespawn.experience import get_experience_spec
from holespawn.site_builder import get_site_content, build_site

content = load_from_twitter_archive("path/to/archive.zip")
profile = build_profile(content)
spec = get_experience_spec(content, profile)
sections = get_site_content(content, profile, spec)
build_site(spec, sections, "output")
```

**Streaming fragments:**
```python
from holespawn.generator import AIRabbitHoleGenerator
ai_gen = AIRabbitHoleGenerator(content, profile)
for token in ai_gen.stream(interval_sec=2, max_fragments=5):
    print(token, end="", flush=True)
```

---

## Cost tracking

Each run prints token usage and estimated cost (e.g. for Gemini Flash, GPT-4o-mini, Claude). Cost thresholds are configurable in `config.yaml` (`costs.warn_threshold`, `costs.max_cost`). Use `--dry-run` to avoid spending on a full generation.

## Data & Ethics

- **Consent**: Only ingest content you own or have permission to use.
- **Twitter-only**: Use your own archive or Apify with appropriate account access.
- **Artistic use**: Output is procedurally generated fiction, not a clinical or diagnostic tool.

---

## License

Use for art and experimentation. Respect privacy and platform ToS.
