import logging
import re

from fastapi import APIRouter, HTTPException

from app.database import repositories as repo
from app.models.schemas import (
    WatchlistBulkCreate,
    WatchlistItemCreate,
    WatchlistItemResponse,
)

logger = logging.getLogger("vibe.routers.watchlist")

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

_SYMBOL_RE = re.compile(r'^[A-Z0-9.\-]{1,10}$', re.IGNORECASE)


@router.get("", response_model=list[WatchlistItemResponse])
async def get_watchlist(market: str | None = None, active_only: bool = True):
    """Get tracked symbols, optionally filtered by market."""
    items = await repo.get_watchlist(
        market=market.upper() if market else None, active_only=active_only,
    )
    return items


@router.post("", response_model=WatchlistItemResponse)
async def add_symbol(item: WatchlistItemCreate):
    """Add a single symbol to the watchlist."""
    if not _SYMBOL_RE.match(item.symbol):
        raise HTTPException(status_code=400, detail="Invalid symbol format (1-10 alphanumeric chars)")
    result = await repo.add_watchlist_item(
        symbol=item.symbol,
        name=item.name,
        market=item.market,
        asset_type=item.asset_type,
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to add symbol")
    logger.info("Watchlist symbol added: %s (%s)", item.symbol, item.market)
    return result


@router.post("/bulk", response_model=dict)
async def add_symbols_bulk(data: WatchlistBulkCreate):
    """Add multiple symbols to the watchlist at once."""
    items = [
        {
            "symbol": i.symbol,
            "name": i.name,
            "market": i.market,
            "asset_type": i.asset_type,
        }
        for i in data.items
    ]
    count = await repo.add_watchlist_bulk(items)
    return {"added": count, "total_submitted": len(items)}


@router.delete("/{symbol}")
async def remove_symbol(symbol: str, market: str = "KR"):
    """Deactivate a symbol from the watchlist (soft delete)."""
    removed = await repo.remove_watchlist_item(symbol=symbol, market=market)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in {market} watchlist")
    logger.info("Watchlist symbol removed: %s (%s)", symbol, market)
    return {"removed": symbol, "market": market}
