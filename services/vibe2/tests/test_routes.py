"""Tests for API routes — integration tests with FastAPI TestClient."""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(temp_db):
    """TestClient with patched DB path."""
    with patch("app.db._DB_PATH", temp_db), \
         patch("app.db._sync_schema_initialized", False):
        # Reset async db so init_db uses temp path
        import app.db as db_mod
        db_mod._db = None

        with TestClient(app) as c:
            yield c


@pytest.fixture
def token(client):
    """Login and get a valid JWT token."""
    resp = client.post("/auth/login", json={"username": "dev", "password": "dev1234"})
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.fixture
def headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuth:
    def test_login_success(self, client):
        resp = client.post("/auth/login", json={"username": "dev", "password": "dev1234"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["username"] == "dev"
        assert data["expires_in"] > 0

    def test_login_wrong_password(self, client):
        resp = client.post("/auth/login", json={"username": "dev", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "xxx"})
        assert resp.status_code == 401


class TestSignal:
    def test_signal_no_auth_401(self, client):
        resp = client.get("/signal/current")
        assert resp.status_code == 401

    def test_signal_with_auth(self, client, headers, mock_collectors):
        with patch("app.routes._signal_cache", {"result": None, "timestamp": 0.0}):
            resp = client.get("/signal/current", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "signal" in data
        assert data["signal"] in ("GREEN", "YELLOW", "RED")
        assert "score" in data


class TestBriefing:
    def test_briefing_latest_with_auth(self, client, headers, mock_collectors):
        with patch("app.briefing.generator._save_briefing"):
            resp = client.get("/briefing/latest", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "signal" in data
        assert "commentary" in data

    def test_briefing_history(self, client, headers):
        resp = client.get("/briefing/history?days=7", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestData:
    def test_macro_with_auth(self, client, headers, mock_collectors):
        resp = client.get("/data/macro", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data

    def test_macro_no_auth_401(self, client):
        resp = client.get("/data/macro")
        assert resp.status_code == 401
