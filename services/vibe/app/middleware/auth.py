"""Authentication middleware — supports JWT Bearer tokens + API Key.

When API_AUTH_ENABLED=True, all endpoints (except public paths)
require either a valid JWT Bearer token OR X-API-Key header.
"""

import hmac
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("vibe.auth")

# Paths that never require authentication
PUBLIC_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}

# Path prefixes that never require authentication
PUBLIC_PREFIXES = (
    "/ui/", "/static/", "/ui",
    "/auth/status", "/auth/login", "/auth/register",
    "/soxl/live/stream",  # SSE — EventSource can't send auth headers
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for public prefixes
        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        # 1) Check Bearer JWT token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from app.routers.auth import decode_token
                payload = decode_token(token)
                if payload and payload.get("sub"):
                    # Valid JWT — allow request
                    return await call_next(request)
            except Exception:
                pass  # Fall through to API key check

        # 2) Check X-API-Key header
        provided_key = request.headers.get("X-API-Key", "")
        if provided_key and hmac.compare_digest(provided_key, self.api_key):
            return await call_next(request)

        # 3) Both failed
        logger.warning(
            "Auth failed: %s %s from %s",
            request.method, request.url.path, request.client.host if request.client else "unknown",
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing authentication"},
        )
