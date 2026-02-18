"""Job queue API: list and status (for dashboard)."""

from flask import Blueprint, jsonify, request

from dashboard.db import get_db
from dashboard.db import operations as ops
from dashboard.services.queue import JobQueue

from .auth import login_required

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@jobs_bp.route("", methods=["GET"])
@login_required
def list_jobs():
    status_filter = request.args.get("status")
    job_type = request.args.get("job_type")
    try:
        limit = int(request.args.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))
    with get_db() as db:
        items = ops.list_jobs(db, status=status_filter, job_type=job_type, limit=limit)
        return jsonify([{
            "id": j.id,
            "job_type": j.job_type,
            "target_id": j.target_id,
            "status": j.status,
            "progress": j.progress,
            "error": j.error,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        } for j in items])


@jobs_bp.route("/<int:job_id>", methods=["GET"])
@login_required
def get_job(job_id):
    q = JobQueue()
    out = q.get_status(job_id)
    if not out:
        return jsonify({"error": "Not found"}), 404
    return jsonify(out)


@jobs_bp.route("/<int:job_id>/run", methods=["POST"])
@login_required
def run_job(job_id):
    q = JobQueue()
    if q.process_one(job_id):
        return jsonify({"ok": True, "job_id": job_id})
    return jsonify({"error": "Job not found or not queued"}), 404
