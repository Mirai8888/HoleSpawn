"""
Build a full personalized website from narrative input.
CLI: prompt Individual or Following, then x.com user link, then scrape; or pass a file.
Pipeline: ingest (scrape or file) -> optional audience map -> profile -> AI spec -> site -> optional deploy.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holespawn.ingest import load_from_file, load_from_text, SocialContent
from holespawn.profile import build_profile
from holespawn.experience import get_experience_spec
from holespawn.site_builder import get_site_content, build_site


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _prompt_scrape_x() -> tuple[SocialContent, list[str] | None, list[str] | None]:
    """
    Interactive: Individual or Following? then x.com link. Scrape and return
    (content, following_handles or None, audience_posts or None).
    """
    from holespawn.x_scraper import parse_x_username, scrape_x_user_tweets, scrape_x_following

    print()
    print("  Individual (1)  - Scrape this user's tweets for their profile.")
    print("  Following (2)    - Scrape this user's tweets + who they follow, map audience.")
    while True:
        choice = input("Select: Individual (1) or Following (2)? ").strip() or "1"
        if choice in ("1", "2"):
            break
        print("Enter 1 or 2.")
    mode = "following" if choice == "2" else "individual"

    while True:
        link = input("Enter x.com user link (e.g. https://x.com/username): ").strip()
        username = parse_x_username(link) if link else None
        if username:
            break
        print("Could not parse username. Use a link like https://x.com/username or just the username.")
    _log(f"Username: {username}")

    _log("Scraping X (this may take a moment; Nitter instances can be slow or down)...")
    subject_tweets = scrape_x_user_tweets(username, max_tweets=100)
    if not subject_tweets:
        _log("No tweets scraped. Nitter may be down; try again or use a file: python -m holespawn.build_site data/posts.txt")
        sys.exit(1)
    content = SocialContent(posts=subject_tweets)
    _log(f"Scraped {len(subject_tweets)} tweets for profile.")

    following_handles = None
    audience_posts = None
    if mode == "following":
        _log("Scraping following list...")
        following_usernames = scrape_x_following(username, max_following=200)
        if not following_usernames:
            _log("Could not get following list (Nitter following page may be down). Continuing without audience map.")
        else:
            following_handles = following_usernames
            _log(f"Found {len(following_handles)} following. Sampling their tweets for audience map...")
            audience_posts = []
            sample = min(25, len(following_handles))
            for i, u in enumerate(following_handles[:sample]):
                _log(f"  [{i+1}/{sample}] {u}")
                try:
                    audience_posts.extend(scrape_x_user_tweets(u, max_tweets=15))
                except Exception:
                    continue
            _log(f"Collected {len(audience_posts)} audience tweets.")

    return content, following_handles, audience_posts


def main():
    parser = argparse.ArgumentParser(
        description="HoleSpawn — Build a personalized rabbit hole / ARG website. CLI: ingest, optional audience map, profile, AI spec, site, optional deploy.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive: prompts Individual or Following, then x.com link (scrapes X)
  python -m holespawn.build_site

  # Build from file
  python -m holespawn.build_site data/posts.txt -o output

  # Map audience from file / Bluesky
  python -m holespawn.build_site data/posts.txt --following-file data/following.txt -o output
  python -m holespawn.build_site data/posts.txt --following-bluesky user.bsky.social -o output

  # Deploy after build
  python -m holespawn.build_site data/posts.txt -o output --deploy
        """,
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to text/JSON file with posts. If omitted, prompts: Individual or Following, then x.com link (scrape).",
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory for the generated site (default: output).",
    )
    parser.add_argument(
        "--provider",
        choices=("anthropic", "openai"),
        default=None,
        help="AI provider (default: Anthropic if ANTHROPIC_API_KEY set, else OpenAI).",
    )
    # Audience / following
    parser.add_argument(
        "--following-file",
        metavar="PATH",
        default=None,
        help="File with following list: one handle per line (Bluesky, Mastodon, etc.).",
    )
    parser.add_argument(
        "--following-bluesky",
        metavar="HANDLE",
        default=None,
        help="Bluesky handle to fetch following from (e.g. user.bsky.social). No API key.",
    )
    parser.add_argument(
        "--following-mastodon",
        metavar="INSTANCE,USERNAME",
        default=None,
        help="Mastodon: instance URL and username (e.g. https://mastodon.social,user). Set MASTODON_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--audience-sample",
        type=int,
        default=25,
        help="When fetching posts for audience map, sample this many followed accounts (default: 25).",
    )
    parser.add_argument(
        "--no-fetch-audience",
        action="store_true",
        help="Do not fetch posts for followed accounts; use only handle list (no Bluesky/Mastodon fetch).",
    )
    # Deploy
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="After building: run Netlify CLI if installed, else print deploy instructions.",
    )
    args = parser.parse_args()

    content = None
    following_handles: list[str] = []
    audience_posts_from_scrape: list[str] | None = None

    if args.input and Path(args.input).exists():
        content = load_from_file(args.input)
        _log(f"Loaded content from {args.input}.")
    else:
        # No file: interactive scrape from X.com
        if not args.input:
            try:
                content, following_handles_list, audience_posts_from_scrape = _prompt_scrape_x()
                if following_handles_list:
                    following_handles = following_handles_list
            except ImportError as e:
                _log(f"Scraping requires ntscraper (and for Following: requests, beautifulsoup4). {e}")
                sys.exit(1)
        else:
            _log("Input file not found. Using minimal sample.")
            content = load_from_text(
                "I keep thinking about the same thing. The days blur. Memory is a trap. Nobody really knows anyone."
            )

    if content is None:
        content = load_from_text("")
    if not list(content.iter_posts()) and not content.raw_text:
        _log("No content to analyze. Add posts to a file or run without args to scrape from x.com.")
        sys.exit(1)

    # Resolve following list (file / Bluesky / Mastodon flags, or from scrape)
    if args.following_file:
        try:
            from holespawn.audience import load_following_from_file
            following_handles = load_following_from_file(args.following_file)
            _log(f"Loaded {len(following_handles)} handles from {args.following_file}.")
        except ImportError:
            _log("audience module not available. Install: pip install requests")
            sys.exit(1)
    if args.following_bluesky:
        try:
            from holespawn.audience import fetch_all_following_bluesky
            following_handles = fetch_all_following_bluesky(args.following_bluesky, max_following=500)
            _log(f"Fetched {len(following_handles)} Bluesky following for {args.following_bluesky}.")
        except ImportError as e:
            _log(f"Bluesky fetch requires requests: {e}")
            sys.exit(1)
        except Exception as e:
            _log(f"Bluesky fetch failed: {e}")
            sys.exit(1)
    if args.following_mastodon:
        part = args.following_mastodon.split(",", 1)
        if len(part) != 2:
            _log("--following-mastodon must be INSTANCE,USERNAME (e.g. https://mastodon.social,user)")
            sys.exit(1)
        instance_url, username = part[0].strip(), part[1].strip()
        try:
            from holespawn.audience import fetch_following_mastodon
            token = os.getenv("MASTODON_ACCESS_TOKEN")
            if not token:
                _log("MASTODON_ACCESS_TOKEN not set. Create an app on your instance and set the token.")
                sys.exit(1)
            following_handles = fetch_following_mastodon(instance_url, username, limit=300)
            _log(f"Fetched {len(following_handles)} Mastodon following for {username}.")
        except ImportError as e:
            _log(f"Mastodon fetch requires requests: {e}")
            sys.exit(1)
        except Exception as e:
            _log(f"Mastodon fetch failed: {e}")
            sys.exit(1)

    audience_profile = None
    if following_handles or audience_posts_from_scrape:
        try:
            from holespawn.audience import map_audience_susceptibility
            _log("Mapping audience susceptibility (who they follow -> what audience is susceptible to)...")
            audience_profile = map_audience_susceptibility(
                following_handles or [],
                sample_size=args.audience_sample,
                fetch_posts=not args.no_fetch_audience and not audience_posts_from_scrape,
                existing_posts=audience_posts_from_scrape,
            )
            if audience_profile.summary:
                _log(f"Audience: {audience_profile.summary[:120]}...")
        except ImportError as e:
            _log(f"Audience mapping requires requests: {e}")
        except Exception as e:
            _log(f"Audience mapping failed: {e}")

    _log("Building profile...")
    profile = build_profile(content)

    _log("Generating personalized experience spec (aesthetic, type, tone)...")
    try:
        spec = get_experience_spec(
            content, profile,
            audience_profile=audience_profile,
            provider=args.provider,
        )
    except ValueError as e:
        _log(str(e))
        sys.exit(1)
    except Exception as e:
        _log(f"Experience spec failed: {e}")
        sys.exit(1)

    _log("Generating site content (copy, puzzles)...")
    try:
        sections_content = get_site_content(
            content, profile, spec,
            audience_summary=audience_profile.summary if audience_profile else None,
            provider=args.provider,
        )
    except Exception as e:
        _log(f"Content generation failed: {e}")
        sys.exit(1)

    out_dir = Path(args.output)
    build_site(spec, sections_content, out_dir)
    _log(f"Site written to {out_dir.absolute()}")
    _log("  index.html, styles.css, app.js")

    if args.deploy:
        _deploy(out_dir)


def _deploy(out_dir: Path) -> None:
    """Run Netlify CLI if available, else print free deploy options."""
    netlify = shutil.which("netlify")
    if netlify:
        _log("Running: netlify deploy --dir=" + str(out_dir))
        r = subprocess.run(
            [netlify, "deploy", "--dir", str(out_dir), "--prod"],
            cwd=out_dir,
        )
        if r.returncode != 0:
            _log("Netlify deploy failed. See instructions below.")
    else:
        _log("Netlify CLI not found. Free deploy options:")
        _log("  1. Netlify Drop: drag the output folder to https://app.netlify.com/drop")
        _log("  2. GitHub Pages: push the folder to a repo, Settings → Pages → source: main / root")
        _log("  3. Install Netlify CLI: npm i -g netlify-cli, then run: netlify deploy --dir=" + str(out_dir))


if __name__ == "__main__":
    main()
