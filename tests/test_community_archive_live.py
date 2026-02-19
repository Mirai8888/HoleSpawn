#!/usr/bin/env python3
"""
Live test of Community Archive adapter against Supabase API.
Fetches real data, builds graph, runs influence_flow + vulnerability.

2026-02-19 - test-fire run
"""

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.home() / "HoleSpawn"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ca-test")

OUTPUT_DIR = Path.home() / "HoleSpawn" / "data" / "community-archive-test-2026-02-19"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

bugs_found = []

def save_json(name, data):
    path = OUTPUT_DIR / name
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Saved %s", path)

# ---- Step 1: Connect to API and list accounts ----
logger.info("=== Step 1: Connect and list accounts ===")

from holespawn.ingest.community_archive import CommunityArchiveClient

client = CommunityArchiveClient(page_size=100, rate_limit_delay=0.3)

try:
    accounts = client.list_accounts()
    logger.info("Found %d accounts in archive", len(accounts))
    save_json("accounts_sample.json", accounts[:10])
except Exception as e:
    logger.error("Failed to list accounts: %s", e)
    bugs_found.append(f"list_accounts failed: {e}")
    accounts = []

if not accounts:
    logger.error("No accounts found, cannot continue")
    sys.exit(1)

# Pick a seed account - find one with a reasonable username
seed_account = None
for a in accounts:
    uname = a.get("username", "")
    if uname and len(uname) > 2:
        seed_account = a
        break

if not seed_account:
    seed_account = accounts[0]

seed_username = seed_account["username"]
seed_account_id = seed_account["account_id"]
logger.info("Seed account: %s (id=%s)", seed_username, seed_account_id)

# ---- Step 2: Fetch follow graph sample ----
logger.info("=== Step 2: Fetch follow graph for seed ===")

try:
    following = client.get_following(str(seed_account_id))
    logger.info("Following count: %d", len(following))
    # Cap at 100 for test
    following_sample = following[:100]
    save_json("following_sample.json", following_sample)
except Exception as e:
    logger.error("get_following failed: %s", e)
    bugs_found.append(f"get_following failed: {e}")
    following_sample = []

try:
    followers = client.get_followers(str(seed_account_id))
    logger.info("Follower count: %d", len(followers))
    followers_sample = followers[:100]
    save_json("followers_sample.json", followers_sample)
except Exception as e:
    logger.error("get_followers failed: %s", e)
    bugs_found.append(f"get_followers failed: {e}")
    followers_sample = []

# ---- Step 3: Fetch some tweets to find quote chains ----
logger.info("=== Step 3: Fetch tweets ===")

try:
    tweets = client.get_tweets(str(seed_account_id), limit=50)
    logger.info("Fetched %d tweets for %s", len(tweets), seed_username)
    save_json("tweets_sample.json", tweets[:10])
except Exception as e:
    logger.error("get_tweets failed: %s", e)
    bugs_found.append(f"get_tweets failed: {e}")
    tweets = []

# ---- Step 4: Use CommunityArchiveSource to build social graph ----
logger.info("=== Step 4: Build social graph via adapter ===")

from holespawn.network.community_archive import CommunityArchiveSource

source = CommunityArchiveSource(client=client)

# Pick 2-3 accounts for graph building (seed + a couple from following)
graph_usernames = [seed_username]

# Find other archived accounts that our seed follows
if following_sample:
    # following records have account_id of who is followed
    # We need to find which of those are also in the archive
    archived_ids = {str(a.get("account_id", "")) for a in accounts}
    for f in following_sample[:50]:
        fid = str(f.get("following_account_id", ""))
        if fid in archived_ids:
            # Find username for this id
            for a in accounts:
                if str(a.get("account_id", "")) == fid:
                    graph_usernames.append(a["username"])
                    break
        if len(graph_usernames) >= 3:
            break

logger.info("Building graph for: %s", graph_usernames)

try:
    t0 = time.time()
    graph_spec = source.build_social_graph(graph_usernames)
    elapsed = time.time() - t0
    logger.info(
        "Graph built in %.1fs: %d nodes, %d edges, types=%s",
        elapsed, graph_spec.node_count, graph_spec.edge_count,
        graph_spec.edge_type_counts,
    )
    save_json("graph_spec.json", graph_spec.to_dict())
except Exception as e:
    logger.error("build_social_graph failed: %s", e)
    bugs_found.append(f"build_social_graph failed: {e}")
    graph_spec = None

