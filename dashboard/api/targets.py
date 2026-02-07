"""
Target management API: CRUD, profile queue, scrape, NLP.
"""

import json
from flask import Blueprint, jsonify, request

from dashboard.db import get_db
from dashboard.db import operations as ops
from dashboard.services.queue import JobQueue
from .auth import login_required, _audit

targets_bp = Blueprint("targets", __name__, url_prefix="/api/targets")


def _serialize_target(t):
    return {
        "id": t.id,
        "identifier": t.identifier,
        "platform": t.platform,
        "status": t.status,
        "priority": t.priority,
        "raw_data": ops._json_load(t.raw_data),
        "profile": ops._json_load(t.profile),
        "nlp_metrics": ops._json_load(t.nlp_metrics),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "profiled_at": t.profiled_at.isoformat() if t.profiled_at else None,
        "deployed_at": t.deployed_at.isoformat() if t.deployed_at else None,
        "last_updated": t.last_updated.isoformat() if t.last_updated else None,
        "tags": ops._json_load(t.tags),
        "notes": t.notes,
    }


@targets_bp.route("", methods=["GET"])
@login_required
def list_targets():
    status = request.args.get("status")
    platform = request.args.get("platform")
    tags = request.args.get("tags")
    limit = int(request.args.get("limit") or 100)
    offset = int(request.args.get("offset") or 0)
    with get_db() as db:
        items = ops.list_targets(db, status=status, platform=platform, tags_contains=tags, limit=limit, offset=offset)
        return jsonify([_serialize_target(t) for t in items])


@targets_bp.route("", methods=["POST"])
@login_required
def create_target():
    data = request.get_json() or {}
    identifier = (data.get("identifier") or "").strip()
    if not identifier:
        return jsonify({"error": "identifier required"}), 400
    with get_db() as db:
        if ops.get_target_by_identifier(db, identifier):
            return jsonify({"error": "Target already exists"}), 409
        t = ops.create_target(
            db,
            identifier=identifier,
            platform=data.get("platform"),
            priority=int(data.get("priority") or 0),
            tags=data.get("tags"),
            notes=data.get("notes"),
        )
        _audit("target_create", t.id, {"identifier": identifier})
        return jsonify(_serialize_target(t)), 201


@targets_bp.route("/<int:target_id>", methods=["GET"])
@login_required
def get_target(target_id):
    with get_db() as db:
        t = ops.get_target(db, target_id)
        if not t:
            return jsonify({"error": "Not found"}), 404
        return jsonify(_serialize_target(t))


@targets_bp.route("/<int:target_id>", methods=["PATCH"])
@login_required
def update_target(target_id):
    data = request.get_json() or {}
    allowed = {"platform", "status", "priority", "tags", "notes", "raw_data", "profile", "nlp_metrics", "profiled_at", "deployed_at"}
    kwargs = {k: data[k] for k in allowed if k in data}
    with get_db() as db:
        t = ops.update_target(db, target_id, **kwargs)
        if not t:
            return jsonify({"error": "Not found"}), 404
        _audit("target_update", target_id, kwargs)
        return jsonify(_serialize_target(t))


@targets_bp.route("/<int:target_id>", methods=["DELETE"])
@login_required
def delete_target(target_id):
    with get_db() as db:
        t = ops.get_target(db, target_id)
        if not t:
            return jsonify({"error": "Not found"}), 404
        ops.delete_target(db, target_id)
        _audit("target_delete", target_id, {"identifier": t.identifier})
        return jsonify({"ok": True})


@targets_bp.route("/<int:target_id>/profile", methods=["POST"])
@login_required
def queue_profile(target_id):
    with get_db() as db:
        if not ops.get_target(db, target_id):
            return jsonify({"error": "Not found"}), 404
    q = JobQueue()
    job_id = q.enqueue("profile", target_id=target_id, params=request.get_json(), priority=1)
    _audit("queue_profile", target_id, {"job_id": job_id})
    return jsonify({"job_id": job_id})


@targets_bp.route("/<int:target_id>/scrape", methods=["POST"])
@login_required
def queue_scrape(target_id):
    with get_db() as db:
        if not ops.get_target(db, target_id):
            return jsonify({"error": "Not found"}), 404
    q = JobQueue()
    job_id = q.enqueue("scrape", target_id=target_id, params=request.get_json())
    _audit("queue_scrape", target_id, {"job_id": job_id})
    return jsonify({"job_id": job_id})


@targets_bp.route("/<int:target_id>/profile", methods=["GET"])
@login_required
def get_profile(target_id):
    with get_db() as db:
        t = ops.get_target(db, target_id)
        if not t:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"profile": ops._json_load(t.profile)})


@targets_bp.route("/<int:target_id>/nlp", methods=["GET"])
@login_required
def get_nlp(target_id):
    with get_db() as db:
        t = ops.get_target(db, target_id)
        if not t:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"nlp_metrics": ops._json_load(t.nlp_metrics)})
