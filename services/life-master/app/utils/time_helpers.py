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


def month_range(ref_date: str | None = None) -> tuple[str, str]:
    """Return (first_day, last_day) ISO strings for the month."""
    d = date.fromisoformat(ref_date) if ref_date else date.today()
    first = d.replace(day=1)
    if d.month == 12:
        last = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
    return first.isoformat(), last.isoformat()


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def days_from_now(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()
