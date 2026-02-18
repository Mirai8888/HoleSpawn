"""
Network analysis service: wrap holespawn network analyzer, persist to C2 Network model.
"""

from pathlib import Path
from typing import Any

from dashboard.db import get_db
from dashboard.db import operations as ops


def _ensure_sys_path():
    import sys
    root = Path(__file__).resolve().parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


class NetworkAnalysisService:
    """Build network graphs and store in C2 networks table."""

    def build_from_profiles_dir(self, dir_path: str, name: str | None = None) -> int | None:
        """
        Load profiles from directory, run community/centrality via NetworkAnalyzer, save as Network.
        Returns network_id or None.
        """
        _ensure_sys_path()
        try:
            from holespawn.network.analyzer import NetworkAnalyzer, load_profiles_from_dir
        except ImportError:
            return None

        profiles = load_profiles_from_dir(dir_path)
        if not profiles:
            return None

        analyzer = NetworkAnalyzer()
        report = analyzer.analyze_network(profiles, edges=None, use_community_detection=True)
        ids = list(profiles.keys())

        node_list = [{"id": i, "label": i} for i in ids]
        # Report doesn't return edge list; store clusters and central accounts
        communities = report.get("clusters") or []
        central_nodes = report.get("central_accounts") or []
        influence_map = report.get("betweenness_centrality") or {}
        # Build placeholder edges from clusters (same-cluster pairs) for viz if needed; else empty
        edge_list: list[dict[str, Any]] = []

        with get_db() as db:
            n = ops.create_network(
                db,
                name=name or Path(dir_path).name,
                nodes=node_list,
                edges=edge_list,
                platform="file",
                communities={"communities": communities},
                central_nodes=central_nodes,
                influence_map=influence_map,
            )
            return n.id

    def get_network_graph(self, network_id: int) -> dict[str, Any]:
        """Return nodes, edges, communities for frontend viz."""
        with get_db() as db:
            n = ops.get_network(db, network_id)
            if not n:
                return {}
            return {
                "id": n.id,
                "name": n.name,
                "nodes": ops._json_load(n.nodes),
                "edges": ops._json_load(n.edges),
                "communities": ops._json_load(n.communities),
                "central_nodes": ops._json_load(n.central_nodes),
                "influence_map": ops._json_load(n.influence_map),
                "platform": n.platform,
                "node_count": n.node_count,
                "edge_count": n.edge_count,
                "scraped_at": n.scraped_at.isoformat() if n.scraped_at else None,
            }
