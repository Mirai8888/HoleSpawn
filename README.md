# HoleSpawn

**An artistic tool that ingests a person's social media output and generates a personalized "rabbit hole" or ARG experience—including a full website tailored to their psychological profile.**

For entertainment and art only. Use only with **your own data** or with **explicit consent** from the subject.

---

## Concept

1. **Ingest** — Feed in social posts (text export, pasted content, or structured files).
2. **Profile** — The system analyzes language to build a psychological/behavioral profile: themes, sentiment, rhythm, obsessions, emotional tone.
3. **Personalize** — The experience is **based on their personal profile**: if they like light and airy things, the rabbit hole feels light and airy; if they are puzzle-oriented, it contains puzzles; if they are narrative/emotional, it’s immersive story and found documents.
4. **Spawn** — Generate either:
   - **Real-time fragments** (streaming text), or
   - **A full website** (HTML/CSS/JS) with narrative sections, optional puzzles, and theme-matched aesthetics—ready to deploy.

The result is a rabbit hole made *for* that psyche: personalized aesthetic, tone, and content (puzzles vs narrative vs exploration).

---

## Setup

```bash
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Set an AI API key for personalized experience and website generation:

```bash
set ANTHROPIC_API_KEY=your_key    # Windows
# or: set OPENAI_API_KEY=your_key
```

---

## Build a full personalized website (CLI pipeline)

**Default: interactive scrape from X.com**

Run with no arguments; you are prompted:

1. **Individual (1)** or **Following (2)?** — Scrape this user's tweets only, or also map their audience (who they follow).
2. **Enter x.com user link** — e.g. `https://x.com/username` or just the username.

The tool then scrapes X (via Nitter; no API key) and builds the site. Nitter instances can be down; if so, use a file instead or set `NITTER_INSTANCE` to a working instance URL.

```bash
python -m holespawn.build_site
```

**Or use a file** (no scraping):

```bash
python -m holespawn.build_site data/sample_posts.txt -o output
```

- **Input**: Omit for interactive X scrape, or path to text/JSON file (one post per line or blank-line blocks).
- **Output**: `-o output` writes `index.html`, `styles.css`, and `app.js`. Deploy that folder to any static host.

### Map audience (who they follow → what their audience is susceptible to)

Scroll through someone’s **following** to infer what their audience engages with; the experience spec and content are then shaped to resonate with that.

**Free options (no API keys for following):**

1. **File** — One handle per line (any platform). Export or paste your following list.
   ```bash
   python -m holespawn.build_site data/posts.txt --following-file data/following.txt -o output
   ```

2. **Bluesky** — Public API, no key. Fetches who they follow, then samples recent posts from those accounts.
   ```bash
   python -m holespawn.build_site data/posts.txt --following-bluesky user.bsky.social -o output
   ```

3. **Mastodon** — Free app token from your instance (Preferences → Development). Set `MASTODON_ACCESS_TOKEN`, then:
   ```bash
   python -m holespawn.build_site data/posts.txt --following-mastodon https://mastodon.social,username -o output
   ```

Options: `--audience-sample 30` (how many followed accounts to sample; default 25). `--no-fetch-audience` uses only the handle list (no post fetch).

### Deploy (CLI)

After building, deploy in one step:

```bash
python -m holespawn.build_site data/posts.txt -o output --deploy
```

- If **Netlify CLI** is installed (`npm i -g netlify-cli`), runs `netlify deploy --dir=output`.
- Otherwise prints **free deploy** options: Netlify Drop (drag folder), GitHub Pages, or install Netlify CLI.

The site’s look and content are driven by the subject’s profile (and, when used, audience susceptibility): colors, tone, narrative vs puzzle sections, and copy are all personalized.

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
Streams AI-generated fragments; style and tone follow the profile (e.g. light/airy vs cryptic, puzzle hints vs pure narrative).

---

## API usage

**Full website (personalized, deployable):**
```python
from holespawn.ingest import load_from_file
from holespawn.profile import build_profile
from holespawn.experience import get_experience_spec
from holespawn.site_builder import get_site_content, build_site

content = load_from_file("data/sample_posts.txt")
profile = build_profile(content)
spec = get_experience_spec(content, profile)       # AI: aesthetic, type, sections
sections = get_site_content(content, profile, spec)  # AI: copy, puzzles
build_site(spec, sections, "output")               # Writes index.html, styles.css, app.js
```

**Streaming fragments (personalized):**
```python
from holespawn.generator import AIRabbitHoleGenerator
ai_gen = AIRabbitHoleGenerator(content, profile)
for token in ai_gen.stream(interval_sec=2, max_fragments=5):
    print(token, end="", flush=True)
```

---

## Tools

- **Ingest**: **Scrape X.com** (default): prompt Individual or Following, then x.com link; uses ntscraper (Nitter). No X API key. Or use a file.
- **Profile**: Local NLP (VADER); no API key.
- **Following list**: From X scrape (Following mode), or file, **Bluesky** (no key), **Mastodon** (free app token).
- **Audience posts**: From X scrape (Following mode), or Bluesky public API; no key.
- **Experience + content**: AI (Claude or OpenAI); key from env.
- **Deploy**: Netlify CLI (free) or instructions for Netlify Drop / GitHub Pages.

**Note:** X scraping uses Nitter (ntscraper). Public Nitter instances are often down; if scraping fails, use a file or set `NITTER_INSTANCE` to a working instance.

---

## Data & Ethics

- **Consent**: Only ingest content you own or have permission to use.
- **No scraping by default**: Manual export / paste; Bluesky/Mastodon use official APIs with user consent.
- **Artistic use**: Output is procedurally generated fiction, not a clinical or diagnostic tool.

---

## License

Use for art and experimentation. Respect privacy and platform ToS.
