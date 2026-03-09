"""Streak and completion rate calculation logic."""

from datetime import date, timedelta


def calculate_streak(logs: list[dict], target_value: float = 1.0) -> dict:
    """Calculate streak info from habit logs (sorted by date DESC expected)."""
    if not logs:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "weekly_rate": 0.0,
            "monthly_rate": 0.0,
            "total_logs": 0,
        }

    today = date.today()
    log_dates = set()
    for log in logs:
        if log.get("value", 0) >= target_value:
            log_dates.add(log["date"])

    # Current streak: consecutive days ending today or yesterday
    current_streak = 0
    check = today
    # Allow starting from today or yesterday
    if str(check) not in log_dates:
        check = today - timedelta(days=1)
    while str(check) in log_dates:
        current_streak += 1
        check -= timedelta(days=1)

    # Longest streak
    if not log_dates:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "weekly_rate": 0.0,
            "monthly_rate": 0.0,
            "total_logs": len(logs),
        }

    sorted_dates = sorted(date.fromisoformat(d) for d in log_dates)
    longest_streak = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] - sorted_dates[i - 1] == timedelta(days=1):
            run += 1
            longest_streak = max(longest_streak, run)
        else:
            run = 1

    # Weekly rate (last 7 days)
    week_start = today - timedelta(days=6)
    week_hits = sum(1 for d in log_dates if date.fromisoformat(d) >= week_start)
    weekly_rate = round(week_hits / 7, 3)

    # Monthly rate (last 30 days)
    month_start = today - timedelta(days=29)
    month_hits = sum(1 for d in log_dates if date.fromisoformat(d) >= month_start)
    monthly_rate = round(month_hits / 30, 3)

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "weekly_rate": weekly_rate,
        "monthly_rate": monthly_rate,
        "total_logs": len(logs),
    }
