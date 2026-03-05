"""API Key authentication middleware.

When API_AUTH_ENABLED=True, all endpoints (except /health and /)
require X-API-Key header matching the configured API_KEY.
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
PUBLIC_PREFIXES = ("/ui/", "/static/", "/ui")


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for dashboard static assets
        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        # Check X-API-Key header
        provided_key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(provided_key, self.api_key):
            logger.warning(
                "Auth failed: %s %s from %s",
                request.method, request.url.path, request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
