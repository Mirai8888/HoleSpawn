"""C2 Dashboard — Flask API for target management, campaign ops, and job queue."""

import json
import os
import uuid
from functools import wraps

from flask import Flask, g, jsonify, request, session

from dashboard.db.session import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("DASHBOARD_SECRET", "dev-secret-key-change-me")

PASSPHRASE = os.environ.get("DASHBOARD_PASSPHRASE", None)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    passphrase = data.get("passphrase", "")
    # If no passphrase configured, any value works (dev mode)
    if PASSPHRASE is None or passphrase == PASSPHRASE:
        session["authenticated"] = True
        return jsonify({"authenticated": True})
    return jsonify({"error": "invalid passphrase"}), 403


@app.route("/api/auth/status")
def auth_status():
    return jsonify({"authenticated": session.get("authenticated", False)})


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

@app.route("/api/targets", methods=["GET"])
@require_auth
def list_targets():
    db = get_db()
    rows = db.execute("SELECT * FROM targets ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/targets", methods=["POST"])
@require_auth
def create_target():
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier")
    platform = data.get("platform", "unknown")
    notes = data.get("notes", "")
    if not identifier:
        return jsonify({"error": "identifier required"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO targets (identifier, platform, notes) VALUES (?, ?, ?)",
        (identifier, platform, notes),
    )
    db.commit()
    row = db.execute("SELECT * FROM targets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@app.route("/api/targets/<int:target_id>", methods=["GET"])
@require_auth
def get_target(target_id):
    db = get_db()
    row = db.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@app.route("/api/campaigns", methods=["GET"])
@require_auth
def list_campaigns():
    db = get_db()
    rows = db.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/campaigns", methods=["POST"])
@require_auth
def create_campaign():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name required"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO campaigns (name, description, goal, target_network) VALUES (?, ?, ?, ?)",
        (name, data.get("description", ""), data.get("goal", ""), data.get("target_network", "")),
    )
    db.commit()
    row = db.execute("SELECT * FROM campaigns WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.route("/api/jobs", methods=["GET"])
@require_auth
def list_jobs():
    db = get_db()
    rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/targets/<int:target_id>/profile", methods=["POST"])
@require_auth
def profile_target(target_id):
    db = get_db()
    target = db.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
    if not target:
        return jsonify({"error": "target not found"}), 404
    data = request.get_json(silent=True) or {}
    job_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO jobs (job_id, job_type, target_id, params, status) VALUES (?, ?, ?, ?, ?)",
        (job_id, "profile", target_id, json.dumps(data), "queued"),
    )
    db.commit()
    return jsonify({"job_id": job_id, "status": "queued"})


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------

@app.route("/api/track/start", methods=["POST"])
def track_start():
    data = request.get_json(silent=True) or {}
    trap_id = data.get("trap_id")
    if not trap_id:
        return jsonify({"error": "trap_id required"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO tracking (trap_id, event_type, metadata) VALUES (?, ?, ?)",
        (trap_id, "start", json.dumps(data)),
    )
    db.commit()
    return jsonify({"status": "tracked"})


# ---------------------------------------------------------------------------
# Init on first request
# ---------------------------------------------------------------------------

@app.before_request
def _ensure_db():
    init_db()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8443, debug=True)
