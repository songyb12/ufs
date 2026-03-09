"""Sentiment API endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from app.database import repositories as repo

logger = logging.getLogger("vibe.routers.sentiment")

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("")
async def get_sentiment(days: int = 7):
    """Get recent sentiment data."""
    days = min(max(days, 1), 365)
    data = await repo.get_sentiment_history(days)
    return {"sentiment": data, "count": len(data)}


@router.get("/latest")
async def get_latest_sentiment():
    """Get the most recent sentiment reading."""
    data = await repo.get_latest_sentiment()
    if not data:
        raise HTTPException(status_code=404, detail="No sentiment data available")
    return data
