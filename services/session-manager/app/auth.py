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
    APP_DIR.parent.parent,        # 01_UFS root (services/session-manager/../../)
    APP_DIR.parent.parent.parent, # D:\Claude (04_ImageGen 등 형제 프로젝트 포함)
    Path(APP_DIR.anchor),         # D:\ — 드라이브 루트 탐색 허용 (browse 네비게이션용)
)


def _is_browse_allowed(folder: Path) -> bool:
    """Verify resolved path is under an allowed root (prevents symlink traversal)."""
    try:
        resolved = folder.resolve()
    except Exception:
        return False
    return any(resolved.is_relative_to(root.resolve()) for root in _ALLOWED_BROWSE_ROOTS)


def validate_work_dir(work_dir: str) -> Path:
    """work_dir 문자열 검증: 존재하는 디렉토리이고 허용 루트 내에 있는지 확인.

    Returns:
        Resolved Path if valid.
    Raises:
        ValueError: path traversal 의심 또는 디렉토리 미존재.
    """
    try:
        resolved = Path(work_dir).resolve()
    except Exception as exc:
        raise ValueError(f"work_dir 경로 파싱 실패: {exc}") from exc

    if not resolved.exists():
        raise ValueError(f"work_dir 경로가 존재하지 않습니다: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"work_dir이 디렉토리가 아닙니다: {resolved}")
    if not _is_browse_allowed(resolved):
        raise ValueError(f"work_dir 접근 불가 (허용 범위 외): {resolved}")
    return resolved
