"""Authentication API — user registration, login, token management."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.database import repositories as repo

logger = logging.getLogger("vibe.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# ── JWT Secret Management ──

_jwt_secret: str = ""


def _get_jwt_secret() -> str:
    """Get JWT secret, auto-generating if not configured."""
    global _jwt_secret
    if _jwt_secret:
        return _jwt_secret
    if settings.JWT_SECRET:
        _jwt_secret = settings.JWT_SECRET
    else:
        _jwt_secret = uuid.uuid4().hex
        logger.info("JWT secret auto-generated (will change on restart)")
    return _jwt_secret


def _create_token(username: str) -> tuple[str, int]:
    """Create JWT token. Returns (token, expires_in_seconds)."""
    secret = _get_jwt_secret()
    expires_in = settings.JWT_EXPIRE_HOURS * 3600
    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, expires_in


def decode_token(token: str) -> dict | None:
    """Decode and validate JWT token. Returns payload or None."""
    try:
        secret = _get_jwt_secret()
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("JWT invalid: %s", e)
        return None


# ── Password Hashing ──


def _hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ── Request Models ──


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=4, max_length=128)


# ── Endpoints ──


@router.get("/status")
async def auth_status(request: Request):
    """Check authentication status.

    Returns whether setup is needed and if current token is valid.
    """
    user_count = await repo.count_users()
    needs_setup = user_count == 0

    # Check Bearer token if present
    authenticated = False
    username = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload and payload.get("sub"):
            user = await repo.get_user_by_username(payload["sub"])
            if user:
                authenticated = True
                username = user["username"]

    return {
        "needs_setup": needs_setup,
        "authenticated": authenticated,
        "username": username,
    }


@router.post("/register")
async def register(body: RegisterRequest):
    """Register the first user account.

    Only allowed when no users exist (initial setup).
    """
    user_count = await repo.count_users()
    if user_count > 0:
        raise HTTPException(
            status_code=403,
            detail="Registration disabled. Account already exists.",
        )

    password_hash = _hash_password(body.password)
    user_id = await repo.create_user(body.username, password_hash)
    logger.info("User registered: %s (id=%d)", body.username, user_id)

    # Auto-login after registration
    token, expires_in = _create_token(body.username)
    await repo.update_last_login(body.username)

    return {
        "status": "ok",
        "token": token,
        "username": body.username,
        "expires_in": expires_in,
    }


@router.post("/login")
async def login(body: LoginRequest):
    """Authenticate with username and password. Returns JWT token."""
    user = await repo.get_user_by_username(body.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_password(body.password, user["password_hash"]):
        logger.warning("Login failed for user: %s", body.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, expires_in = _create_token(body.username)
    await repo.update_last_login(body.username)
    logger.info("User logged in: %s", body.username)

    return {
        "token": token,
        "username": body.username,
        "expires_in": expires_in,
    }


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, request: Request):
    """Change password. Requires valid Bearer token."""
    # Verify current authentication
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = auth_header[7:]
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    username = payload["sub"]
    user = await repo.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Verify current password
    if not _verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # Update password
    new_hash = _hash_password(body.new_password)
    await repo.update_user_password(username, new_hash)
    logger.info("Password changed for user: %s", username)

    # Issue new token
    new_token, expires_in = _create_token(username)

    return {
        "status": "ok",
        "token": new_token,
        "expires_in": expires_in,
    }
