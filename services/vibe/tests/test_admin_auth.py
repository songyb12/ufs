"""
Admin endpoint authentication tests — require_auth defense-in-depth.

Covers:
- POST /admin/backup requires authentication (401 without credentials)
- POST /admin/retention requires authentication (401 without credentials)
- Valid JWT bypasses the auth guard (non-401 response)
"""

import pytest
import pytest_asyncio
import httpx
from fastapi import Depends, FastAPI

from app.middleware.auth import require_auth


# ── Build a minimal app with admin endpoints that use require_auth ──

def _build_admin_app() -> FastAPI:
    """Create a test app that mirrors main.py's admin endpoints."""
    admin_app = FastAPI()

    @admin_app.post("/admin/backup")
    async def trigger_backup(_user: str = Depends(require_auth)):
        return {"status": "ok", "user": _user}

    @admin_app.post("/admin/retention")
    async def trigger_retention(_user: str = Depends(require_auth)):
        return {"status": "ok", "user": _user}

    return admin_app


@pytest_asyncio.fixture(scope="module")
async def admin_client():
    """HTTP client for the admin-only test app."""
    app = _build_admin_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _make_jwt(username: str = "testuser") -> str:
    """Create a valid JWT token for testing."""
    from app.routers.auth import _create_token
    token, _ = _create_token(username)
    return token


# ── Tests ──


class TestAdminBackupAuth:
    @pytest.mark.asyncio
    async def test_backup_no_auth_returns_401(self, admin_client):
        """POST /admin/backup without credentials → 401."""
        resp = await admin_client.post("/admin/backup")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_backup_invalid_token_returns_401(self, admin_client):
        """POST /admin/backup with garbage Bearer token → 401."""
        resp = await admin_client.post(
            "/admin/backup",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_backup_valid_jwt_passes_auth(self, admin_client):
        """POST /admin/backup with valid JWT → 200 (auth passes)."""
        token = _make_jwt("admin")
        resp = await admin_client.post(
            "/admin/backup",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] == "admin"

    @pytest.mark.asyncio
    async def test_backup_valid_api_key_passes_auth(self, admin_client):
        """POST /admin/backup with valid X-API-Key → 200."""
        from app.config import settings
        if not settings.API_KEY:
            pytest.skip("API_KEY not configured")
        resp = await admin_client.post(
            "/admin/backup",
            headers={"X-API-Key": settings.API_KEY},
        )
        assert resp.status_code == 200


class TestAdminRetentionAuth:
    @pytest.mark.asyncio
    async def test_retention_no_auth_returns_401(self, admin_client):
        """POST /admin/retention without credentials → 401."""
        resp = await admin_client.post("/admin/retention")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_retention_valid_jwt_passes_auth(self, admin_client):
        """POST /admin/retention with valid JWT → 200."""
        token = _make_jwt("admin")
        resp = await admin_client.post(
            "/admin/retention",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] == "admin"
