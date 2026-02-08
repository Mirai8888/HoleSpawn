"""
CLI for network analysis. Two modes:
  1) Graph profiling: python -m holespawn.network @username -o output_dir  (fetch graph, profile key nodes, report + viz)
  2) File-based / Apify profiles: python -m holespawn.network profiles_dir/ -o report.json  or  --apify @user -o report.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Load .env so APIFY_API_TOKEN and LLM keys are available (same as build_site)
ROOT = Path(__file__).resolve().parent.parent.parent
try:
    from dotenv import load_dotenv

    _env_path = ROOT / ".env"
    if _env_path.exists():
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

from .analyzer import NetworkAnalyzer, load_edges_file, load_profiles_from_dir
from .apify_network import fetch_profiles_via_apify
from .brief import get_network_engagement_brief
from .pipeline import run_network_graph_pipeline


def _looks_like_username(s: str) -> bool:
    if not s or len(s) > 100:
        return False
    s = s.strip().lstrip("@")
    return bool(s) and not Path(s).exists() and "/" not in s and "\\" not in s and "." not in s


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Network analysis: graph profiling (@username) or file-based profiles (dir / --apify)."
    )
    parser.add_argument(
        "positional",
        nargs="?",
        default=None,
        help="Username (e.g. @user) for graph pipeline, or directory for profile-based analysis.",
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
        help="Output: directory for graph pipeline, or report JSON path for profile-based.",
    )
    parser.add_argument(
        "--inner-circle-size",
        type=int,
        default=150,
        metavar="N",
        help="Graph pipeline: how many top connections to crawl for inter-edges (default 150).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Graph pipeline: hops from target to explore (default 1; reserved for future).",
    )
    parser.add_argument(
        "--top-nodes",
        type=int,
        default=15,
        help="Graph pipeline: how many key nodes to fully profile (default 15).",
    )
    parser.add_argument(
        "--no-viz",
        action="store_true",
        help="Graph pipeline: skip generating network_graph.html.",
    )
    parser.add_argument(
        "--communities-only",
        action="store_true",
        help="Graph pipeline: only detect/describe communities, skip individual node profiling.",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        metavar="DOLLARS",
        help="Graph pipeline: max spend in dollars (e.g. 5.00). Uses COST_MAX_THRESHOLD if not set.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Graph pipeline: resume from existing network_raw_data.json if present.",
    )
    parser.add_argument(
        "--consent-acknowledged",
        action="store_true",
        help="Graph pipeline: skip cost estimate / Proceed? prompt (for scripted use).",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.12,
        help="Profile-based: min Jaccard similarity when no edges file (default 0.12).",
    )
    parser.add_argument(
        "--no-brief",
        action="store_true",
        help="Profile-based: skip network_engagement_brief.md.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Store network report in SQLite (path or dir).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation for large --apify runs.",
    )
    args = parser.parse_args()

    # Graph profiling mode: positional is username and -o is directory (not a .json file)
    if (
        args.positional
        and _looks_like_username(args.positional)
        and args.output
        and Path(args.output).suffix.lower() != ".json"
    ):
        username = args.positional.strip().lstrip("@")
        out_dir = Path(args.output)
        try:
            run_network_graph_pipeline(
                username,
                out_dir,
                inner_circle_size=args.inner_circle_size,
                top_nodes=0 if args.communities_only else args.top_nodes,
                communities_only=args.communities_only,
                no_viz=args.no_viz,
                budget=args.budget,
                resume=args.resume,
                consent_acknowledged=args.consent_acknowledged,
                log=lambda msg: sys.stderr.write(msg + "\n"),
            )
            sys.stderr.write(f"Network profiling complete. Output: {out_dir}\n")
            return
        except Exception as e:
            sys.stderr.write(f"[holespawn] error: graph pipeline failed: {e}\n")
            sys.exit(1)

    # Profile-based mode (existing behavior)
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
    elif args.positional and Path(args.positional).is_dir():
        profiles_dir = Path(args.positional)
        profiles = load_profiles_from_dir(profiles_dir)
        if not profiles:
            sys.stderr.write(
                "[holespawn] error: no behavioral_matrix.json or profile.json found under dir\n"
            )
            sys.exit(1)
    else:
        sys.stderr.write(
            "[holespawn] error: provide username (e.g. @user) with -o <dir> for graph pipeline, or profiles_dir / --apify USERNAME for profile-based\n"
        )
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
