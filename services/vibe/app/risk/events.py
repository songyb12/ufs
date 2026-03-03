"""Event Calendar - FOMC, earnings, holidays, options expiry."""

import logging
from datetime import datetime, timedelta

from app.database import repositories as repo

logger = logging.getLogger("vibe.risk.events")

# FOMC 2026 meeting dates (static, update annually)
FOMC_2026 = [
    ("2026-01-27", "2026-01-28"),
    ("2026-03-17", "2026-03-18"),
    ("2026-05-05", "2026-05-06"),
    ("2026-06-16", "2026-06-17"),
    ("2026-07-28", "2026-07-29"),
    ("2026-09-15", "2026-09-16"),
    ("2026-11-03", "2026-11-04"),
    ("2026-12-15", "2026-12-16"),
]

# KR market holidays 2026 (approximate, major ones)
KR_HOLIDAYS_2026 = [
    ("2026-01-01", "New Year's Day"),
    ("2026-01-28", "Lunar New Year"),
    ("2026-01-29", "Lunar New Year"),
    ("2026-01-30", "Lunar New Year"),
    ("2026-03-01", "Independence Movement Day"),
    ("2026-05-05", "Children's Day"),
    ("2026-05-24", "Buddha's Birthday"),
    ("2026-06-06", "Memorial Day"),
    ("2026-08-15", "Liberation Day"),
    ("2026-09-24", "Chuseok"),
    ("2026-09-25", "Chuseok"),
    ("2026-09-26", "Chuseok"),
    ("2026-10-03", "National Foundation Day"),
    ("2026-10-09", "Hangul Day"),
    ("2026-12-25", "Christmas Day"),
]


class EventCalendar:
    """Manage economic events and earnings dates."""

    async def seed_static_events(self) -> int:
        """Insert FOMC schedule and KR holidays into DB."""
        events = []

        # FOMC meetings
        for day1, day2 in FOMC_2026:
            events.append({
                "event_date": day1,
                "event_type": "fomc",
                "market": None,
                "symbol": None,
                "description": f"FOMC Meeting Day 1 ({day1})",
                "impact_level": "high",
            })
            events.append({
                "event_date": day2,
                "event_type": "fomc",
                "market": None,
                "symbol": None,
                "description": f"FOMC Meeting Day 2 / Decision ({day2})",
                "impact_level": "high",
            })

        # KR holidays
        for date_str, name in KR_HOLIDAYS_2026:
            events.append({
                "event_date": date_str,
                "event_type": "kr_holiday",
                "market": "KR",
                "symbol": None,
                "description": name,
                "impact_level": "medium",
            })

        # US options expiry (3rd Friday of each month)
        for month in range(1, 13):
            dt = datetime(2026, month, 1)
            # Find first Friday
            days_until_friday = (4 - dt.weekday()) % 7
            first_friday = dt + timedelta(days=days_until_friday)
            third_friday = first_friday + timedelta(weeks=2)
            events.append({
                "event_date": third_friday.strftime("%Y-%m-%d"),
                "event_type": "options_expiry",
                "market": "US",
                "symbol": None,
                "description": f"US Monthly Options Expiry ({third_friday.strftime('%b %Y')})",
                "impact_level": "medium",
            })

        count = await repo.insert_events(events)
        logger.info("Seeded %d static events", count)
        return count

    async def check_upcoming_events(
        self,
        market: str,
        symbol: str | None = None,
        days_ahead: int = 3,
    ) -> list[dict]:
        """Return events within D-N for a symbol/market."""
        return await repo.get_upcoming_events(market, symbol=symbol, days_ahead=days_ahead)

    def should_suppress_signal(self, events: list[dict]) -> tuple[bool, str]:
        """If high-impact event within window, return (True, reason)."""
        high_impact = [e for e in events if e.get("impact_level") == "high"]
        if high_impact:
            event_names = ", ".join(e["description"][:40] for e in high_impact[:3])
            return True, f"High-impact event D-3: {event_names}"
        return False, ""
