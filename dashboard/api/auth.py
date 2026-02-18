"""
Authentication and audit for C2 dashboard.
Passphrase-based; audit log for operations.
"""

import os
from functools import wraps

from flask import Blueprint, jsonify, request, session

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _check_passphrase(passphrase: str) -> bool:
    stored = os.getenv("DASHBOARD_PASSPHRASE")
    if stored:
        return passphrase == stored
    stored_hash = os.getenv("DASHBOARD_PASSPHRASE_HASH")
    if stored_hash:
        try:
            import bcrypt
            h = stored_hash.encode("utf-8") if isinstance(stored_hash, str) else stored_hash
            return bcrypt.checkpw(passphrase.encode("utf-8"), h)
        except Exception:
            return False
    # No auth configured: accept any submission (dev only)
    return True


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapped


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    passphrase = (data.get("passphrase") or "").strip()
    if not _check_passphrase(passphrase):
        return jsonify({"error": "Invalid passphrase"}), 401
    session["authenticated"] = True
    session.permanent = True
    _audit("login", None, {"ip": request.remote_addr})
    return jsonify({"ok": True})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    _audit("logout", None, None)
    session.pop("authenticated", None)
    return jsonify({"ok": True})


@auth_bp.route("/status")
def status():
    return jsonify({"authenticated": session.get("authenticated", False)})


def _audit(operation: str, target_id, details):
    try:
        from dashboard.db import get_db
        from dashboard.db import operations as ops
        with get_db() as db:
            ops.audit_log(db, session.get("session_id"), operation, target_id=target_id, details=details)
    except Exception:
        pass
