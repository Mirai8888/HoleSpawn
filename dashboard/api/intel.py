"""
Intelligence API: networks, cluster, vulnerabilities, effectiveness patterns.
"""

from flask import Blueprint, jsonify, request

from dashboard.db import get_db
from dashboard.db import operations as ops
from dashboard.services.analytics import AnalyticsEngine
from dashboard.services.network_analysis import NetworkAnalysisService

from .auth import login_required

intel_bp = Blueprint("intel", __name__, url_prefix="/api/intel")


@intel_bp.route("/networks", methods=["GET"])
@login_required
def list_networks():
    try:
        limit = int(request.args.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))
    with get_db() as db:
        items = ops.list_networks(db, limit=limit)
        return jsonify([{
            "id": n.id,
            "name": n.name,
            "platform": n.platform,
            "node_count": n.node_count,
            "edge_count": n.edge_count,
            "scraped_at": n.scraped_at.isoformat() if n.scraped_at else None,
        } for n in items])


@intel_bp.route("/networks", methods=["POST"])
@login_required
def create_network():
    data = request.get_json() or {}
    dir_path = data.get("dir_path") or data.get("path")
    name = data.get("name")
    if not dir_path:
        return jsonify({"error": "dir_path required"}), 400
    svc = NetworkAnalysisService()
    network_id = svc.build_from_profiles_dir(dir_path, name=name)
    if network_id is None:
        return jsonify({"error": "Failed to build network (no profiles or analyzer error)"}), 500
    return jsonify({"id": network_id}, 201)


@intel_bp.route("/networks/<int:network_id>", methods=["GET"])
@login_required
def get_network(network_id):
    svc = NetworkAnalysisService()
    out = svc.get_network_graph(network_id)
    if not out:
        return jsonify({"error": "Not found"}), 404
    return jsonify(out)


@intel_bp.route("/networks/<int:network_id>/communities", methods=["GET"])
@login_required
def get_communities(network_id):
    with get_db() as db:
        n = ops.get_network(db, network_id)
        if not n:
            return jsonify({"error": "Not found"}), 404
        comm = ops._json_load(n.communities)
        return jsonify(comm or {})


@intel_bp.route("/networks/<int:network_id>/central", methods=["GET"])
@login_required
def get_central(network_id):
    with get_db() as db:
        n = ops.get_network(db, network_id)
        if not n:
            return jsonify({"error": "Not found"}), 404
        return jsonify({
            "central_nodes": ops._json_load(n.central_nodes),
            "influence_map": ops._json_load(n.influence_map),
        })


@intel_bp.route("/cluster", methods=["POST"])
@login_required
def cluster_targets():
    """Cluster targets by psychology (stub: returns empty until we have profile vectors)."""
    return jsonify({"clusters": [], "message": "Wire to profile similarity / NLP clustering"})


@intel_bp.route("/vulnerabilities", methods=["GET"])
@login_required
def vulnerabilities():
    """Aggregate vulnerability patterns from profiles (stub)."""
    return jsonify({"patterns": [], "message": "Wire to NLP vulnerability extraction"})


@intel_bp.route("/effectiveness", methods=["GET"])
@login_required
def effectiveness_patterns():
    """What trap patterns work best."""
    engine = AnalyticsEngine()
    patterns = engine.identify_patterns()
    return jsonify(patterns)
