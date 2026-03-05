"""Risk management API endpoints."""

from fastapi import APIRouter

from app.database import repositories as repo
from app.risk.events import EventCalendar
from app.risk.sector import SECTOR_MAP, compute_sector_exposure

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/portfolio")
async def get_portfolio(market: str | None = None):
    """Get current portfolio state and sector exposure."""
    positions = await repo.get_portfolio_state(
        market=market.upper() if market else None,
    )
    position_map = {p["symbol"]: p.get("position_size", 0) for p in positions}
    sector_exp = compute_sector_exposure(position_map)
    return {
        "positions": positions,
        "sector_exposure": sector_exp,
        "total_positions": len(positions),
    }


@router.get("/events")
async def get_events(market: str = "KR", days_ahead: int = 7):
    """Get upcoming events within N days."""
    events = await repo.get_upcoming_events(market.upper(), days_ahead=days_ahead)
    return {"events": events, "count": len(events)}


@router.post("/events/seed")
async def seed_events():
    """Seed static events (FOMC, holidays, options expiry) into DB."""
    calendar = EventCalendar()
    count = await calendar.seed_static_events()
    return {"seeded": count}


@router.get("/sectors")
async def get_sectors():
    """Get all sector mappings."""
    return {"sectors": SECTOR_MAP}
