"""Screening API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.database import repositories as repo
from app.screening.scanner import DynamicScreener

logger = logging.getLogger("vibe.routers.screening")
router = APIRouter(prefix="/screening", tags=["screening"])


class StatusUpdate(BaseModel):
    status: str  # "approved" | "rejected" | "new"


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
    market = market.upper()
    if market not in ("KR", "US"):
        raise HTTPException(status_code=400, detail="market must be 'KR' or 'US'")
    if status is not None and status not in ("new", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'new', 'approved', or 'rejected'")
    candidates = await repo.get_screening_candidates(market, status=status)
    return {"candidates": candidates, "count": len(candidates)}


@router.patch("/candidates/{candidate_id}/status")
async def update_candidate_status(candidate_id: int, body: StatusUpdate):
    """Update screening candidate status (approved/rejected/new)."""
    if body.status not in ("approved", "rejected", "new"):
        raise HTTPException(status_code=400, detail="Invalid status")
    updated = await repo.update_screening_status(candidate_id, body.status)
    if updated == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"ok": True, "id": candidate_id, "status": body.status}
