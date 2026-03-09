"""
Authentication API tests — register, login, token validation, password change.

Covers:
- POST /auth/register (first-time setup)
- POST /auth/login (ID/PW login)
- GET /auth/status (token validation)
- POST /auth/change-password
"""

import pytest
import pytest_asyncio

from app.database.connection import get_db


@pytest_asyncio.fixture(autouse=True)
async def _clean_users():
    """Clean users table before and after each test."""
    db = await get_db()
    await db.execute("DELETE FROM users")
    await db.commit()
    yield
    await db.execute("DELETE FROM users")
    await db.commit()


# ── Registration ──


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_first_user(self, client):
        """POST /auth/register creates the first user and returns token."""
        resp = await client.post("/auth/register", json={
            "username": "admin",
            "password": "test1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["username"] == "admin"
        assert "token" in data
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_register_blocked_when_user_exists(self, client):
        """POST /auth/register returns 403 when a user already exists."""
        # Create first user
        resp1 = await client.post("/auth/register", json={
            "username": "admin",
            "password": "test1234",
        })
        assert resp1.status_code == 200

        # Try to register again
        resp2 = await client.post("/auth/register", json={
            "username": "hacker",
            "password": "hax0r",
        })
        assert resp2.status_code == 403

    @pytest.mark.asyncio
    async def test_register_validation_short_password(self, client):
        """POST /auth/register rejects short passwords."""
        resp = await client.post("/auth/register", json={
            "username": "admin",
            "password": "ab",
        })
        assert resp.status_code == 422  # Pydantic validation

    @pytest.mark.asyncio
    async def test_register_validation_short_username(self, client):
        """POST /auth/register rejects short usernames."""
        resp = await client.post("/auth/register", json={
            "username": "a",
            "password": "test1234",
        })
        assert resp.status_code == 422


# ── Login ──


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """POST /auth/login returns token for valid credentials."""
        # Register first
        await client.post("/auth/register", json={
            "username": "admin",
            "password": "mypassword",
        })

        # Login
        resp = await client.post("/auth/login", json={
            "username": "admin",
            "password": "mypassword",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["username"] == "admin"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """POST /auth/login returns 401 for wrong password."""
        await client.post("/auth/register", json={
            "username": "admin",
            "password": "correct",
        })

        resp = await client.post("/auth/login", json={
            "username": "admin",
            "password": "wrong",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """POST /auth/login returns 401 for unknown user."""
        resp = await client.post("/auth/login", json={
            "username": "ghost",
            "password": "test1234",
        })
        assert resp.status_code == 401


# ── Status ──


class TestAuthStatus:
    @pytest.mark.asyncio
    async def test_status_needs_setup_when_no_users(self, client):
        """GET /auth/status returns needs_setup=true when no users."""
        resp = await client.get("/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_setup"] is True
        assert data["authenticated"] is False

    @pytest.mark.asyncio
    async def test_status_authenticated_with_valid_token(self, client):
        """GET /auth/status returns authenticated=true with valid Bearer token."""
        # Register & get token
        reg = await client.post("/auth/register", json={
            "username": "admin",
            "password": "test1234",
        })
        token = reg.json()["token"]

        # Check status with token
        resp = await client.get("/auth/status", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["username"] == "admin"
        assert data["needs_setup"] is False

    @pytest.mark.asyncio
    async def test_status_not_authenticated_with_invalid_token(self, client):
        """GET /auth/status returns authenticated=false with invalid token."""
        resp = await client.get("/auth/status", headers={
            "Authorization": "Bearer invalidtoken",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is False

    @pytest.mark.asyncio
    async def test_status_not_setup_after_register(self, client):
        """GET /auth/status returns needs_setup=false after registration."""
        await client.post("/auth/register", json={
            "username": "admin",
            "password": "test1234",
        })

        resp = await client.get("/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_setup"] is False


# ── Change Password ──


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_change_password_success(self, client):
        """POST /auth/change-password updates password and returns new token."""
        reg = await client.post("/auth/register", json={
            "username": "admin",
            "password": "old_pass",
        })
        token = reg.json()["token"]

        resp = await client.post("/auth/change-password",
            json={"current_password": "old_pass", "new_password": "new_pass"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "token" in data

        # Login with new password
        login_resp = await client.post("/auth/login", json={
            "username": "admin",
            "password": "new_pass",
        })
        assert login_resp.status_code == 200

        # Old password should fail
        old_resp = await client.post("/auth/login", json={
            "username": "admin",
            "password": "old_pass",
        })
        assert old_resp.status_code == 401

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client):
        """POST /auth/change-password returns 401 for wrong current password."""
        reg = await client.post("/auth/register", json={
            "username": "admin",
            "password": "correct",
        })
        token = reg.json()["token"]

        resp = await client.post("/auth/change-password",
            json={"current_password": "wrong", "new_password": "newpass"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_change_password_requires_auth(self, client):
        """POST /auth/change-password returns 401 without token."""
        resp = await client.post("/auth/change-password",
            json={"current_password": "oldpass", "new_password": "newpass1234"},
        )
        assert resp.status_code == 401
