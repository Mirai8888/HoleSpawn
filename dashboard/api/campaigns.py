"""
Campaign orchestration API: CRUD, add/remove targets, start/pause, status.
"""

from datetime import datetime
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from dashboard.db import get_db
from dashboard.db import operations as ops
from dashboard.services.analytics import AnalyticsEngine

from .auth import login_required, _audit


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse ISO datetime string to datetime; return None if invalid or not a string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/api/campaigns")


def _serialize_campaign(c):
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "goal": c.goal,
        "target_network": c.target_network,
        "campaign_type": c.campaign_type,
        "orchestration_plan": ops._json_load(c.orchestration_plan),
        "status": c.status,
        "started_at": c.started_at.isoformat() if c.started_at else None,
        "ends_at": c.ends_at.isoformat() if c.ends_at else None,
        "total_targets": c.total_targets,
        "deployed_traps": c.deployed_traps,
        "total_engagement": c.total_engagement,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@campaigns_bp.route("", methods=["GET"])
@login_required
def list_campaigns():
    status = request.args.get("status")
    limit = int(request.args.get("limit") or 50)
    with get_db() as db:
        items = ops.list_campaigns(db, status=status, limit=limit)
        return jsonify([_serialize_campaign(c) for c in items])


@campaigns_bp.route("", methods=["POST"])
@login_required
def create_campaign():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    with get_db() as db:
        c = ops.create_campaign(
            db,
            name=name,
            description=data.get("description"),
            goal=data.get("goal"),
            target_network=data.get("target_network"),
            campaign_type=data.get("campaign_type"),
            orchestration_plan=data.get("orchestration_plan"),
        )
        _audit("campaign_create", None, {"campaign_id": c.id, "name": name})
        return jsonify(_serialize_campaign(c)), 201


@campaigns_bp.route("/<int:campaign_id>", methods=["GET"])
@login_required
def get_campaign(campaign_id):
    with get_db() as db:
        c = ops.get_campaign(db, campaign_id)
        if not c:
            return jsonify({"error": "Not found"}), 404
        out = _serialize_campaign(c)
        # Include target memberships
        out["targets"] = [
            {"target_id": ct.target_id, "phase": ct.phase, "status": ct.status, "scheduled_deploy": ct.scheduled_deploy.isoformat() if ct.scheduled_deploy else None}
            for ct in c.targets
        ]
        return jsonify(out)


@campaigns_bp.route("/<int:campaign_id>", methods=["PATCH"])
@login_required
def update_campaign(campaign_id):
    data = request.get_json() or {}
    allowed = {"name", "description", "goal", "target_network", "campaign_type", "orchestration_plan", "status", "started_at", "ends_at", "total_targets", "deployed_traps", "total_engagement"}
    kwargs = {k: data[k] for k in allowed if k in data}
    with get_db() as db:
        c = ops.get_campaign(db, campaign_id)
        if not c:
            return jsonify({"error": "Not found"}), 404
        for k, v in kwargs.items():
            if not hasattr(c, k):
                continue
            if k == "orchestration_plan" and v is not None and not isinstance(v, str):
                v = ops._json_dump(v)
            if k in ("started_at", "ends_at") and isinstance(v, str):
                try:
                    v = datetime.fromisoformat(v.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
            setattr(c, k, v)
        db.commit()
        db.refresh(c)
        _audit("campaign_update", None, {"campaign_id": campaign_id, **kwargs})
        return jsonify(_serialize_campaign(c))


@campaigns_bp.route("/<int:campaign_id>", methods=["DELETE"])
@login_required
def delete_campaign(campaign_id):
    with get_db() as db:
        c = ops.get_campaign(db, campaign_id)
        if not c:
            return jsonify({"error": "Not found"}), 404
        db.delete(c)
        db.commit()
        _audit("campaign_delete", None, {"campaign_id": campaign_id})
        return jsonify({"ok": True})


@campaigns_bp.route("/<int:campaign_id>/targets", methods=["POST"])
@login_required
def add_targets(campaign_id):
    data = request.get_json() or {}
    target_ids = data.get("target_ids") or data.get("target_id")
    if target_ids is None:
        target_ids = [data.get("target_id")]
    if not target_ids:
        return jsonify({"error": "target_id or target_ids required"}), 400
    if isinstance(target_ids, int):
        target_ids = [target_ids]
    added = []
    with get_db() as db:
        if not ops.get_campaign(db, campaign_id):
            return jsonify({"error": "Campaign not found"}), 404
        for tid in target_ids:
            ct = ops.add_target_to_campaign(
                db,
                campaign_id,
                tid,
                phase=data.get("phase", 0),
                scheduled_deploy=_parse_datetime(data.get("scheduled_deploy")),
                custom_messaging=data.get("custom_messaging"),
            )
            if ct:
                added.append(tid)
    _audit("campaign_add_targets", None, {"campaign_id": campaign_id, "target_ids": added})
    return jsonify({"added": added})


@campaigns_bp.route("/<int:campaign_id>/targets/<int:target_id>", methods=["DELETE"])
@login_required
def remove_target(campaign_id, target_id):
    with get_db() as db:
        if not ops.get_campaign(db, campaign_id):
            return jsonify({"error": "Campaign not found"}), 404
        ok = ops.remove_target_from_campaign(db, campaign_id, target_id)
        if not ok:
            return jsonify({"error": "Target not in campaign"}), 404
    _audit("campaign_remove_target", None, {"campaign_id": campaign_id, "target_id": target_id})
    return jsonify({"ok": True})


@campaigns_bp.route("/<int:campaign_id>/start", methods=["POST"])
@login_required
def start_campaign(campaign_id):
    with get_db() as db:
        c = ops.get_campaign(db, campaign_id)
        if not c:
            return jsonify({"error": "Not found"}), 404
        c.status = "active"
        c.started_at = c.started_at or datetime.utcnow()
        db.commit()
        db.refresh(c)
    _audit("campaign_start", None, {"campaign_id": campaign_id})
    return jsonify(_serialize_campaign(c))


@campaigns_bp.route("/<int:campaign_id>/pause", methods=["POST"])
@login_required
def pause_campaign(campaign_id):
    with get_db() as db:
        c = ops.get_campaign(db, campaign_id)
        if not c:
            return jsonify({"error": "Not found"}), 404
        c.status = "paused"
        db.commit()
        db.refresh(c)
    _audit("campaign_pause", None, {"campaign_id": campaign_id})
    return jsonify(_serialize_campaign(c))


@campaigns_bp.route("/<int:campaign_id>/status", methods=["GET"])
@login_required
def campaign_status(campaign_id):
    with get_db() as db:
        c = ops.get_campaign(db, campaign_id)
        if not c:
            return jsonify({"error": "Not found"}), 404
    engine = AnalyticsEngine()
    metrics = engine.aggregate_campaign_metrics(campaign_id)
    return jsonify({
        "campaign": _serialize_campaign(c),
        "metrics": metrics,
    })
