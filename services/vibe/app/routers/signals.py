import logging

from fastapi import APIRouter, Query

from app.backtesting.tracker import SignalPerformanceTracker
from app.database import repositories as repo
from app.models.schemas import SignalPerformanceResponse, SignalResponse

logger = logging.getLogger("vibe.routers.signals")

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalResponse])
async def get_signals(market: str | None = None):
    """Get the latest signals, optionally filtered by market."""
    return await repo.get_latest_signals(market=market.upper() if market else None)


@router.get("/performance", response_model=SignalPerformanceResponse)
async def get_performance(market: str | None = None, lookback_days: int = Query(90, ge=1, le=730)):
    """Get signal performance summary (hit rate, avg returns)."""
    tracker = SignalPerformanceTracker()
    summary = await tracker.get_hit_rate_summary(
        market=market.upper() if market else None, lookback_days=lookback_days,
    )
    return summary


@router.get("/{market}", response_model=list[SignalResponse])
async def get_signals_by_market(market: str):
    """Get the latest signals for a specific market (KR or US)."""
    return await repo.get_latest_signals(market=market.upper())
