"""
Visit tracking API: called by tracker.js injected into traps.
POST /api/track/start, POST /api/track/end (no auth so traps can report).
"""

from flask import Blueprint, jsonify, request

from dashboard.db import get_db
from dashboard.db import operations as ops
from dashboard.services.monitor import get_monitor

track_bp = Blueprint("track", __name__, url_prefix="/api/track")


def _get_monitor_with_emit():
    """Return monitor; emit can be wired to SocketIO in app."""
    return get_monitor()


def _safe_int(val, default=None):
    """Coerce to int; return default on failure."""
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


@track_bp.route("/start", methods=["POST"])
def track_start():
    """Record visit start. Called by tracker.js."""
    data = request.get_json() or {}
    trap_id = _safe_int(data.get("trap_id"))
    if trap_id is None:
        return jsonify({"error": "trap_id required"}), 400
    with get_db() as db:
        trap = ops.get_trap(db, trap_id)
        if not trap:
            return jsonify({"error": "trap not found"}), 404
        target_id = trap.target_id
    monitor = _get_monitor_with_emit()
    visit_id = monitor.track_visit_start(
        trap_id=trap_id,
        target_id=target_id,
        session_id=data.get("session_id"),
        visitor_fingerprint=data.get("fingerprint"),
        entry_page=data.get("entry_page"),
        referrer=data.get("referrer"),
        utm_params=data.get("utm_params"),
    )
    if visit_id is None:
        return jsonify({"error": "failed to record"}), 500
    return jsonify({"visit_id": visit_id, "ok": True})


@track_bp.route("/end", methods=["POST"])
def track_end():
    """Record visit end. Called by tracker.js."""
    data = request.get_json() or {}
    trap_id = _safe_int(data.get("trap_id"))
    session_id = data.get("session_id")
    if trap_id is None or session_id is None:
        return jsonify({"error": "trap_id and session_id required"}), 400
    try:
        duration = float(data.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    depth_raw = data.get("depth")
    try:
        depth = int(depth_raw) if depth_raw is not None else None
    except (TypeError, ValueError):
        depth = None
    monitor = _get_monitor_with_emit()
    visit = monitor.track_visit_end(
        trap_id=trap_id,
        session_id=session_id,
        duration=duration,
        exit_page=data.get("exit_page"),
        pages_visited=data.get("pages_visited"),
        depth=depth,
        scroll_depth=data.get("max_scroll"),  # can be a dict or single value
        clicks=data.get("clicks"),
        time_per_page=data.get("time_per_page"),
    )
    if visit is None:
        return jsonify({"error": "visit not found or already ended"}), 404
    return jsonify({"ok": True})
