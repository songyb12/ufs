from fastapi import APIRouter

from app.database import repositories as repo
from app.models.schemas import SignalResponse

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalResponse])
async def get_signals(market: str | None = None):
    """Get the latest signals, optionally filtered by market."""
    return await repo.get_latest_signals(market=market)


@router.get("/{market}", response_model=list[SignalResponse])
async def get_signals_by_market(market: str):
    """Get the latest signals for a specific market (KR or US)."""
    return await repo.get_latest_signals(market=market.upper())
