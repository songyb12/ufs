"""Risk management API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.database import repositories as repo
from app.risk.events import EventCalendar
from app.risk.sector import SECTOR_MAP, compute_sector_exposure

logger = logging.getLogger("vibe.routers.risk")

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/portfolio")
async def get_portfolio(market: str | None = None):
    """Get current portfolio state and sector exposure across ALL groups."""
    try:
        # Aggregate across all portfolio groups
        groups = await repo.get_portfolio_groups()
        all_positions = []
        for g in groups:
            positions = await repo.get_portfolio_state(
                portfolio_id=g["id"],
                market=market.upper() if market else None,
            )
            all_positions.extend(positions)

        # Fallback: if no groups, try default
        if not groups:
            all_positions = await repo.get_portfolio_state(
                market=market.upper() if market else None,
            )

        # Normalize position_size to percentage for sector exposure
        total_invested = sum(p.get("position_size", 0) for p in all_positions)
        if total_invested > 0:
            position_map = {p["symbol"]: round(p.get("position_size", 0) / total_invested * 100, 2)
                            for p in all_positions if p.get("symbol")}
        else:
            position_map = {p["symbol"]: 0 for p in all_positions if p.get("symbol")}
        sector_exp = compute_sector_exposure(position_map)
        return {
            "positions": all_positions,
            "sector_exposure": sector_exp,
            "total_positions": len(all_positions),
        }
    except Exception as e:
        logger.error("Failed to get portfolio: market=%s, error=%s", market, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Portfolio retrieval failed. Check server logs for details.")


@router.get("/events")
async def get_events(market: str = Query("KR", pattern="^(KR|US|ALL)$"), days_ahead: int = Query(7, ge=1, le=365)):
    """Get upcoming events within N days."""
    events = await repo.get_upcoming_events(market.upper(), days_ahead=days_ahead)
    return {"events": events, "count": len(events)}


@router.post("/events/seed")
async def seed_events():
    """Seed static events (FOMC, holidays, options expiry) into DB."""
    logger.info("Event seeding requested")
    calendar = EventCalendar()
    count = await calendar.seed_static_events()
    logger.info("Event seeding completed: %d events seeded", count)
    return {"seeded": count}


@router.get("/sectors")
async def get_sectors():
    """Get all sector mappings."""
    return {"sectors": SECTOR_MAP}
