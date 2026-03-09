"""Monthly performance report generator.

Aggregates signal, performance, and pipeline data for a given month.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from app.database import repositories as repo
from app.database.connection import get_db

logger = logging.getLogger("vibe.reports.monthly")


async def generate_monthly_report(
    report_month: str | None = None,
    market: str = "ALL",
) -> dict:
    """Generate a monthly report for the given month (YYYY-MM format).

    If report_month is None, defaults to the previous month.

    Metrics:
    1. Signal counts (BUY/SELL/HOLD)
    2. Performance hit rates (T+5, T+20)
    3. Pipeline run statistics
    4. Top/worst performers by return_t20
    """
    if not report_month:
        today = date.today()
        first = today.replace(day=1)
        prev_last = first - timedelta(days=1)
        report_month = prev_last.strftime("%Y-%m")

    month_start = f"{report_month}-01"
    year, month = map(int, report_month.split("-"))
    if month == 12:
        month_end = f"{year + 1}-01-01"
    else:
        month_end = f"{year}-{month + 1:02d}-01"

    db = await get_db()

    # 1. Signal counts
    cursor = await db.execute(
        """SELECT final_signal, COUNT(*) as cnt FROM signals
           WHERE signal_date >= ? AND signal_date < ?
           GROUP BY final_signal""",
        (month_start, month_end),
    )
    signal_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    for row in await cursor.fetchall():
        if row["final_signal"] in signal_counts:
            signal_counts[row["final_signal"]] = row["cnt"]

    # 2. Performance hit rates
    cursor = await db.execute(
        """SELECT
             AVG(CASE WHEN is_correct_t5 IS NOT NULL THEN CAST(is_correct_t5 AS REAL) END) as hit_t5,
             AVG(CASE WHEN is_correct_t20 IS NOT NULL THEN CAST(is_correct_t20 AS REAL) END) as hit_t20,
             AVG(return_t5) as avg_ret_t5,
             AVG(return_t20) as avg_ret_t20
           FROM signal_performance
           WHERE signal_date >= ? AND signal_date < ?
           AND signal_type IN ('BUY', 'SELL')""",
        (month_start, month_end),
    )
    perf_row = await cursor.fetchone()
    perf = dict(perf_row) if perf_row else {}

    # 3. Pipeline run stats
    cursor = await db.execute(
        """SELECT status, COUNT(*) as cnt FROM pipeline_runs
           WHERE started_at >= ? AND started_at < ?
           GROUP BY status""",
        (month_start, month_end),
    )
    pipeline_stats = {}
    for row in await cursor.fetchall():
        pipeline_stats[row["status"]] = row["cnt"]

    # 4. Top performers (best BUY signals)
    cursor = await db.execute(
        """SELECT sp.symbol, sp.market, sp.return_t20, w.name
           FROM signal_performance sp
           LEFT JOIN watchlist w ON sp.symbol = w.symbol AND sp.market = w.market
           WHERE sp.signal_date >= ? AND sp.signal_date < ?
           AND sp.signal_type = 'BUY' AND sp.return_t20 IS NOT NULL
           ORDER BY sp.return_t20 DESC LIMIT 5""",
        (month_start, month_end),
    )
    top_performers = [dict(r) for r in await cursor.fetchall()]

    # 5. Worst performers
    cursor = await db.execute(
        """SELECT sp.symbol, sp.market, sp.return_t20, w.name
           FROM signal_performance sp
           LEFT JOIN watchlist w ON sp.symbol = w.symbol AND sp.market = w.market
           WHERE sp.signal_date >= ? AND sp.signal_date < ?
           AND sp.signal_type = 'BUY' AND sp.return_t20 IS NOT NULL
           ORDER BY sp.return_t20 ASC LIMIT 5""",
        (month_start, month_end),
    )
    worst_performers = [dict(r) for r in await cursor.fetchall()]

    hit_t5 = perf.get("hit_t5")
    hit_t20 = perf.get("hit_t20")
    avg_ret_t5 = perf.get("avg_ret_t5")
    avg_ret_t20 = perf.get("avg_ret_t20")

    content = {
        "report_month": report_month,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signals": signal_counts,
        "total_signals": sum(signal_counts.values()),
        "hit_rate_t5": round(hit_t5 * 100, 1) if hit_t5 is not None else None,
        "hit_rate_t20": round(hit_t20 * 100, 1) if hit_t20 is not None else None,
        "avg_return_t5": round(avg_ret_t5, 2) if avg_ret_t5 is not None else None,
        "avg_return_t20": round(avg_ret_t20, 2) if avg_ret_t20 is not None else None,
        "pipeline_runs": pipeline_stats,
        "top_performers": top_performers,
        "worst_performers": worst_performers,
    }

    # Save to DB
    await repo.upsert_monthly_report(report_month, market, content)
    logger.info("Monthly report generated: %s (market=%s)", report_month, market)

    return content
