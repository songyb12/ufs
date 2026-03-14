"""Weekly performance report generator.

Aggregates signal, portfolio, and macro data for a given week (Mon-Sun).
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone

from app.database.connection import get_db

logger = logging.getLogger("vibe.reports.weekly")


async def generate_weekly_report(
    week_start: str | None = None,
    market: str = "ALL",
) -> dict:
    """Generate a weekly report for the given week.

    week_start: ISO date string for Monday (YYYY-MM-DD). Defaults to last week.

    Metrics:
    1. Signal distribution (BUY/SELL/HOLD)
    2. Portfolio weekly P&L
    3. Macro regime snapshot
    4. Top movers from watchlist
    5. Key events summary
    """
    if not week_start:
        today = date.today()
        # Last Monday
        last_monday = today - timedelta(days=today.weekday() + 7)
        week_start = last_monday.isoformat()

    ws = date.fromisoformat(week_start)
    # Ensure it's a Monday
    ws = ws - timedelta(days=ws.weekday())
    week_start = ws.isoformat()
    week_end = (ws + timedelta(days=7)).isoformat()

    db = await get_db()

    # Market filter
    mf_sig = " AND market = ?" if market != "ALL" else ""
    mp_sig = (market,) if market != "ALL" else ()
    mf_perf = " AND sp.market = ?" if market != "ALL" else ""
    mp_perf = (market,) if market != "ALL" else ()

    # 1. Signal counts
    cursor = await db.execute(
        f"""SELECT final_signal, COUNT(*) as cnt FROM signals
           WHERE signal_date >= ? AND signal_date < ?{mf_sig}
           GROUP BY final_signal""",
        (week_start, week_end) + mp_sig,
    )
    signal_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    for row in await cursor.fetchall():
        if row["final_signal"] in signal_counts:
            signal_counts[row["final_signal"]] = row["cnt"]

    # 2. Performance for signals issued this week
    cursor = await db.execute(
        f"""SELECT
             AVG(CASE WHEN is_correct_t5 IS NOT NULL THEN CAST(is_correct_t5 AS REAL) END) as hit_t5,
             AVG(return_t5) as avg_ret_t5,
             COUNT(*) as perf_count
           FROM signal_performance sp
           WHERE signal_date >= ? AND signal_date < ?
           AND signal_type IN ('BUY', 'SELL'){mf_perf}""",
        (week_start, week_end) + mp_perf,
    )
    perf_row = await cursor.fetchone()
    perf = dict(perf_row) if perf_row else {}

    # 3. Portfolio weekly P&L (positions that were active during this week)
    portfolio = {}
    try:
        cursor = await db.execute(
            """SELECT
                 SUM(CASE WHEN unrealized_pnl IS NOT NULL THEN unrealized_pnl ELSE 0 END) as total_pnl,
                 COUNT(*) as position_count
               FROM portfolio_positions
               WHERE status = 'open'"""
        )
        port_row = await cursor.fetchone()
        portfolio = dict(port_row) if port_row else {}
    except Exception:
        logger.debug("portfolio_positions table not available, skipping")

    # 4. Macro snapshot (latest in the week)
    cursor = await db.execute(
        """SELECT indicator_date, vix, wti_crude, gold_price, usd_krw, dxy_index,
                  fear_greed_index, us_10y_yield
           FROM macro_indicators
           WHERE indicator_date >= ? AND indicator_date < ?
           ORDER BY indicator_date DESC LIMIT 1""",
        (week_start, week_end),
    )
    macro_row = await cursor.fetchone()
    macro = dict(macro_row) if macro_row else None

    # 5. Top movers from watchlist (biggest price changes)
    cursor = await db.execute(
        f"""SELECT w.symbol, w.market, w.name,
                   ph_latest.close as latest_close, ph_prev.close as prev_close
           FROM watchlist w
           LEFT JOIN (
             SELECT symbol, market, close FROM price_history
             WHERE trade_date = (SELECT MAX(trade_date) FROM price_history WHERE trade_date < ?)
             GROUP BY symbol, market
           ) ph_prev ON w.symbol = ph_prev.symbol AND w.market = ph_prev.market
           LEFT JOIN (
             SELECT symbol, market, close FROM price_history
             WHERE trade_date = (SELECT MAX(trade_date) FROM price_history WHERE trade_date < ?)
             GROUP BY symbol, market
           ) ph_latest ON w.symbol = ph_latest.symbol AND w.market = ph_latest.market
           WHERE ph_latest.close IS NOT NULL AND ph_prev.close IS NOT NULL AND ph_prev.close > 0
           ORDER BY ABS((ph_latest.close - ph_prev.close) / ph_prev.close) DESC
           LIMIT 10""",
        (week_start, week_end),
    )
    movers = []
    for row in await cursor.fetchall():
        r = dict(row)
        if r["prev_close"] and r["prev_close"] > 0:
            r["change_pct"] = round((r["latest_close"] - r["prev_close"]) / r["prev_close"] * 100, 2)
        movers.append(r)

    # 6. Pipeline run stats for the week
    cursor = await db.execute(
        """SELECT status, COUNT(*) as cnt FROM pipeline_runs
           WHERE started_at >= ? AND started_at < ?
           GROUP BY status""",
        (week_start, week_end),
    )
    pipeline_stats = {}
    for row in await cursor.fetchall():
        pipeline_stats[row["status"]] = row["cnt"]

    content = {
        "week_start": week_start,
        "week_end": week_end,
        "market": market,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signals": signal_counts,
        "total_signals": sum(signal_counts.values()),
        "hit_rate_t5": round(perf.get("hit_t5", 0) * 100, 1) if perf.get("hit_t5") else None,
        "avg_return_t5": round(perf.get("avg_ret_t5", 0), 2) if perf.get("avg_ret_t5") else None,
        "portfolio": {
            "total_pnl": portfolio.get("total_pnl"),
            "position_count": portfolio.get("position_count", 0),
        },
        "macro_snapshot": macro,
        "top_movers": movers,
        "pipeline_runs": pipeline_stats,
    }

    # Save to DB
    await db.execute(
        """INSERT INTO weekly_reports (week_start, week_end, market, report_json, created_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(week_start, market) DO UPDATE SET
             report_json = excluded.report_json,
             created_at = excluded.created_at""",
        (week_start, week_end, market, json.dumps(content, ensure_ascii=False),
         datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()
    logger.info("Weekly report generated: %s ~ %s (market=%s)", week_start, week_end, market)

    return content
