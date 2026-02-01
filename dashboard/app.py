"""
HoleSpawn dashboard: list profiles, agenda search, network reports.
Run: python -m dashboard.app (or flask --app dashboard.app run)
"""

import json
import os
import sqlite3
from pathlib import Path

# Project root (parent of dashboard/)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

# Load .env before Flask so API keys are set. Windows often saves .env as UTF-16.
os.environ.setdefault("FLASK_SKIP_DOTENV", "1")
try:
    from dotenv import load_dotenv
    _env_path = ROOT / ".env"
    if _env_path.exists():
        try:
            with open(_env_path, encoding="utf-8") as f:
                load_dotenv(stream=f)
        except UnicodeDecodeError:
            with open(_env_path, encoding="utf-16") as f:
                load_dotenv(stream=f)
    else:
        load_dotenv(_env_path)
except ImportError:
    pass

from flask import Flask, jsonify, request, send_from_directory

# DB path: env or default
def _db_path() -> Path:
    p = os.getenv("HOLESPAWN_DB", "")
    if p:
        return Path(p)
    return ROOT / "outputs" / "holespawn.sqlite"


app = Flask(__name__, static_folder="static")


def _get_db():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        from holespawn.db import init_db
        init_db(path)
    return sqlite3.connect(str(path))


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/profiles")
def list_profiles():
    try:
        conn = _get_db()
        try:
            rows = conn.execute(
                """SELECT run_id, source_username, created_at, data_source, output_dir,
                          (engagement_brief IS NOT NULL AND trim(engagement_brief) != '') AS has_brief
                   FROM profiles ORDER BY created_at DESC"""
            ).fetchall()
            return jsonify([
            {
                "run_id": r[0],
                "source_username": r[1],
                "created_at": r[2],
                "data_source": r[3],
                "output_dir": r[4],
                "has_brief": bool(r[5]),
            }
            for r in rows
        ])
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profiles/<run_id>/repair", methods=["POST"])
def repair_profile_brief(run_id: str):
    """Regenerate engagement brief from stored behavioral matrix (no raw content). Requires LLM API key."""
    try:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT behavioral_matrix FROM profiles WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row or not row[0]:
                return jsonify({"error": "Profile not found"}), 404
            matrix_text = row[0]
        finally:
            conn.close()
        profile_dict = json.loads(matrix_text)
        from holespawn.engagement import get_engagement_brief_from_profile
        brief = get_engagement_brief_from_profile(profile_dict)
        conn = _get_db()
        try:
            conn.execute(
                "UPDATE profiles SET engagement_brief = ? WHERE run_id = ?",
                (brief.strip(), run_id),
            )
            conn.commit()
            return jsonify({"ok": True, "brief": brief.strip()})
        finally:
            conn.close()
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid profile data: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profiles/<run_id>/brief")
def get_profile_brief(run_id: str):
    try:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT engagement_brief FROM profiles WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row or not row[0]:
                return jsonify({"brief": None}), 404
            return jsonify({"brief": row[0]})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search", methods=["POST"])
def search():
    try:
        body = request.get_json() or {}
        agenda = (body.get("agenda") or "").strip()
        limit = int(body.get("limit") or 20)
        if not agenda:
            return jsonify({"error": "agenda required"}), 400
        from holespawn.db import search_by_agenda
        results = search_by_agenda(agenda, _db_path(), limit=limit)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/network_reports")
def list_network_reports():
    try:
        conn = _get_db()
        try:
            rows = conn.execute(
                """SELECT run_id, created_at, source, output_dir
                   FROM network_reports ORDER BY created_at DESC"""
            ).fetchall()
            return jsonify([
                {"run_id": r[0], "created_at": r[1], "source": r[2], "output_dir": r[3]}
                for r in rows
            ])
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/network_reports/<run_id>/brief")
def get_network_brief(run_id: str):
    try:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT brief_text FROM network_reports WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row or not row[0]:
                return jsonify({"brief": None}), 404
            return jsonify({"brief": row[0]})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import threading
    import webbrowser

    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:5000")

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
