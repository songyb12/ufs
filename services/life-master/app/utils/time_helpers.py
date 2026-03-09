"""Time and date utility functions."""

from datetime import date, timedelta

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def today_str() -> str:
    return date.today().isoformat()


def today_day_name() -> str:
    return DAY_NAMES[date.today().weekday()]


def week_range(ref_date: str | None = None) -> tuple[str, str]:
    """Return (monday, sunday) ISO strings for the week containing ref_date."""
    d = date.fromisoformat(ref_date) if ref_date else date.today()
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()
