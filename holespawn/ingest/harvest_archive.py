#!/usr/bin/env python3
"""
CLI runner: harvest Community Archive data, build graph, run analysis.

Usage:
    python -m holespawn.ingest.harvest_archive [--usernames user1,user2]
    python -m holespawn.ingest.harvest_archive --overlap partition.json
    python -m holespawn.ingest.harvest_archive --list-accounts
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / "HoleSpawn" / "data" / "community-archive"
INTEL_DIR = DATA_DIR / "intel"


def main():
    parser = argparse.ArgumentParser(description="Harvest Community Archive for HoleSpawn intel")
    parser.add_argument("--list-accounts", action="store_true", help="List all archived accounts")
    parser.add_argument("--usernames", type=str, help="Comma-separated usernames to harvest")
    parser.add_argument("--overlap", type=str, help="Path to partition JSON (our network data)")
    parser.add_argument("--analyze", action="store_true", help="Run graph + content analysis after harvest")
    parser.add_argument("--all", action="store_true", help="Harvest ALL archived accounts")
    args = parser.parse_args()

    from holespawn.ingest.community_archive import (
        CommunityArchiveClient,
        harvest_account,
        harvest_network_overlap,
        to_holespawn_graph,
        extract_content,
    )

    client = CommunityArchiveClient()

    if args.list_accounts:
        accounts = client.list_accounts()
        for a in sorted(accounts, key=lambda x: x.get("username", "")):
            print(f"  {a.get('username', '?'):>25s}  (id={a.get('account_id', '?')})")
        print(f"\nTotal: {len(accounts)} accounts")
        return

    harvested: dict = {}

    if args.usernames:
        for username in args.usernames.split(","):
            username = username.strip()
            if username:
                data = harvest_account(username, client=client)
                if data:
                    harvested[username.lower()] = data

    elif args.overlap:
        partition_path = Path(args.overlap)
        with open(partition_path) as f:
            partition = json.load(f)
        harvested = harvest_network_overlap(partition, client=client)

    elif args.all:
        accounts = client.list_accounts()
        for acct in accounts:
            username = acct.get("username")
            if username:
                try:
                    data = harvest_account(username, client=client)
                    if data:
                        harvested[username.lower()] = data
                except Exception as e:
                    logger.error("Failed %s: %s", username, e)

    else:
        parser.print_help()
        return

    if not harvested:
        logger.warning("No data harvested.")
        return

    logger.info("Harvested %d accounts", len(harvested))

    if args.analyze or args.overlap:
        _run_analysis(harvested)


def _run_analysis(harvested: dict) -> None:
    """Build graph, run influence_flow and content_overlay, save results."""
    from holespawn.ingest.community_archive import to_holespawn_graph, extract_content
    from holespawn.network.graph_builder import build_graph
    from holespawn.network.content_overlay import analyze_content_overlay
    from holespawn.network.influence_flow import analyze_influence

    INTEL_DIR.mkdir(parents=True, exist_ok=True)

    # Build graph
    graph_input = to_holespawn_graph(harvested)
    logger.info(
        "Graph input: %d tweets, %d follower lists, %d edge maps",
        len(graph_input["tweets"]), len(graph_input["followers"]), len(graph_input["edge_map"]),
    )
    graph_spec = build_graph(**graph_input)
    logger.info("Graph: %d nodes, %d edges", graph_spec.node_count, graph_spec.edge_count)

    # Save graph metadata
    with open(INTEL_DIR / "graph_spec.json", "w") as f:
        json.dump(graph_spec.to_dict(), f, indent=2, default=str)

    # Content overlay analysis
    content_tweets = extract_content(harvested)
    logger.info("Content corpus: %d tweets", len(content_tweets))
    content_report = analyze_content_overlay(graph_spec.graph, content_tweets)
    with open(INTEL_DIR / "content_overlay.json", "w") as f:
        json.dump(content_report.to_dict(), f, indent=2, default=str)

    # Influence flow analysis
    try:
        influence_report = analyze_influence(graph_spec.graph)
        with open(INTEL_DIR / "influence_flow.json", "w") as f:
            json.dump(influence_report, f, indent=2, default=str)
    except Exception as e:
        logger.error("Influence analysis failed: %s", e)

    # Save harvested account list
    account_summary = {
        username: {
            "tweets": len(d.get("tweets", [])),
            "followers": len(d.get("followers", [])),
            "following": len(d.get("following", [])),
        }
        for username, d in harvested.items()
    }
    with open(INTEL_DIR / "account_summary.json", "w") as f:
        json.dump(account_summary, f, indent=2)

    logger.info("Intel saved to %s", INTEL_DIR)


if __name__ == "__main__":
    main()
