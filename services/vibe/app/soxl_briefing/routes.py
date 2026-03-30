"""SOXL Briefing API Router.

Endpoints:
  GET /soxl-briefing/generate  — Generate a fresh daily briefing (slow, calls LLM)
  GET /soxl-briefing/latest    — Return the most recent cached briefing
  GET /soxl-briefing/history   — Return recent briefing history
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.soxl_briefing.generator import generate_soxl_briefing
from app.soxl_briefing.store import get_briefing_history, get_latest_briefing

router = APIRouter(prefix="/soxl-briefing", tags=["soxl-briefing"])
logger = logging.getLogger("vibe.soxl_briefing.routes")


@router.get("/generate")
async def generate_briefing():
    """Generate today's SOXL daily briefing via LLM and persist it.

    This endpoint is slow (~10-30 s) because it calls the Anthropic API.
    """
    result = await generate_soxl_briefing()
    return {
        "date": result["metadata"].get("generated_at", "")[:10],
        "briefing": result["briefing_text"],
        "metadata": result["metadata"],
    }


@router.get("/latest")
async def latest_briefing():
    """Return the most recently cached briefing (no LLM call)."""
    row = await get_latest_briefing()
    if not row:
        raise HTTPException(404, detail="아직 생성된 브리핑이 없습니다.")
    return row


@router.get("/history")
async def briefing_history(limit: int = Query(30, ge=1, le=100)):
    """Return the *limit* most recent briefings (newest first)."""
    rows = await get_briefing_history(limit=limit)
    return {"count": len(rows), "briefings": rows}
