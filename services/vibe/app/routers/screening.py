"""Screening API endpoints."""

import logging

from fastapi import APIRouter, Query

from app.database import repositories as repo
from app.screening.scanner import DynamicScreener

logger = logging.getLogger("vibe.routers.screening")
router = APIRouter(prefix="/screening", tags=["screening"])


@router.post("/scan")
async def run_scan(
    market: str = Query("KR", pattern="^(KR|US)$"),
    days_back: int = Query(5, ge=1, le=90),
):
    """Run dynamic screening scan."""
    screener = DynamicScreener()
    candidates = await screener.scan(market, days_back=days_back)

    # Store candidates
    count = 0
    for c in candidates:
        try:
            await repo.insert_screening_candidate(c)
            count += 1
        except Exception as e:
            logger.warning("Failed to store screening candidate %s: %s", c.get("symbol"), e)

    return {
        "market": market,
        "candidates_found": len(candidates),
        "stored": count,
        "candidates": candidates,
    }


@router.get("/candidates")
async def get_candidates(market: str = "KR", status: str | None = None):
    """Get screening candidates."""
    candidates = await repo.get_screening_candidates(market, status=status)
    return {"candidates": candidates, "count": len(candidates)}
