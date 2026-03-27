"""JWT authentication — login, token creation, dependency."""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt

from app.config import settings
from app.db import get_db

logger = logging.getLogger("vibe2.auth")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(username: str) -> tuple[str, int]:
    """Create a JWT token. Returns (token_string, expires_in_seconds)."""
    expires_in = settings.JWT_EXPIRE_MINUTES * 60
    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns payload dict or None."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.debug("JWT decode failed: %s", e)
        return None


async def get_current_user(request: Request) -> str:
    """FastAPI dependency — extract and validate Bearer token.

    Returns the username from the token payload.
    Raises 401 if token is missing, invalid, or user not found.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = auth_header[7:]
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    username = payload["sub"]

    # Verify user still exists in DB
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    )
    user = await cursor.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return username
