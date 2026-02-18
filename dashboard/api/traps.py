"""
Trap management API: CRUD, deploy, visits, analytics, effectiveness.
"""

from flask import Blueprint, jsonify, request

from dashboard.db import get_db
from dashboard.db import operations as ops
from dashboard.services.monitor import get_monitor

from .auth import _audit, login_required

traps_bp = Blueprint("traps", __name__, url_prefix="/api/traps")


def _serialize_trap(t):
    return {
        "id": t.id,
        "target_id": t.target_id,
        "url": t.url,
        "local_path": t.local_path,
        "deployment_method": t.deployment_method,
        "architecture": t.architecture,
        "design_system": ops._json_load(t.design_system),
        "total_visits": t.total_visits,
        "unique_visitors": t.unique_visitors,
        "avg_session_duration": t.avg_session_duration,
        "avg_depth": t.avg_depth,
        "return_rate": t.return_rate,
        "trap_effectiveness": t.trap_effectiveness,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "last_visit": t.last_visit.isoformat() if t.last_visit else None,
        "campaign_id": t.campaign_id,
    }


def _safe_limit_offset():
    try:
        limit = int(request.args.get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = int(request.args.get("offset") or 0)
    except (TypeError, ValueError):
        offset = 0
    return max(1, min(limit, 500)), max(0, offset)


@traps_bp.route("", methods=["GET"])
@login_required
def list_traps():
    target_id = request.args.get("target_id", type=int)
    campaign_id = request.args.get("campaign_id", type=int)
    is_active = request.args.get("is_active")
    if is_active is not None:
        is_active = is_active.lower() in ("1", "true", "yes")
    limit, offset = _safe_limit_offset()
    with get_db() as db:
        items = ops.list_traps(db, target_id=target_id, campaign_id=campaign_id, is_active=is_active, limit=limit, offset=offset)
        return jsonify([_serialize_trap(t) for t in items])


@traps_bp.route("", methods=["POST"])
@login_required
def create_trap():
    data = request.get_json() or {}
    target_id = data.get("target_id")
    if target_id is None:
        return jsonify({"error": "target_id required"}), 400
    with get_db() as db:
        if not ops.get_target(db, target_id):
            return jsonify({"error": "Target not found"}), 404
        t = ops.create_trap(
            db,
            target_id=target_id,
            url=data.get("url"),
            local_path=data.get("local_path"),
            deployment_method=data.get("deployment_method"),
            architecture=data.get("architecture"),
            design_system=data.get("design_system"),
            campaign_id=data.get("campaign_id"),
        )
        _audit("trap_create", target_id, {"trap_id": t.id})
        return jsonify(_serialize_trap(t)), 201


@traps_bp.route("/<int:trap_id>", methods=["GET"])
@login_required
def get_trap(trap_id):
    with get_db() as db:
        t = ops.get_trap(db, trap_id)
        if not t:
            return jsonify({"error": "Not found"}), 404
        return jsonify(_serialize_trap(t))


@traps_bp.route("/<int:trap_id>", methods=["PATCH"])
@login_required
def update_trap(trap_id):
    data = request.get_json() or {}
    allowed = {"url", "local_path", "deployment_method", "architecture", "design_system", "is_active"}
    kwargs = {k: data[k] for k in allowed if k in data}
    with get_db() as db:
        t = ops.update_trap(db, trap_id, **kwargs)
        if not t:
            return jsonify({"error": "Not found"}), 404
        _audit("trap_update", t.target_id, {"trap_id": trap_id, **kwargs})
        return jsonify(_serialize_trap(t))


@traps_bp.route("/<int:trap_id>", methods=["DELETE"])
@login_required
def delete_trap(trap_id):
    with get_db() as db:
        t = ops.get_trap(db, trap_id)
        if not t:
            return jsonify({"error": "Not found"}), 404
        target_id = t.target_id
        db.delete(t)
        db.commit()
        _audit("trap_delete", target_id, {"trap_id": trap_id})
        return jsonify({"ok": True})


@traps_bp.route("/<int:trap_id>/deploy", methods=["POST"])
@login_required
def deploy_trap(trap_id):
    from dashboard.services.queue import JobQueue
    q = JobQueue()
    job_id = q.enqueue("deploy", target_id=None, params={"trap_id": trap_id, **(request.get_json() or {})}, priority=1)
    _audit("trap_deploy", None, {"trap_id": trap_id, "job_id": job_id})
    return jsonify({"job_id": job_id})


@traps_bp.route("/<int:trap_id>/visits", methods=["GET"])
@login_required
def get_visits(trap_id):
    limit, _ = _safe_limit_offset()
    with get_db() as db:
        t = ops.get_trap(db, trap_id)
        if not t:
            return jsonify({"error": "Not found"}), 404
        visits = ops.get_visits_for_trap(db, trap_id, limit=limit)
        return jsonify([{
            "id": v.id,
            "session_id": v.session_id,
            "started_at": v.started_at.isoformat() if v.started_at else None,
            "ended_at": v.ended_at.isoformat() if v.ended_at else None,
            "duration": v.duration,
            "entry_page": v.entry_page,
            "exit_page": v.exit_page,
            "depth": v.depth,
        } for v in visits])


@traps_bp.route("/<int:trap_id>/analytics", methods=["GET"])
@login_required
def get_analytics(trap_id):
    with get_db() as db:
        t = ops.get_trap(db, trap_id)
        if not t:
            return jsonify({"error": "Not found"}), 404
        visits = ops.get_visits_for_trap(db, trap_id, limit=500)
        durations = [v.duration for v in visits if v.duration is not None]
        depths = [v.depth for v in visits if v.depth is not None]
        return jsonify({
            "trap_id": trap_id,
            "total_visits": t.total_visits,
            "unique_visitors": t.unique_visitors,
            "avg_session_duration": sum(durations) / len(durations) if durations else None,
            "avg_depth": sum(depths) / len(depths) if depths else None,
            "return_rate": t.return_rate,
            "trap_effectiveness": t.trap_effectiveness,
        })


@traps_bp.route("/<int:trap_id>/effectiveness", methods=["GET"])
@login_required
def get_effectiveness(trap_id):
    monitor = get_monitor()
    score = monitor.get_trap_effectiveness(trap_id)
    return jsonify({"trap_id": trap_id, "effectiveness": score})
