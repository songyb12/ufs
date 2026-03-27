"""
app/auth.py — Authentication dependencies and access-control helpers.

Contains:
- verify_admin_key: FastAPI Depends() for /admin/* endpoints
- _ALLOWED_BROWSE_ROOTS / _is_browse_allowed: path-traversal guard for /api/browse
"""

import os
from pathlib import Path

from fastapi import Header, HTTPException

from app.models import APP_DIR

# ─── Admin API auth ───────────────────────────────────────────────────────────

_ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "")


async def verify_admin_key(x_admin_key: str = Header(default="")) -> None:
    """Admin endpoint authentication dependency.

    Checks X-Admin-Key header against ADMIN_API_KEY env var.
    Returns 403 if env var is not set (admin API disabled) or key mismatch.
    """
    key = os.environ.get("ADMIN_API_KEY", _ADMIN_API_KEY)
    if not key:
        raise HTTPException(
            status_code=403,
            detail="Admin API disabled — set the ADMIN_API_KEY environment variable",
        )
    if x_admin_key != key:
        raise HTTPException(status_code=403, detail="Admin authentication failed")


# ─── Browse path security ─────────────────────────────────────────────────────

# Only allow browsing within home directory or project root
_ALLOWED_BROWSE_ROOTS: tuple[Path, ...] = (
    Path.home(),
    APP_DIR.parent.parent,  # project root (services/session-manager/../../)
)


def _is_browse_allowed(folder: Path) -> bool:
    """Verify resolved path is under an allowed root (prevents symlink traversal)."""
    try:
        resolved = folder.resolve()
    except Exception:
        return False
    return any(resolved.is_relative_to(root.resolve()) for root in _ALLOWED_BROWSE_ROOTS)
