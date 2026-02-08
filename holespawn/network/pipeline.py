"""
Run the full network graph profiling pipeline: fetch -> analyze -> profile key nodes -> report -> viz.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from holespawn.cost_tracker import CostTracker
from holespawn.ingest.network import (
    NetworkData,
    fetch_network_data,
    validate_network_data,
)
from holespawn.network.graph_analysis import (
    NetworkAnalysis,
    build_network_analysis,
    network_analysis_to_dict,
)
from holespawn.network.node_profiler import profile_key_nodes
from holespawn.network.vulnerability_map import generate_network_report
from holespawn.network.visualizer import generate_network_graph_html

logger = logging.getLogger(__name__)


def _top_key_node_usernames(analysis: NetworkAnalysis, top_n: int) -> list[str]:
    """Collect usernames for top key nodes: bridges, community hubs (1 per community), amplifiers, vulnerable, then betweenness."""
    import random
    seen: set[str] = set()
    out: list[str] = []
    # 1) All bridge nodes
    for b in analysis.bridge_nodes:
        u = b.get("username")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    # 2) At least one hub per community
    for cid, metrics in analysis.community_metrics.items():
        hub = metrics.get("hub_node")
        if hub and hub not in seen:
            seen.add(hub)
            out.append(hub)
    # 3) Amplifiers and vulnerable entry points
    for a in analysis.amplifiers[:3]:
        u = a.get("username")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    for v in analysis.vulnerable_entry_points[:5]:
        u = v.get("username")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    # 4) Fill rest by betweenness
    sorted_bet = sorted(
        analysis.betweenness.items(), key=lambda x: (-x[1], random.random())
    )
    for node, _ in sorted_bet:
        if node not in seen:
            seen.add(node)
            out.append(node)
        if len(out) >= top_n:
            break
    return out[:top_n]


def run_network_graph_pipeline(
    target_username: str,
    output_dir: Path | str,
    *,
    inner_circle_size: int = 150,
    top_nodes: int = 15,
    communities_only: bool = False,
    no_viz: bool = False,
    budget: float | None = None,
    resume: bool = False,
    consent_acknowledged: bool = False,
    tracker: CostTracker | None = None,
    provider: str | None = None,
    model: str | None = None,
    calls_per_minute: int = 20,
    log: Any = None,
) -> dict[str, Any]:
    """
    Fetch social graph, build analysis, optionally profile key nodes, generate report and viz.
    Writes network_raw_data.json, network_analysis.json, network_report.md, and (unless no_viz) network_graph.html to output_dir.
    Returns summary dict with keys: network_data, analysis, node_profiles, report_path, viz_path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    def _log(msg: str, *args: Any) -> None:
        text = (msg % args) if args else msg
        if callable(log):
            log(text)
        else:
            logger.info(text)

    if tracker is None:
        cfg = {}
        try:
            from holespawn.config import load_config
            cfg = load_config()
        except Exception:
            pass
        costs = cfg.get("costs", {})
        warn = float(costs.get("warn_threshold", os.getenv("COST_WARN_THRESHOLD", "1")))
        max_cost = budget if budget is not None else float(costs.get("max_cost", os.getenv("COST_MAX_THRESHOLD", "5")))
        tracker = CostTracker(warn_threshold=warn, max_cost=max_cost)

    raw_path = output_dir / "network_raw_data.json"
    resume_path = raw_path if resume and raw_path.exists() else None
    if not consent_acknowledged and not resume_path:
        apify_est = 2 + inner_circle_size
        llm_est = (0 if communities_only else top_nodes) + 1
        _log(
            "Network analysis for @%s: inner circle %d → ~%d Apify calls, %d LLM calls. Proceed? [y/N] ",
            target_username.lstrip("@"),
            inner_circle_size,
            apify_est,
            llm_est,
        )
        try:
            ans = input().strip().lower()
            if ans not in ("y", "yes"):
                raise SystemExit("Aborted.")
        except EOFError:
            raise SystemExit("Aborted (no input).")

    _log("Fetching network data (following, followers, interactions, then inter-connection crawl)...")
    network_data = fetch_network_data(
        target_username,
        inner_circle_size=inner_circle_size,
        raw_data_path=raw_path,
        resume_from_path=resume_path,
        log_progress=_log,
    )
    if network_data is None:
        raise ValueError("Failed to fetch network data (check APIFY_API_TOKEN and username)")
    checks = validate_network_data(network_data)
    if not checks.get("has_real_graph"):
        raise ValueError(
            "Network data has too few inter-connection edges (star topology). "
            "Analysis would be meaningless. Check that the crawl step ran and inner_circle_size is sufficient."
        )
    if not network_data.raw_edges and not network_data.following:
        raise ValueError("No edges or following list returned for this user")

    _log("Building graph and running community detection...")
    analysis = build_network_analysis(network_data)
    analysis_dict = network_analysis_to_dict(analysis)
    out_json = output_dir / "network_analysis.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(analysis_dict, f, indent=2)
    _log(f"  {out_json.name}")

    node_profiles: dict[str, dict[str, Any]] = {}
    if not communities_only and top_nodes > 0:
        key_usernames = _top_key_node_usernames(analysis, top_nodes)
        _log(f"Profiling {len(key_usernames)} key nodes (tweets + LLM synthesis)...")
        node_profiles = profile_key_nodes(
            key_usernames,
            analysis,
            max_tweets_per_user=300,
            tracker=tracker,
            provider=provider,
            model=model,
            calls_per_minute=calls_per_minute,
        )
        if tracker.get_cost() > tracker.max_cost:
            raise RuntimeError(
                f"Network profiling cost ${tracker.get_cost():.2f} exceeded budget ${tracker.max_cost:.2f}"
            )

    _log("Generating network vulnerability report...")
    report_md = generate_network_report(
        analysis,
        node_profiles,
        target_username,
        tracker=tracker,
        provider=provider,
        model=model,
        calls_per_minute=calls_per_minute,
    )
    report_path = output_dir / "network_report.md"
    report_path.write_text(report_md, encoding="utf-8")
    _log(f"  {report_path.name}")

    viz_path = None
    if not no_viz:
        _log("Generating network graph visualization...")
        html_path = output_dir / "network_graph.html"
        generate_network_graph_html(
            analysis,
            node_profiles,
            html_path,
            target_username=target_username,
        )
        _log(f"  {html_path.name}")
        viz_path = str(html_path)

    tracker.save_to_file(output_dir)
    return {
        "network_data": network_data,
        "analysis": analysis,
        "node_profiles": node_profiles,
        "report_path": str(report_path),
        "viz_path": viz_path,
    }
