# Code Review: `holespawn/network/` Module

**Date:** 2026-02-18  
**Files reviewed:** graph_builder.py, influence_flow.py, vulnerability.py, temporal.py, content_overlay.py, \_\_init\_\_.py  
**Tests:** tests/test_network.py (27 tests, all passing before and after changes)

---

## Changes Made

### graph_builder.py
- **Moved `re` import to module level** and pre-compiled regexes (`_RE_RT_PREFIX`, `_RE_MENTION`). Previously `import re` happened inside `_extract_mentions()` on every call.

### influence_flow.py
- **Fixed duplicate amplification chains in `_trace_from_seed()`**. The old code appended a chain at leaf nodes *and* at every intermediate node with predecessors, producing redundant sub-chains for every path prefix. Now only emits chains at true leaves (no unvisited predecessors) or max-depth cutoff. Cycle filtering moved earlier for clarity.

---

## Findings (no change needed)

### graph_builder.py
- **`_parse_twitter_time` fallback formats:** Reasonable defensive parsing. No issues.
- **`_add_edge` weight accumulation:** Correct — repeated edges sum weights.
- **`filter_graph_by_time` copies all node attributes then strips isolates:** Fine for expected graph sizes.

### influence_flow.py
- **`detect_narrative_seeds`:** `sorted(amp_counts, key=amp_counts.get, reverse=True)` — works correctly; `dict.get` returns the value for sorting.
- **`analyze_bridges`:** Betweenness computed on directed graph, communities on undirected — intentional and sensible (bridges control directed flow across structural communities).
- **`compute_influence_scores`:** Eigenvector centrality fallback chain (numpy → iterative → zeros) is good defensive coding. Weight constants (0.35/0.15/0.25/0.25) sum to 1.0 ✓.

### vulnerability.py
- **`analyze_fragmentation` copies undirected graph per candidate node.** O(candidates × (V+E)) memory. Acceptable for expected graph sizes (<10K nodes). For larger graphs, consider copy-once + add-back-node pattern.
- **`map_attack_surface`:** Greedy betweenness removal is correct. Recalculates betweenness each step — O(steps × V × E) but `max_nodes=20` caps it.
- **`find_single_points_of_failure`:** Uses `nx.articulation_points` — exact and efficient.

### temporal.py
- **`track_community_evolution`:** Jaccard matching with greedy 1-to-1 assignment is a reasonable heuristic. Inner loop for unmatched communities scans O(members × communities) — fine for expected sizes.
- **`compare_snapshots`:** Clean set-based diff. Weight change threshold 0.01 is hardcoded — acceptable.

### content_overlay.py
- **`cluster_by_beliefs`:** Adds isolate nodes to similarity graph then filters singleton clusters — minor wasted work, not worth changing.
- **`_STOPWORDS`:** Adequate for English Twitter text. Could be extended but that's feature work.
- **VADER optional import:** Graceful fallback to 0.0 sentiment. Documented implicitly.

### \_\_init\_\_.py
- Clean re-exports. `__all__` matches actual exports. No issues.

### tests/test_network.py
- Good coverage of happy paths and edge cases (empty graph, small graph, empty tweets).
- Missing: test for `filter_graph_by_time` with `start` parameter, test for graphs with cycles in amplification chains, test for `_parse_twitter_time` with invalid input. These are minor gaps.

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| Bug fix  | 1     | Duplicate amplification chains in `_trace_from_seed` |
| Perf     | 1     | Pre-compiled regexes + top-level `re` import |
| Advisory | 1     | `analyze_fragmentation` graph-copy-per-node scales poorly for large graphs |
| Advisory | 1     | Minor test coverage gaps |

Overall quality: **good**. Code is readable, well-structured, with sensible defensive patterns.
