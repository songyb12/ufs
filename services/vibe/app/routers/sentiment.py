"""Sentiment API endpoints."""

from fastapi import APIRouter

from app.database import repositories as repo

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.get("")
async def get_sentiment(days: int = 7):
    """Get recent sentiment data."""
    data = await repo.get_sentiment_history(days)
    return {"sentiment": data, "count": len(data)}


@router.get("/latest")
async def get_latest_sentiment():
    """Get the most recent sentiment reading."""
    data = await repo.get_latest_sentiment()
    return data or {"message": "No sentiment data available"}
