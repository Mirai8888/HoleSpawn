"""
C2 Dashboard API and job queue tests.
Set DASHBOARD_DB before importing dashboard so tests use a temp DB.
"""

import os
import tempfile

import pytest

# Use a temp DB so we don't touch the real c2.sqlite
_test_db = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
_test_db.close()
os.environ["DASHBOARD_DB"] = _test_db.name

# Import after env is set so dashboard uses test DB
from dashboard.app import app
from dashboard.db.session import init_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        with app.app_context():
            init_db()
        # Login (any passphrase works when DASHBOARD_PASSPHRASE not set)
        c.post("/api/auth/login", json={"passphrase": "test"})
        yield c


def test_auth_status(client):
    rv = client.get("/api/auth/status")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get("authenticated") is True


def test_create_target(client):
    rv = client.post(
        "/api/targets",
        json={"identifier": "test_user", "platform": "discord", "notes": "Test target"},
    )
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["identifier"] == "test_user"
    assert data["platform"] == "discord"
    assert "id" in data


def test_list_targets(client):
    client.post("/api/targets", json={"identifier": "u1", "platform": "twitter"})
    rv = client.get("/api/targets")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)
    assert any(t["identifier"] == "u1" for t in data)


def test_create_campaign(client):
    rv = client.post(
        "/api/campaigns",
        json={
            "name": "Test Campaign",
            "description": "Test description",
            "goal": "test",
            "target_network": "test_network",
        },
    )
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["name"] == "Test Campaign"
    assert data["goal"] == "test"
    assert "id" in data


def test_job_queue(client):
    rv = client.post("/api/targets", json={"identifier": "job_test_user", "platform": "discord"})
    assert rv.status_code == 201
    target_id = rv.get_json()["id"]

    rv = client.post(f"/api/targets/{target_id}/profile", json={"use_nlp": True, "use_llm": False})
    assert rv.status_code == 200
    data = rv.get_json()
    assert "job_id" in data

    rv = client.get("/api/jobs")
    assert rv.status_code == 200
    jobs = rv.get_json()
    assert len(jobs) > 0
    assert any(j["job_type"] == "profile" for j in jobs)


def test_unauthorized_rejected():
    """Endpoints require auth when not logged in."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        rv = c.get("/api/targets")
        assert rv.status_code == 401


def test_track_start_requires_trap_id():
    """Track start returns 400 without trap_id."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        rv = c.post("/api/track/start", json={}, headers={"Content-Type": "application/json"})
        assert rv.status_code == 400
