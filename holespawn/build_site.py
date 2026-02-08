"""
Build a full personalized website from Twitter/X data.
Twitter-only: --twitter-archive (recommended) or --twitter-username (Apify) or file.
Pipeline: ingest -> profile -> AI spec -> site -> optional deploy.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env so API keys are available (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
try:
    from dotenv import load_dotenv
    _env_path = ROOT / ".env"
    if _env_path.exists():
        # Windows often saves .env as UTF-16; try UTF-8 first, then UTF-16
        try:
            with open(_env_path, encoding="utf-8") as f:
                load_dotenv(stream=f)
        except UnicodeDecodeError:
            with open(_env_path, encoding="utf-16") as f:
                load_dotenv(stream=f)
    else:
        load_dotenv(_env_path)
except ImportError:
    pass

from holespawn.cache import ProfileCache
from holespawn.config import load_config
from holespawn.cost_tracker import CostExceededError, CostTracker
from holespawn.errors import ApifyError
from holespawn.ingest import (
    load_from_file,
    load_from_text,
    load_from_twitter_archive,
    fetch_twitter_apify,
    load_from_discord,
    SocialContent,
)
from holespawn.profile import build_profile, PsychologicalProfile
from holespawn.experience import get_experience_spec
from holespawn.site_builder import get_site_content, build_site
from holespawn.site_builder.validator import SiteValidator
from holespawn.site_builder.pure_generator import generate_site_from_profile


def _setup_logging(verbose: bool = False, quiet: bool = False, log_dir: Optional[Path] = None) -> None:
    try:
        from loguru import logger
        logger.remove()
        level = "DEBUG" if verbose else ("ERROR" if quiet else "INFO")
        logger.add(sys.stderr, level=level, format="<level>{message}</level>")
        # Default log file in project root (logs/holespawn_*.log)
        log_root = ROOT / "logs"
        log_root.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_root / "holespawn_{time:YYYY-MM-DD}.log"),
            level="DEBUG",
            rotation="500 MB",
            retention="7 days",
        )
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "generation.log"
            logger.add(str(log_file), level="DEBUG", rotation="10 MB", retention="7 days")
    except ImportError:
        pass


def _log(msg: str) -> None:
    try:
        from loguru import logger
        logger.info(msg)
    except ImportError:
        print(msg, file=sys.stderr)


def _create_output_dir(username: str, base_dir: str = "outputs", use_site_subdir: bool = True) -> Path:
    """Create timestamped output directory: outputs/YYYYMMDD_HHMMSS_username."""
    safe = re.sub(r"[^\w\-]", "_", username.strip().lstrip("@")) or "user"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    output_dir = base / f"{timestamp}_{safe}"
    output_dir.mkdir(parents=True, exist_ok=True)
    if use_site_subdir:
        (output_dir / "trap_architecture").mkdir(exist_ok=True)
    # Record latest run (file instead of symlink for Windows)
    latest_file = base / "latest.txt"
    latest_file.write_text(output_dir.name, encoding="utf-8")
    return output_dir


def _profile_to_dict(profile: PsychologicalProfile) -> dict:
    d = asdict(profile)
    # themes is list[tuple] -> list[list] for JSON
    d["themes"] = [list(t) for t in d["themes"]]
    return d


def _check_api_keys() -> bool:
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return True
    if os.getenv("LLM_API_BASE"):
        return True  # local OpenAI-compatible endpoint
    return False


def _dry_run(
    content: SocialContent,
    username: str,
    config: dict,
    provider: Optional[str],
) -> None:
    """Preview generation without LLM calls."""
    _log("DRY RUN — No LLM calls will be made")
    posts = list(content.iter_posts())
    n = len(posts)
    _log(f"Loaded {n} posts")
    if n == 0:
        _log("No posts to analyze. Exiting.")
        return
    _log("Building profile (local only)...")
    profile = build_profile(content)
    themes = [t[0] for t in profile.themes[:5]]
    _log(f"Profile preview: sentiment={profile.sentiment_compound:.2f}, top themes={', '.join(themes)}")
    # Rough cost estimate
    cfg_llm = config.get("llm", {})
    cfg_costs = config.get("costs", {})
    model = cfg_llm.get("model", "gemini-2.5-flash")
    warn = float(cfg_costs.get("warn_threshold", 1.0))
    est_input = min(30_000, sum(len(p) for p in posts) * 2)  # rough tokens
    est_output = 6000  # spec + content + brief
    tracker = CostTracker(model=model, warn_threshold=warn)
    tracker.add_usage(est_input, est_output, operation="estimate")
    est_cost = tracker.get_cost()
    _log(f"Estimated cost: ${est_cost:.4f} (model={model})")
    if est_cost > warn:
        _log(f"Above warning threshold ${warn:.2f}")
    base = config.get("output", {}).get("base_dir", "outputs")
    safe = re.sub(r"[^\w\-]", "_", username.strip().lstrip("@")) or "user"
    _log(f"Output would be: {Path(base).absolute()}/YYYY-MM-DD_HHMMSS_{safe}/")
    _log("Remove --dry-run to generate.")


def _deploy(site_dir: Path) -> None:
    """Run Netlify CLI if available, else print deploy options."""
    netlify = shutil.which("netlify")
    if netlify:
        _log("Running: netlify deploy --dir=" + str(site_dir))
        r = subprocess.run(
            [netlify, "deploy", "--dir", str(site_dir), "--prod"],
            cwd=site_dir,
        )
        if r.returncode != 0:
            _log("Netlify deploy failed. See instructions below.")
    else:
        _log("Netlify CLI not found. Free deploy options:")
        _log("  1. Netlify Drop: drag the site folder to https://app.netlify.com/drop")
        _log("  2. GitHub Pages: push the folder to a repo, Settings -> Pages")
        _log("  3. Install Netlify CLI: npm i -g netlify-cli, then run: netlify deploy --dir=" + str(site_dir))


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HoleSpawn — Build a personalized rabbit hole / ARG website from Twitter/X.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Twitter archive (recommended)
  python -m holespawn.build_site --twitter-archive path/to/twitter-archive.zip

  # Apify (requires APIFY_API_TOKEN)
  python -m holespawn.build_site --twitter-username @username

  # Text file
  python -m holespawn.build_site data/posts.txt

  # Preview without spending money
  python -m holespawn.build_site --twitter-archive archive.zip --dry-run

  # Deploy after build
  python -m holespawn.build_site --twitter-archive archive.zip --deploy

  # Custom config
  python -m holespawn.build_site --twitter-archive archive.zip --config my_config.yaml
""",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to text/JSON file with posts (one per line). Optional if using --twitter-archive or --twitter-username.",
    )
    parser.add_argument(
        "--twitter-archive",
        metavar="PATH",
        default=None,
        help="Path to Twitter/X archive ZIP (recommended).",
    )
    parser.add_argument(
        "--twitter-username",
        metavar="USERNAME",
        default=None,
        help="Twitter/X username (e.g. @user). Uses Apify; requires APIFY_API_TOKEN.",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory. If omitted, uses outputs/YYYYMMDD_HHMMSS_username/.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml).",
    )
    parser.add_argument(
        "--provider",
        choices=("anthropic", "openai", "google"),
        default=None,
        help="AI provider (default: from env / config).",
    )
    parser.add_argument(
        "--discord",
        metavar="PATH",
        default=None,
        help="Path to Discord export JSON. Uses NLP+LLM hybrid profile when set.",
    )
    parser.add_argument(
        "--local-model",
        choices=("ollama-llama3", "ollama-mistral", "lmstudio", "vllm"),
        default=None,
        help="Use a local model preset (OpenAI-compatible API).",
    )
    parser.add_argument(
        "--model-endpoint",
        metavar="URL",
        default=None,
        help="Custom LLM API base URL (e.g. http://localhost:11434/v1 for Ollama).",
    )
    parser.add_argument(
        "--model-name",
        metavar="NAME",
        default=None,
        help="Model name for --model-endpoint or local preset.",
    )
    parser.add_argument(
        "--no-engagement",
        action="store_true",
        help="Skip generating binding_protocol.md.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable profile caching.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making LLM calls or spending money.",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="After building: run Netlify CLI if installed.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Debug logging.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output (errors only).",
    )
    parser.add_argument(
        "--single-page",
        action="store_true",
        help="Use legacy single-page template (default is dynamic multi-page by profile).",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        default=None,
        help="After run: store profile in SQLite (path or dir; default outputs/holespawn.sqlite).",
    )
    return parser


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    _setup_logging(verbose=args.verbose, quiet=args.quiet)

    # Local model: set env so all call_llm use this endpoint
    if args.local_model or args.model_endpoint or args.model_name:
        from holespawn.config import get_llm_config
        llm_cfg = get_llm_config(
            preset=args.local_model,
            api_base=args.model_endpoint,
            model=args.model_name,
        )
        if llm_cfg.get("api_base"):
            os.environ["LLM_API_BASE"] = llm_cfg["api_base"]
        if llm_cfg.get("model"):
            os.environ["LLM_MODEL"] = llm_cfg["model"]

    # Resolve content source and username
    content: Optional[SocialContent] = None
    username = "user"
    discord_data: Optional[dict] = None

    if getattr(args, "discord", None) and Path(args.discord).exists():
        _log("Loading Discord export...")
        with open(args.discord, encoding="utf-8") as f:
            discord_data = json.load(f)
        content = load_from_discord(discord_data)
        posts_list = list(content.iter_posts())
        if not posts_list:
            _log("No messages in Discord export. Exiting.")
            sys.exit(1)
        _log(f"Loaded {len(posts_list)} messages from Discord.")
        username = (discord_data.get("username") or discord_data.get("user_id") or "discord_user")[:50]
    elif args.twitter_archive:
        _log("Loading from Twitter archive...")
        content = load_from_twitter_archive(args.twitter_archive)
        posts_list = list(content.iter_posts())
        if not posts_list:
            _log("No tweets found in archive. Check data/tweets.js (or tweets-part*.js) in the ZIP.")
            sys.exit(1)
        _log(f"Loaded {len(posts_list)} tweets from archive.")
        username = Path(args.twitter_archive).stem.replace(" ", "_")[:50]
    elif args.twitter_username:
        _log("Fetching tweets via Apify...")
        try:
            content = fetch_twitter_apify(args.twitter_username)
        except ApifyError as e:
            _log(f"Apify failed: {e}")
            sys.exit(1)
        if content is None:
            if not os.getenv("APIFY_API_TOKEN") and not os.getenv("APIFY_TOKEN"):
                _log("Apify requires APIFY_API_TOKEN. Set it in .env or use --twitter-archive.")
            else:
                _log("Apify fetch returned no tweets. Try --twitter-archive or check token.")
            sys.exit(1)
        posts_list = list(content.iter_posts())
        _log(f"Fetched {len(posts_list)} tweets.")
        username = args.twitter_username.strip().lstrip("@") or "user"
    elif args.input and Path(args.input).exists():
        content = load_from_file(args.input)
        _log(f"Loaded content from {args.input}.")
        username = Path(args.input).stem
    else:
        if args.input:
            _log("Input file not found. Using minimal sample.")
        else:
            _log("No data source. Use --twitter-archive PATH, --twitter-username @user, or a text file.")
            _log("Example: python -m holespawn.build_site --twitter-archive archive.zip")
        content = load_from_text(
            "I keep thinking about the same thing. The days blur. Memory is a trap. Nobody really knows anyone."
        )

    if not list(content.iter_posts()) and not content.raw_text:
        _log("No content to analyze. Exiting.")
        sys.exit(1)

    # Dry run
    if args.dry_run:
        _dry_run(content, username, config, args.provider)
        return

    if not _check_api_keys():
        _log("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY to generate the site.")
        sys.exit(1)

    # Output directory
    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        site_dir = out_dir / "trap_architecture"
        site_dir.mkdir(exist_ok=True)
        use_organized = False
    else:
        base_dir = config.get("output", {}).get("base_dir", "outputs")
        out_dir = _create_output_dir(username, base_dir=base_dir, use_site_subdir=True)
        site_dir = out_dir / "trap_architecture"
        use_organized = True
        if not args.quiet:
            _setup_logging(verbose=args.verbose, quiet=False, log_dir=out_dir)

    # Cost tracker (needed for Discord hybrid profile LLM calls)
    cfg_llm = config.get("llm", {})
    cfg_costs = config.get("costs", {})
    model = cfg_llm.get("model", "claude-sonnet-4-20250514")
    if os.getenv("LLM_MODEL"):
        model = os.getenv("LLM_MODEL")
    def _cost_env(name: str, default: float) -> float:
        v = os.getenv(name)
        if v is None or not (v and str(v).strip()):
            return default
        try:
            return float(str(v).strip())
        except ValueError:
            return default
    warn = _cost_env("COST_WARN_THRESHOLD", float(cfg_costs.get("warn_threshold", 1.0)))
    max_cost = _cost_env("COST_MAX_THRESHOLD", float(cfg_costs.get("max_cost", 5.0)))
    rate = int(config.get("rate_limit", {}).get("calls_per_minute", 20))
    tracker = CostTracker(model=model, warn_threshold=warn, max_cost=max_cost)

    # Profile (with optional cache); Discord uses NLP+LLM hybrid
    posts_list = list(content.iter_posts())
    if discord_data is not None:
        _log("Building Discord profile (NLP + LLM hybrid)...")
        from holespawn.profile.discord_profile_builder import build_discord_profile
        profile = build_discord_profile(
            discord_data,
            use_nlp=True,
            use_llm=True,
            use_local=bool(getattr(args, "local_model", None)),
            local_preset=getattr(args, "local_model", None),
            tracker=tracker,
        )
    elif args.no_cache:
        _log("Building profile...")
        profile = build_profile(content)
    else:
        cache = ProfileCache()
        cached = cache.get(posts_list)
        if cached is not None:
            _log("Using cached profile.")
            profile = cached
        else:
            _log("Building profile...")
            profile = build_profile(content)
            cache.set(posts_list, profile)

    # Pure generation (no templates) vs legacy single-page
    if args.single_page:
        # Legacy path: experience spec → section content → fill template
        _log("Generating experience spec...")
        try:
            spec = get_experience_spec(
                content,
                profile,
                provider=args.provider,
                tracker=tracker,
                calls_per_minute=rate,
            )
        except ValueError as e:
            _log(str(e))
            sys.exit(1)
        except Exception as e:
            _log(f"Experience spec failed: {e}")
            sys.exit(1)
        _log("Generating legacy single-page site...")
        try:
            sections_content = get_site_content(
                content,
                profile,
                spec,
                provider=args.provider,
                tracker=tracker,
                calls_per_minute=rate,
            )
        except Exception as e:
            _log(f"Content generation failed: {e}")
            sys.exit(1)
        build_site(spec, sections_content, site_dir, profile=profile)
        _log(f"Site written to {site_dir}")
    else:
        # Pure generation: LLM designs structure, CSS, and content from full profile
        _log("Building site from profile (pure generation, no templates)...")
        try:
            generate_site_from_profile(
                profile,
                site_dir,
                content=content,
                tracker=tracker,
                provider=args.provider,
                calls_per_minute=rate,
            )
            _log(f"Site written to {site_dir}")
        except ValueError as e:
            _log(str(e))
            sys.exit(1)
        except Exception as e:
            _log(f"Pure generation failed: {e}")
            sys.exit(1)

    # Validate
    validator = SiteValidator(site_dir)
    if not validator.validate_all():
        _log("Site validation issues: " + "; ".join(validator.get_errors()))

    # Metadata and profile (always write when we have out_dir)
    metadata = {
        "username": username,
        "generated_at": datetime.now().isoformat(),
        "version": "0.1.0",
        "llm_model": model,
        "data_source": "twitter_archive" if args.twitter_archive else ("apify" if args.twitter_username else "file"),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out_dir / "behavioral_matrix.json").write_text(
        json.dumps(_profile_to_dict(profile), indent=2), encoding="utf-8"
    )

    # Binding protocol (engagement brief)
    if not args.no_engagement:
        try:
            from holespawn.engagement import get_engagement_brief
            _log("Generating binding protocol...")
            brief = get_engagement_brief(
                content,
                profile,
                provider=args.provider,
                tracker=tracker,
                calls_per_minute=rate,
            )
            brief_path = out_dir / "binding_protocol.md"
            brief_path.write_text(brief.strip(), encoding="utf-8")
            _log("  binding_protocol.md")
        except ValueError:
            _log("Skipping engagement brief (no API key).")
        except Exception as e:
            _log(f"Engagement brief failed: {e}")

    # Store in DB if requested
    if getattr(args, "db", None):
        try:
            from holespawn.db import store_profile, init_db
            db_path = Path(args.db)
            init_db(db_path)
            run_id = store_profile(out_dir, db_path)
            if run_id and not args.quiet:
                _log(f"  stored in DB: {run_id}")
        except Exception as e:
            _log(f"  DB store skipped: {e}")

    # Cost summary and hard cap
    tracker.save_to_file(out_dir)
    if not args.quiet:
        tracker.print_summary()
    if tracker.get_cost() > tracker.max_cost:
        _log(f"Cost ${tracker.get_cost():.2f} exceeded max ${tracker.max_cost:.2f}. Set COST_MAX_THRESHOLD to increase.")
        sys.exit(1)

    if args.deploy:
        _deploy(site_dir)

    if not args.quiet:
        _log(f"Done. Output: {out_dir.absolute()}")


if __name__ == "__main__":
    main()
