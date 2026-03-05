from fastapi import APIRouter, Query

from app.database import repositories as repo
from app.database.connection import get_db
from app.models.schemas import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(market: str | None = None):
    """Get the latest dashboard snapshot."""
    snapshot = await repo.get_latest_dashboard(market=market)
    if not snapshot:
        return {
            "status": "not_generated",
            "message": "No dashboard snapshot available yet. Run the pipeline first.",
        }
    return {
        "snapshot_date": snapshot["snapshot_date"],
        "market": snapshot["market"],
        "run_id": snapshot["run_id"],
        "content": snapshot["content_json"],
        "discord_sent": bool(snapshot["discord_sent"]),
        "discord_sent_at": snapshot.get("discord_sent_at"),
    }


@router.get("/summary")
async def get_dashboard_summary(portfolio_id: int = Query(1)):
    """Aggregated KPI summary for the web dashboard."""
    db = await get_db()

    # Signal counts (latest date)
    c = await db.execute(
        """SELECT final_signal, COUNT(*) as cnt
           FROM signals
           WHERE signal_date = (SELECT MAX(signal_date) FROM signals)
           GROUP BY final_signal"""
    )
    signal_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    for row in await c.fetchall():
        signal_counts[row["final_signal"]] = row["cnt"]

    # Hard limit count (latest date)
    c = await db.execute(
        """SELECT COUNT(*) FROM signals
           WHERE signal_date = (SELECT MAX(signal_date) FROM signals)
           AND hard_limit_triggered = 1"""
    )
    hl_count = (await c.fetchone())[0]

    # Portfolio P&L — filtered by portfolio_id
    c = await db.execute(
        """SELECT ps.symbol, ps.market, ps.entry_price, ps.position_size,
                  w.name, lp.close as current_price
           FROM portfolio_state ps
           LEFT JOIN watchlist w ON ps.symbol = w.symbol AND ps.market = w.market
           LEFT JOIN (
               SELECT symbol, market, close
               FROM price_history
               WHERE (symbol, market, trade_date) IN (
                   SELECT symbol, market, MAX(trade_date)
                   FROM price_history
                   GROUP BY symbol, market
               )
           ) lp ON ps.symbol = lp.symbol AND ps.market = lp.market
           WHERE ps.position_size > 0 AND ps.portfolio_id = ?""",
        (portfolio_id,),
    )
    positions = [dict(r) for r in await c.fetchall()]
    total_invested = 0.0
    total_current = 0.0
    portfolio_items = []
    for p in positions:
        entry = p.get("entry_price") or 0
        current = p.get("current_price") or entry
        size = p.get("position_size", 0)
        pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
        total_invested += size  # size IS the invested KRW/USD amount
        if entry > 0:
            shares = size / entry  # derive share count from invested amount
            total_current += current * shares
        else:
            total_current += size  # no entry price = assume flat
        portfolio_items.append({
            "symbol": p["symbol"],
            "market": p["market"],
            "name": p.get("name", p["symbol"]),
            "entry_price": entry,
            "current_price": current,
            "position_size": size,
            "pnl_pct": round(pnl_pct, 2),
        })
    portfolio_pnl = round(
        (total_current - total_invested) / total_invested * 100, 2
    ) if total_invested > 0 else 0.0

    # Pipeline freshness
    last_kr = await repo.get_latest_pipeline_run("KR")
    last_us = await repo.get_latest_pipeline_run("US")

    # Total data counts
    c = await db.execute("SELECT COUNT(*) FROM price_history")
    price_count = (await c.fetchone())[0]
    c = await db.execute("SELECT COUNT(*) FROM signals")
    signal_total = (await c.fetchone())[0]
    c = await db.execute("SELECT COUNT(DISTINCT symbol) FROM watchlist WHERE is_active=1")
    watchlist_count = (await c.fetchone())[0]

    # Latest signal date
    c = await db.execute("SELECT MAX(signal_date) FROM signals")
    latest_date = (await c.fetchone())[0]

    return {
        "latest_signal_date": latest_date,
        "signals": signal_counts,
        "hard_limit_count": hl_count,
        "portfolio": {
            "positions": portfolio_items,
            "total_pnl_pct": portfolio_pnl,
            "holdings_count": len(positions),
        },
        "pipelines": {
            "KR": {
                "status": last_kr.get("status") if last_kr else "never_run",
                "last_run": last_kr.get("completed_at") or last_kr.get("started_at") if last_kr else None,
            },
            "US": {
                "status": last_us.get("status") if last_us else "never_run",
                "last_run": last_us.get("completed_at") or last_us.get("started_at") if last_us else None,
            },
        },
        "data": {
            "prices": price_count,
            "signals_total": signal_total,
            "watchlist": watchlist_count,
        },
    }


@router.get("/prices/{symbol}")
async def get_price_chart(
    symbol: str,
    market: str = Query("KR"),
    days: int = Query(60, ge=5, le=365),
):
    """Get OHLCV price data for charting."""
    db = await get_db()
    c = await db.execute(
        """SELECT trade_date, open, high, low, close, volume
           FROM price_history
           WHERE symbol = ? AND market = ?
           ORDER BY trade_date DESC
           LIMIT ?""",
        (symbol, market, days),
    )
    rows = [dict(r) for r in await c.fetchall()]
    rows.reverse()  # chronological order
    return {"symbol": symbol, "market": market, "data": rows}


@router.get("/signals/history")
async def get_signal_history(
    market: str | None = None,
    days: int = Query(30, ge=1, le=365),
):
    """Get signal history for the past N days."""
    db = await get_db()
    query = """
        SELECT s.symbol, s.market, s.signal_date, s.raw_signal, s.raw_score,
               s.final_signal, s.hard_limit_triggered, s.rsi_value,
               s.disparity_value, s.technical_score, s.macro_score,
               s.fund_flow_score, s.rationale, s.explanation_rule,
               w.name
        FROM signals s
        LEFT JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
        WHERE s.signal_date >= date('now', ?)
    """
    params: list = [f"-{days} days"]
    if market:
        query += " AND s.market = ?"
        params.append(market.upper())
    query += " ORDER BY s.signal_date DESC, s.raw_score DESC"

    c = await db.execute(query, params)
    rows = [dict(r) for r in await c.fetchall()]
    return {"count": len(rows), "signals": rows}


@router.get("/reports/monthly")
async def get_monthly_reports(limit: int = Query(12, ge=1, le=24)):
    """Get recent monthly reports."""
    reports = await repo.get_monthly_reports(limit=limit)
    return {"reports": reports, "count": len(reports)}


@router.post("/reports/monthly/generate")
async def generate_monthly_report_endpoint(
    report_month: str | None = None,
    market: str = "ALL",
):
    """Generate a monthly report for the given month."""
    from app.reports.monthly_report import generate_monthly_report

    content = await generate_monthly_report(report_month, market)
    return {"status": "ok", "report": content}
