"""Portfolio management API endpoints."""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException

from app.database import repositories as repo
from app.models.schemas import (
    PortfolioBulkCreate,
    PortfolioPositionCreate,
    PortfolioQuickAdd,
)

logger = logging.getLogger("vibe.routers.portfolio")

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# ── Seed data: pre-defined portfolio holdings ──
# Users can edit this list and call POST /portfolio/seed to register all at once.
PORTFOLIO_SEED: list[dict] = [
    # 예시: {"symbol": "005930", "market": "KR", "position_size": 5000000, "entry_price": 56000, "entry_date": "2025-12-01", "sector": "Semiconductor"},
    # {"symbol": "000660", "market": "KR", "position_size": 3000000, "entry_price": 200000, "entry_date": "2025-11-15", "sector": "Semiconductor"},
]


@router.get("")
async def get_portfolio(market: str | None = None):
    """Get current portfolio positions."""
    positions = await repo.get_portfolio_state(
        market=market.upper() if market else None,
    )
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


@router.post("/quick")
async def quick_add(items: list[PortfolioQuickAdd]):
    """Quickly register positions with minimal info.

    Only symbol, market, position_size required.
    entry_price is auto-filled from the latest price in DB.
    entry_date defaults to today.

    Example request body:
    [
        {"symbol": "005930", "market": "KR", "position_size": 5000000},
        {"symbol": "000660", "market": "KR", "position_size": 3000000}
    ]
    """
    results = []
    today = date.today().strftime("%Y-%m-%d")

    for item in items:
        # Auto-fill entry_price from latest price data
        entry_price = None
        price_row = await repo.get_price_at_date(
            item.symbol, item.market, today,
        )
        if price_row:
            entry_price = price_row.get("close")

        if entry_price is None:
            logger.warning(
                "No price data for %s/%s — entry_price will be null",
                item.market, item.symbol,
            )

        # Look up name from watchlist for logging
        watchlist = await repo.get_watchlist_item(item.symbol, item.market)
        name = watchlist.get("name", item.symbol) if watchlist else item.symbol

        await repo.upsert_portfolio_position(
            symbol=item.symbol,
            market=item.market,
            data={
                "position_size": item.position_size,
                "entry_date": today,
                "entry_price": entry_price,
                "sector": None,
            },
        )
        results.append({
            "symbol": item.symbol,
            "name": name,
            "market": item.market,
            "position_size": item.position_size,
            "entry_price": entry_price,
            "entry_date": today,
        })
        logger.info(
            "Quick add: %s (%s) size=%.0f price=%s",
            name, item.symbol, item.position_size,
            f"{entry_price:,.0f}" if entry_price else "N/A",
        )

    return {
        "status": "ok",
        "registered": len(results),
        "positions": results,
    }


@router.post("/bulk")
async def bulk_add(payload: PortfolioBulkCreate):
    """Register multiple portfolio positions at once.

    Example request body:
    {
        "items": [
            {"symbol": "005930", "market": "KR", "position_size": 5000000, "entry_price": 56000, "entry_date": "2025-12-01"},
            {"symbol": "000660", "market": "KR", "position_size": 3000000, "entry_price": 200000, "entry_date": "2025-11-15"}
        ]
    }
    """
    results = []
    for item in payload.items:
        await repo.upsert_portfolio_position(
            symbol=item.symbol,
            market=item.market,
            data={
                "position_size": item.position_size,
                "entry_date": item.entry_date,
                "entry_price": item.entry_price,
                "sector": item.sector,
            },
        )
        results.append({"symbol": item.symbol, "market": str(item.market)})
        logger.info(
            "Bulk add: %s/%s size=%.0f",
            item.market, item.symbol, item.position_size,
        )

    return {
        "status": "ok",
        "registered": len(results),
        "positions": results,
    }


@router.post("/seed")
async def seed_portfolio():
    """Register all positions from the PORTFOLIO_SEED list.

    Edit PORTFOLIO_SEED in app/routers/portfolio.py to define your holdings,
    then call this endpoint to register them all.
    """
    if not PORTFOLIO_SEED:
        return {
            "status": "empty",
            "message": "PORTFOLIO_SEED is empty. Edit app/routers/portfolio.py to add holdings.",
            "example": {
                "symbol": "005930",
                "market": "KR",
                "position_size": 5000000,
                "entry_price": 56000,
                "entry_date": "2025-12-01",
                "sector": "Semiconductor",
            },
        }

    count = 0
    for item in PORTFOLIO_SEED:
        await repo.upsert_portfolio_position(
            symbol=item["symbol"],
            market=item["market"],
            data={
                "position_size": item.get("position_size", 0),
                "entry_date": item.get("entry_date"),
                "entry_price": item.get("entry_price"),
                "sector": item.get("sector"),
            },
        )
        count += 1
        logger.info("Seed portfolio: %s/%s", item["market"], item["symbol"])

    return {"status": "ok", "seeded": count}


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


@router.delete("/all")
async def clear_all_positions(market: str | None = None):
    """Remove all positions (optionally filtered by market)."""
    market_upper = market.upper() if market else None
    count = await repo.clear_portfolio_positions(market=market_upper)
    return {"status": "cleared", "removed": count}


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