# ---- Step 5: Run influence_flow ----
if graph_spec and graph_spec.graph.number_of_nodes() > 0:
    logger.info("=== Step 5: Influence flow analysis ===")

    from holespawn.network.influence_flow import analyze_influence_flow

    try:
        t0 = time.time()
        influence = analyze_influence_flow(graph_spec.graph)
        elapsed = time.time() - t0
        logger.info("Influence analysis done in %.1fs", elapsed)

        # Top 5 by influence score
        sorted_scores = sorted(
            influence.influence_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        logger.info("Top 5 influential nodes:")
        for node, score in sorted_scores:
            breakdown = influence.influence_breakdown.get(node, {})
            logger.info("  %s: %.4f (seed=%.3f amp=%.3f bridge=%.3f reach=%.3f)",
                        node, score,
                        breakdown.get("seeding", 0),
                        breakdown.get("amplification", 0),
                        breakdown.get("bridging", 0),
                        breakdown.get("reach", 0))

        logger.info("Narrative seeds: %d", len(influence.seeds))
        logger.info("Amplification chains: %d", len(influence.amplification_chains))
        logger.info("Bridge nodes: %d", len(influence.bridge_nodes))

        save_json("influence_report.json", influence.to_dict())
    except Exception as e:
        logger.error("influence_flow failed: %s", e)
        bugs_found.append(f"influence_flow failed: {e}")
        import traceback
        traceback.print_exc()

    # ---- Step 6: Vulnerability analysis ----
    logger.info("=== Step 6: Vulnerability analysis ===")

    from holespawn.network.vulnerability import analyze_vulnerability

    try:
        t0 = time.time()
        vuln = analyze_vulnerability(graph_spec.graph)
        elapsed = time.time() - t0
        logger.info("Vulnerability analysis done in %.1fs", elapsed)

        logger.info("Fragmentation results: %d nodes tested", len(vuln.fragmentation))
        if vuln.fragmentation:
            top_frag = vuln.fragmentation[0]
            logger.info("  Most fragmenting node: %s (ratio=%.4f)",
                        top_frag.node, top_frag.fragmentation_ratio)

        logger.info("Single points of failure: %d", len(vuln.single_points_of_failure))
        for spof in vuln.single_points_of_failure[:5]:
            logger.info("  %s (betweenness=%.4f, degree=%d)",
                        spof["node"], spof["betweenness"], spof["degree"])

        logger.info("Community cohesion: %d communities", len(vuln.community_cohesion))
        for c in vuln.community_cohesion:
            logger.info("  Community %d: size=%d, cohesion=%.4f, density=%.4f",
                        c.community_id, c.size, c.cohesion, c.density)

        logger.info("Attack surface: %d steps to target fragmentation",
                    len(vuln.attack_surfaces))

        save_json("vulnerability_report.json", vuln.to_dict())
    except Exception as e:
        logger.error("vulnerability analysis failed: %s", e)
        bugs_found.append(f"vulnerability analysis failed: {e}")
        import traceback
        traceback.print_exc()

# ---- Step 7: Quote chain test ----
logger.info("=== Step 7: Quote chain test ===")

if tweets:
    test_tweet_ids = [str(t.get("tweet_id", "")) for t in tweets[:3] if t.get("tweet_id")]
    if test_tweet_ids:
        try:
            chains = source.fetch_quote_chains(test_tweet_ids)
            logger.info("Quote chains fetched: %d", len(chains))
            for c in chains:
                logger.info("  Tweet %s by %s: %d quotes (%d non-self)",
                            c.original_tweet_id, c.original_author,
                            len(c.quotes), c.non_self_quote_count)
            save_json("quote_chains.json", [c.to_dict() for c in chains])
        except Exception as e:
            logger.error("fetch_quote_chains failed: %s", e)
            bugs_found.append(f"fetch_quote_chains failed: {e}")
            import traceback
            traceback.print_exc()

# ---- Summary ----
logger.info("=== SUMMARY ===")
if graph_spec:
    logger.info("Node count: %d", graph_spec.node_count)
    logger.info("Edge count: %d", graph_spec.edge_count)
    logger.info("Edge types: %s", graph_spec.edge_type_counts)

if bugs_found:
    logger.warning("BUGS FOUND: %d", len(bugs_found))
    for b in bugs_found:
        logger.warning("  - %s", b)
else:
    logger.info("No bugs found!")

save_json("bugs.json", bugs_found)

# Save full summary
summary = {
    "seed_account": seed_username,
    "graph_usernames": graph_usernames if 'graph_usernames' in dir() else [],
    "node_count": graph_spec.node_count if graph_spec else 0,
    "edge_count": graph_spec.edge_count if graph_spec else 0,
    "edge_types": graph_spec.edge_type_counts if graph_spec else {},
    "bugs_found": bugs_found,
    "output_dir": str(OUTPUT_DIR),
}
save_json("summary.json", summary)
logger.info("All results saved to %s", OUTPUT_DIR)
