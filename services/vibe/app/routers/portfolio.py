"""Portfolio management API endpoints."""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.database import repositories as repo
from app.models.schemas import (
    PortfolioBulkCreate,
    PortfolioGroupCreate,
    PortfolioGroupUpdate,
    PortfolioPositionCreate,
    PortfolioQuickAdd,
)

logger = logging.getLogger("vibe.routers.portfolio")

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# ── Seed data: pre-defined portfolio holdings ──
# Users can edit this list and call POST /portfolio/seed to register all at once.
PORTFOLIO_SEED: list[dict] = [
    # 예시: {"symbol": "005930", "market": "KR", "position_size": 5000000, "entry_price": 56000, "entry_date": "2025-12-01", "sector": "Semiconductor"},
]


# ── Portfolio Groups ──


@router.get("/groups")
async def get_groups():
    """Get all portfolio groups."""
    groups = await repo.get_portfolio_groups()
    return {"groups": groups, "count": len(groups)}


@router.post("/groups")
async def create_group(payload: PortfolioGroupCreate):
    """Create a new portfolio group."""
    group_id = await repo.create_portfolio_group(payload.name, payload.description)
    return {"status": "ok", "id": group_id, "name": payload.name}


@router.put("/groups/{group_id}")
async def update_group(group_id: int, payload: PortfolioGroupUpdate):
    """Update a portfolio group."""
    ok = await repo.update_portfolio_group(group_id, payload.name, payload.description)
    if not ok:
        raise HTTPException(404, "Portfolio group not found")
    return {"status": "ok", "id": group_id}


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int):
    """Delete a portfolio group (cannot delete default)."""
    ok = await repo.delete_portfolio_group(group_id)
    if not ok:
        raise HTTPException(400, "Cannot delete default group or group not found")
    return {"status": "deleted", "id": group_id}


# ── Portfolio Positions ──


@router.get("")
async def get_portfolio(
    market: str | None = None,
    portfolio_id: int = Query(1, alias="portfolio_id"),
    include_hidden: bool = Query(False),
):
    """Get current portfolio positions."""
    positions = await repo.get_portfolio_state(
        portfolio_id=portfolio_id,
        market=market.upper() if market else None,
        include_hidden=include_hidden,
    )
    return {
        "portfolio_id": portfolio_id,
        "positions": positions,
        "count": len(positions),
    }


@router.patch("/position/{market}/{symbol}/hide")
async def toggle_hide_position(
    market: str, symbol: str,
    portfolio_id: int = Query(1),
):
    """Toggle hidden state for a portfolio position."""
    result = await repo.toggle_position_hidden(
        symbol=symbol, market=market.upper(), portfolio_id=portfolio_id,
    )
    if not result.get("found"):
        raise HTTPException(404, "Position not found")
    logger.info(
        "Position hidden toggled: group=%d %s/%s -> hidden=%s",
        portfolio_id, market.upper(), symbol, result["is_hidden"],
    )
    return {
        "status": "ok",
        "symbol": symbol,
        "market": market.upper(),
        "is_hidden": result["is_hidden"],
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
        portfolio_id=position.portfolio_id,
    )
    logger.info(
        "Portfolio position updated: group=%d %s/%s size=%.0f",
        position.portfolio_id, position.market, position.symbol, position.position_size,
    )
    return {"status": "ok", "symbol": position.symbol, "market": position.market,
            "portfolio_id": position.portfolio_id}


@router.post("/quick")
async def quick_add(
    items: list[PortfolioQuickAdd],
    portfolio_id: int = Query(1, alias="portfolio_id"),
):
    """Quickly register positions with minimal info.

    Only symbol, market, position_size required.
    entry_price is auto-filled from the latest price in DB.
    entry_date defaults to today.
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
            portfolio_id=portfolio_id,
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
            "Quick add: %s (%s) group=%d size=%.0f price=%s",
            name, item.symbol, portfolio_id, item.position_size,
            f"{entry_price:,.0f}" if entry_price else "N/A",
        )

    return {
        "status": "ok",
        "portfolio_id": portfolio_id,
        "registered": len(results),
        "positions": results,
    }


@router.post("/bulk")
async def bulk_add(payload: PortfolioBulkCreate):
    """Register multiple portfolio positions at once."""
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
            portfolio_id=payload.portfolio_id,
        )
        results.append({"symbol": item.symbol, "market": str(item.market)})
        logger.info(
            "Bulk add: group=%d %s/%s size=%.0f",
            payload.portfolio_id, item.market, item.symbol, item.position_size,
        )

    return {
        "status": "ok",
        "portfolio_id": payload.portfolio_id,
        "registered": len(results),
        "positions": results,
    }


@router.post("/seed")
async def seed_portfolio(portfolio_id: int = Query(1)):
    """Register all positions from the PORTFOLIO_SEED list."""
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
            portfolio_id=portfolio_id,
        )
        count += 1
        logger.info("Seed portfolio: group=%d %s/%s", portfolio_id, item["market"], item["symbol"])

    return {"status": "ok", "portfolio_id": portfolio_id, "seeded": count}


@router.delete("/position/{market}/{symbol}")
async def remove_position(
    market: str, symbol: str,
    portfolio_id: int = Query(1),
):
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
        portfolio_id=portfolio_id,
    )
    logger.info("Portfolio position removed: group=%d %s/%s", portfolio_id, market.upper(), symbol)
    return {"status": "removed", "symbol": symbol, "market": market.upper(),
            "portfolio_id": portfolio_id}


@router.delete("/all")
async def clear_all_positions(
    market: str | None = None,
    portfolio_id: int = Query(1),
):
    """Remove all positions in a group (optionally filtered by market)."""
    market_upper = market.upper() if market else None
    count = await repo.clear_portfolio_positions(
        portfolio_id=portfolio_id, market=market_upper,
    )
    return {"status": "cleared", "portfolio_id": portfolio_id, "removed": count}


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


# ── Position Exits ──


@router.post("/position/{market}/{symbol}/exit")
async def exit_position_endpoint(
    market: str, symbol: str,
    exit_reason: str = Query("manual"),
    portfolio_id: int = Query(1),
):
    """Exit a position and record exit history."""
    result = await repo.exit_position(
        symbol=symbol, market=market.upper(),
        exit_reason=exit_reason, portfolio_id=portfolio_id,
    )
    if result.get("status") == "not_found":
        raise HTTPException(404, f"Position {symbol}/{market} not found")
    return result


@router.post("/batch-exit")
async def batch_exit(portfolio_id: int = Query(1)):
    """Exit all positions that have breached stop-loss."""
    from app.config import settings
    count = await repo.batch_exit_stop_loss(
        portfolio_id=portfolio_id,
        stop_pct=settings.BACKTEST_STOP_LOSS_PCT,
    )
    return {"status": "ok", "exited_count": count}


@router.get("/exits")
async def get_exits(
    portfolio_id: int = Query(1),
    limit: int = Query(50, ge=1, le=200),
):
    """Get position exit history."""
    exits = await repo.get_exit_history(portfolio_id, limit)
    return {"exits": exits, "count": len(exits)}
