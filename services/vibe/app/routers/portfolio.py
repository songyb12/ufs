"""Portfolio management API endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from app.database import repositories as repo
from app.models.schemas import PortfolioPositionCreate

logger = logging.getLogger("vibe.routers.portfolio")

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
async def get_portfolio(market: str | None = None):
    """Get current portfolio positions."""
    positions = await repo.get_portfolio_state(market=market.upper() if market else None)
    return {
        "positions": positions,
        "count": len(positions),
    }


@router.post("/position")
async def add_position(position: PortfolioPositionCreate):
    """Add or update a portfolio position."""
    await repo.upsert_portfolio_position(
        symbol=position.symbol,
        market=position.market,
        data={
            "position_size": position.position_size,
            "entry_date": position.entry_date,
            "entry_price": position.entry_price,
            "sector": position.sector,
        },
    )
    logger.info(
        "Portfolio position updated: %s/%s size=%.0f",
        position.market, position.symbol, position.position_size,
    )
    return {"status": "ok", "symbol": position.symbol, "market": position.market}


@router.delete("/position/{market}/{symbol}")
async def remove_position(market: str, symbol: str):
    """Remove a position (set size to 0)."""
    await repo.upsert_portfolio_position(
        symbol=symbol,
        market=market.upper(),
        data={
            "position_size": 0,
            "entry_date": None,
            "entry_price": None,
            "sector": None,
        },
    )
    logger.info("Portfolio position removed: %s/%s", market.upper(), symbol)
    return {"status": "removed", "symbol": symbol, "market": market.upper()}


@router.get("/scenarios")
async def get_latest_scenarios(market: str | None = None):
    """Get latest portfolio scenarios from the last pipeline run."""
    scenarios = await repo.get_latest_portfolio_scenarios(
        market=market.upper() if market else None,
    )
    held = [s for s in scenarios if s.get("scenario_type") == "held"]
    entry = [s for s in scenarios if s.get("scenario_type") == "entry"]
    return {
        "held_scenarios": held,
        "entry_scenarios": entry,
        "total": len(scenarios),
    }
