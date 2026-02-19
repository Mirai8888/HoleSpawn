"""
CLI for network analysis. Two modes:
  1) Graph profiling: python -m holespawn.network @username -o output_dir  (fetch graph, profile key nodes, report + viz)
  2) File-based / live-scraped profiles: python -m holespawn.network profiles_dir/ -o report.json  or  --apify @user -o report.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Load .env so LLM keys are available (same as build_site)
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
from .engine import NetworkEngine
from .pipeline import run_network_graph_pipeline


def _looks_like_username(s: str) -> bool:
    if not s or len(s) > 100:
        return False
    s = s.strip().lstrip("@")
    return bool(s) and not Path(s).exists() and "/" not in s and "\\" not in s and "." not in s


def _run_engine(args: argparse.Namespace) -> None:
    """Run the operational network engine CLI."""
    import networkx as nx
    from .graph_builder import build_graph

    graph_path = Path(args.graph)
    if not graph_path.exists():
        sys.stderr.write(f"[engine] error: graph file not found: {graph_path}\n")
        sys.exit(1)

    data = json.loads(graph_path.read_text())

    # Accept multiple formats: raw edge list, graph_builder output, or nx node_link
    G: nx.DiGraph | None = None
    if "links" in data and "nodes" in data:
        # node_link_data format
        G = nx.node_link_graph(data, directed=True)
    elif "edges" in data:
        # Our edge list format: [{source, target, weight?, types?}, ...]
        G = nx.DiGraph()
        for e in data["edges"]:
            src = e.get("source") or e.get("from")
            tgt = e.get("target") or e.get("to")
            if src and tgt:
                G.add_edge(
                    src, tgt,
                    weight=e.get("weight", 1.0),
                    types=set(e.get("types", [])),
                )
    elif isinstance(data, list):
        # Plain edge list: [{source, target, ...}, ...]
        G = nx.DiGraph()
        for e in data:
            src = e.get("source") or e.get("from")
            tgt = e.get("target") or e.get("to")
            if src and tgt:
                G.add_edge(
                    src, tgt,
                    weight=e.get("weight", 1.0),
                    types=set(e.get("types", [])),
                )
    else:
        sys.stderr.write(
            "[engine] error: unrecognized graph format. Expected node_link, {edges: [...]}, or [{source, target}, ...]\n"
        )
        sys.exit(1)

    if G is None or G.number_of_nodes() == 0:
        sys.stderr.write("[engine] error: graph is empty\n")
        sys.exit(1)

    sys.stderr.write(f"[engine] Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges\n")

    engine = NetworkEngine(G)
    out_dir = Path(args.output) if args.output else Path(".")

    if args.command == "analyze":
        intel = engine.analyze()
        out_path = out_dir / "network_intel.json"
        engine.export_intel(out_path)
        sys.stderr.write(f"[engine] Intel exported: {out_path}\n")
        sys.stderr.write(f"  Communities: {intel.community_count}\n")
        sys.stderr.write(f"  Hubs: {len(intel.hubs)} | Bridges: {len(intel.bridges)} | SPOFs: {len(intel.spofs)}\n")

        # Print top 10 by influence
        top = intel.top_nodes(by="influence_score", n=10)
        sys.stderr.write("  Top 10 by influence:\n")
        for op in top:
            sys.stderr.write(f"    {op.node:20s}  {op.role:12s}  score={op.influence_score:.4f}  pr={op.pagerank:.6f}\n")

    elif args.command == "paths":
        if not args.source or not args.target_node:
            sys.stderr.write("[engine] error: --source and --target required for paths\n")
            sys.exit(1)
        paths = engine.find_influence_paths(args.source, args.target_node, k=args.top_k)
        if not paths:
            sys.stderr.write(f"[engine] No paths found from {args.source} to {args.target_node}\n")
            return
        for i, p in enumerate(paths):
            sys.stderr.write(
                f"  Path {i+1}: {' -> '.join(p.path)}  "
                f"(hops={p.hops}, reliability={p.reliability:.4f}, "
                f"bottleneck={p.bottleneck_edge})\n"
            )
        out_path = out_dir / "influence_paths.json"
        out_path.write_text(json.dumps([p.to_dict() for p in paths], indent=2))
        sys.stderr.write(f"[engine] Paths exported: {out_path}\n")

    elif args.command == "plan":
        target_nodes = args.target_nodes.split(",") if args.target_nodes else None
        target_comm = args.target_community
        entry = args.entry.split(",") if args.entry else None

        plan = engine.plan_operation(
            objective=args.objective or "reach",
            target_nodes=target_nodes,
            target_community=target_comm,
            entry_nodes=entry,
        )
        out_path = out_dir / "operation_plan.json"
        engine.export_plan(plan, out_path)
        sys.stderr.write(f"[engine] Plan exported: {out_path}\n")
        sys.stderr.write(f"  Objective: {plan.objective}\n")
        sys.stderr.write(f"  Entry points: {len(plan.entry_points)}\n")
        sys.stderr.write(f"  Paths: {len(plan.paths)}\n")
        sys.stderr.write(f"  Amplifiers: {len(plan.amplification_chain)}\n")
        sys.stderr.write(f"  Weak links: {len(plan.weak_links)}\n")
        sys.stderr.write(f"  Estimated reach: {plan.estimated_reach_pct:.1%}\n")

    elif args.command == "compare":
        if not args.graph_b:
            sys.stderr.write("[engine] error: --graph-b required for compare\n")
            sys.exit(1)
        data_b = json.loads(Path(args.graph_b).read_text())
        if "links" in data_b and "nodes" in data_b:
            G_b = nx.node_link_graph(data_b, directed=True)
        elif "edges" in data_b:
            G_b = nx.DiGraph()
            for e in data_b["edges"]:
                src = e.get("source") or e.get("from")
                tgt = e.get("target") or e.get("to")
                if src and tgt:
                    G_b.add_edge(src, tgt, weight=e.get("weight", 1.0), types=set(e.get("types", [])))
        else:
            sys.stderr.write("[engine] error: unrecognized format for --graph-b\n")
            sys.exit(1)

        engine_b = NetworkEngine(G_b)
        diff = engine.compare(engine_b)
        out_path = out_dir / "network_diff.json"
        out_path.write_text(json.dumps(diff, indent=2, default=str))
        sys.stderr.write(f"[engine] Diff exported: {out_path}\n")
        sys.stderr.write(f"  Nodes: {diff['node_count_delta']:+d} | Edges: {diff['edge_count_delta']:+d}\n")
        sys.stderr.write(f"  New: {len(diff['new_nodes'])} | Lost: {len(diff['lost_nodes'])} | Role changes: {len(diff['role_changes'])}\n")

    else:
        sys.stderr.write(f"[engine] Unknown command: {args.command}\n")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Network analysis: graph profiling (@username), file-based profiles, or operational engine."
    )
    subparsers = parser.add_subparsers(dest="mode")

    # Engine subcommand
    eng = subparsers.add_parser("engine", help="Operational network engine")
    eng.add_argument("command", choices=["analyze", "paths", "plan", "compare"],
                     help="Engine command: analyze|paths|plan|compare")
    eng.add_argument("--graph", required=True, help="Path to graph JSON (node_link or edge list)")
    eng.add_argument("-o", "--output", help="Output directory (default: current)")
    # paths args
    eng.add_argument("--source", help="Source node for paths command")
    eng.add_argument("--target-node", help="Target node for paths command")
    eng.add_argument("--top-k", type=int, default=5, help="Number of paths to find (default: 5)")
    # plan args
    eng.add_argument("--objective", default="reach", help="Operation objective: reach|disrupt|monitor")
    eng.add_argument("--target-nodes", help="Comma-separated target nodes")
    eng.add_argument("--target-community", type=int, default=None, help="Target community ID")
    eng.add_argument("--entry", help="Comma-separated entry nodes")
    # compare args
    eng.add_argument("--graph-b", help="Second graph for compare command")

    # Legacy positional mode
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
        help=(
            "Fetch network via self-hosted scraper (legacy flag name): target username (e.g. @user). "
            "Requires X session (python -m holespawn.scraper login)."
        ),
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

    # Engine mode
    if args.mode == "engine":
        _run_engine(args)
        return

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
                f"[holespawn] Large scraper run: --max-following={n}. Scraper will run ~{n} tweet scrapes + 1 following list. "
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
            sys.stderr.write(f"[holespawn] error: scraper fetch failed: {e}\n")
            sys.exit(1)
        if not profiles:
            sys.stderr.write(
                "[holespawn] error: no profiles from scraper (check X session and --apify username)\n"
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
