"""
CLI for network analysis. Data from file-based dir or paid API (Apify).
Usage:
  python -m holespawn.network profiles_dir/ -o report.json
  python -m holespawn.network profiles_dir/ --edges edges.csv -o report.json
  python -m holespawn.network --apify @username --max-following 50 -o report.json  (requires APIFY_API_TOKEN)
"""

import argparse
import json
import os
import sys
from pathlib import Path

from .analyzer import NetworkAnalyzer, load_edges_file, load_profiles_from_dir
from .apify_network import fetch_profiles_via_apify
from .brief import get_network_engagement_brief


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze network from file-based profiles or paid API (Apify)."
    )
    parser.add_argument(
        "profiles_dir",
        type=Path,
        nargs="?",
        default=None,
        help="Directory with behavioral_matrix.json or profile.json per account.",
    )
    parser.add_argument(
        "--apify",
        type=str,
        default=None,
        metavar="USERNAME",
        help="Fetch network via Apify: target username (e.g. @user). Uses APIFY_API_TOKEN.",
    )
    parser.add_argument(
        "--max-following",
        type=int,
        default=50,
        help="When using --apify, max accounts to profile (default 50).",
    )
    parser.add_argument(
        "--edges",
        type=Path,
        default=None,
        help="Optional CSV or JSON file with source,target edges (follow graph).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write report JSON here. Default: stdout.",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.12,
        help="Min Jaccard similarity to link profiles when no edges file (default 0.12).",
    )
    parser.add_argument(
        "--no-brief",
        action="store_true",
        help="Skip generating network_engagement_brief.md (requires API key when -o is set).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Store network report in SQLite (path or dir; e.g. outputs/holespawn.sqlite).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation for large --apify runs (--max-following > 20).",
    )
    args = parser.parse_args()

    if args.apify:
        username = (args.apify or "").strip().lstrip("@")
        if not username:
            sys.stderr.write("[holespawn] error: --apify requires a username\n")
            sys.exit(1)
        n = args.max_following
        if n > 20 and not args.yes:
            sys.stderr.write(
                f"[holespawn] Large Apify run: --max-following={n}. Apify will run ~{n} tweet scrapes + 1 following list (billed separately). "
                "LLM cost for network brief only is typically $0.01–0.10. Continue? [y/N] "
            )
            try:
                line = sys.stdin.readline().strip().lower()
                if line not in ("y", "yes"):
                    sys.stderr.write("[holespawn] Aborted.\n")
                    sys.exit(0)
            except (KeyboardInterrupt, EOFError):
                sys.stderr.write("\n[holespawn] Aborted.\n")
                sys.exit(0)
        try:
            profiles = fetch_profiles_via_apify(
                username,
                max_following=args.max_following,
                max_tweets_per_user=300,
            )
        except Exception as e:
            sys.stderr.write(f"[holespawn] error: Apify failed: {e}\n")
            sys.exit(1)
        if not profiles:
            sys.stderr.write(
                "[holespawn] error: no profiles from Apify (check APIFY_API_TOKEN and --apify username)\n"
            )
            sys.exit(1)
    elif args.profiles_dir and Path(args.profiles_dir).is_dir():
        profiles_dir = Path(args.profiles_dir)
        profiles = load_profiles_from_dir(profiles_dir)
        if not profiles:
            sys.stderr.write(
                "[holespawn] error: no behavioral_matrix.json or profile.json found under dir\n"
            )
            sys.exit(1)
    else:
        sys.stderr.write("[holespawn] error: provide profiles_dir or --apify USERNAME\n")
        sys.exit(1)

    edges = None
    if args.edges and Path(args.edges).is_file():
        edges = load_edges_file(args.edges)

    analyzer = NetworkAnalyzer(similarity_threshold=args.similarity_threshold)
    report = analyzer.analyze_network(profiles, edges=edges)
    report["stats"]["source"] = "apify" if args.apify else "file"

    out = json.dumps(report, indent=2)
    brief_text = None
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        if not args.no_brief:
            try:
                from holespawn.cost_tracker import CostTracker

                tracker = CostTracker(
                    warn_threshold=float(os.getenv("COST_WARN_THRESHOLD", "1")),
                    max_cost=float(os.getenv("COST_MAX_THRESHOLD", "5")),
                )
                brief_text = get_network_engagement_brief(report, tracker=tracker)
                brief_path = Path(args.output).parent / "network_engagement_brief.md"
                brief_path.write_text(brief_text, encoding="utf-8")
                sys.stderr.write("  network_engagement_brief.md\n")
                tracker.save_to_file(Path(args.output).parent)
                cost = tracker.get_cost()
                sys.stderr.write(
                    f"  Network brief cost: ${cost:.4f} ({tracker.input_tokens:,} in / {tracker.output_tokens:,} out tokens)\n"
                )
            except Exception as e:
                sys.stderr.write(f"[holespawn] error: network brief failed: {e}\n")
        if args.db:
            try:
                from datetime import datetime

                from holespawn.db import init_db, store_network_report

                db_path = Path(args.db)
                init_db(db_path)
                run_id = (
                    f"network_{Path(args.output).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                store_network_report(
                    run_id=run_id,
                    output_dir=Path(args.output).parent,
                    report_json=out,
                    brief_text=brief_text,
                    db_path=db_path,
                    source=report.get("stats", {}).get("source", "file"),
                )
                sys.stderr.write(f"  stored in DB: {run_id}\n")
            except Exception as e:
                sys.stderr.write(f"  (DB store skipped: {e})\n")
    else:
        print(out)


if __name__ == "__main__":
    main()
