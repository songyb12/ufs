import logging

from fastapi import APIRouter, HTTPException, Query

from app.database import repositories as repo
from app.database.connection import get_db
from app.models.schemas import DashboardResponse

logger = logging.getLogger("vibe.routers.dashboard")

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
    try:
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
            sig = row["final_signal"]
            if sig in signal_counts:
                signal_counts[sig] = row["cnt"]

        # Hard limit count (latest date)
        c = await db.execute(
            """SELECT COUNT(*) FROM signals
               WHERE signal_date = (SELECT MAX(signal_date) FROM signals)
               AND hard_limit_triggered = 1"""
        )
        row = await c.fetchone()
        hl_count = row[0] if row else 0

        # Portfolio P&L — single query for all groups or specific group
        # portfolio_id=0 → all groups, otherwise specific group
        portfolio_query = """
            SELECT ps.symbol, ps.market, ps.entry_price, ps.position_size,
                   w.name, lp.close as current_price
            FROM portfolio_state ps
            LEFT JOIN watchlist w ON ps.symbol = w.symbol AND ps.market = w.market
            LEFT JOIN (
                SELECT ph.symbol, ph.market, ph.close
                FROM price_history ph
                INNER JOIN (
                    SELECT symbol, market, MAX(trade_date) AS max_date
                    FROM price_history
                    GROUP BY symbol, market
                ) latest ON ph.symbol = latest.symbol
                        AND ph.market = latest.market
                        AND ph.trade_date = latest.max_date
            ) lp ON ps.symbol = lp.symbol AND ps.market = lp.market
            WHERE ps.position_size > 0
        """
        pf_params: list = []
        if portfolio_id > 0:
            portfolio_query += " AND ps.portfolio_id = ?"
            pf_params.append(portfolio_id)
        c = await db.execute(portfolio_query, pf_params)
        positions = [dict(r) for r in await c.fetchall()]
        total_invested = 0.0
        total_current = 0.0
        portfolio_items = []
        for p in positions:
            entry = p.get("entry_price") if p.get("entry_price") is not None else 0
            current = p.get("current_price") if p.get("current_price") is not None else entry
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

        # Total data counts (null-safe fetchone)
        c = await db.execute("SELECT COUNT(*) FROM price_history")
        row = await c.fetchone()
        price_count = row[0] if row else 0
        c = await db.execute("SELECT COUNT(*) FROM signals")
        row = await c.fetchone()
        signal_total = row[0] if row else 0
        c = await db.execute("SELECT COUNT(DISTINCT symbol) FROM watchlist WHERE is_active=1")
        row = await c.fetchone()
        watchlist_count = row[0] if row else 0

        # Latest signal date
        c = await db.execute("SELECT MAX(signal_date) FROM signals")
        row = await c.fetchone()
        latest_date = row[0] if row else None

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
    except Exception as e:
        logger.error("Dashboard summary SQL query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Dashboard summary failed. Check server logs for details.")


@router.get("/prices/{symbol}")
async def get_price_chart(
    symbol: str,
    market: str = Query("KR"),
    days: int = Query(60, ge=5, le=365),
):
    """Get OHLCV price data for charting."""
    try:
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
    except Exception as e:
        logger.error("Price chart query failed for %s: %s", symbol, e, exc_info=True)
        raise HTTPException(status_code=500, detail="가격 데이터 조회 실패")


@router.get("/signals/history")
async def get_signal_history(
    market: str | None = None,
    days: int = Query(30, ge=1, le=365),
    symbol: str | None = None,
):
    """Get signal history for the past N days, optionally filtered by symbol."""
    db = await get_db()
    query = """
        SELECT s.symbol, s.market, s.signal_date, s.raw_signal, s.raw_score,
               s.final_signal, s.hard_limit_triggered, s.rsi_value,
               s.disparity_value, s.technical_score, s.macro_score,
               s.fund_flow_score, s.rationale, s.explanation_rule,
               w.name
        FROM signals s
        INNER JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
            AND w.is_active = 1
        WHERE s.signal_date >= date('now', ?)
    """
    params: list = [f"-{days} days"]
    if market:
        query += " AND s.market = ?"
        params.append(market.upper())
    if symbol:
        query += " AND s.symbol = ?"
        params.append(symbol)
    query += " ORDER BY s.signal_date DESC, s.raw_score DESC"
    # Safety LIMIT: days param bounds the date range, but cap row count
    # to prevent excessive memory usage (50 symbols * 365 days = 18,250 max)
    query += " LIMIT 20000"

    c = await db.execute(query, params)
    rows = [dict(r) for r in await c.fetchall()]
    return {"count": len(rows), "signals": rows}


@router.get("/data-status")
async def get_data_status():
    """Get data freshness and coverage statistics for each table."""
    db = await get_db()
    tables = {}

    # Price History
    c = await db.execute(
        """SELECT COUNT(*) as cnt,
                  MIN(trade_date) as earliest,
                  MAX(trade_date) as latest,
                  COUNT(DISTINCT symbol) as symbols
           FROM price_history"""
    )
    r = await c.fetchone()
    tables["price_history"] = dict(r) if r else {"cnt": 0, "earliest": None, "latest": None, "symbols": 0}

    def _safe_dict(row, defaults=None):
        """Safely convert fetchone result to dict with fallback."""
        if row:
            return dict(row)
        return defaults or {"cnt": 0}

    # Signals
    c = await db.execute(
        """SELECT COUNT(*) as cnt,
                  MIN(signal_date) as earliest,
                  MAX(signal_date) as latest,
                  COUNT(DISTINCT symbol) as symbols
           FROM signals"""
    )
    tables["signals"] = _safe_dict(await c.fetchone(), {"cnt": 0, "earliest": None, "latest": None, "symbols": 0})

    # Macro Indicators
    c = await db.execute(
        """SELECT COUNT(*) as cnt,
                  MIN(indicator_date) as earliest,
                  MAX(indicator_date) as latest
           FROM macro_indicators"""
    )
    tables["macro_indicators"] = _safe_dict(await c.fetchone(), {"cnt": 0, "earliest": None, "latest": None})

    # Sentiment Data
    c = await db.execute(
        """SELECT COUNT(*) as cnt,
                  MIN(indicator_date) as earliest,
                  MAX(indicator_date) as latest
           FROM sentiment_data"""
    )
    tables["sentiment_data"] = _safe_dict(await c.fetchone(), {"cnt": 0, "earliest": None, "latest": None})

    # News Data
    c = await db.execute(
        """SELECT COUNT(*) as cnt,
                  MIN(trade_date) as earliest,
                  MAX(trade_date) as latest,
                  COUNT(DISTINCT symbol) as symbols
           FROM news_data"""
    )
    tables["news_data"] = _safe_dict(await c.fetchone(), {"cnt": 0, "earliest": None, "latest": None, "symbols": 0})

    # Fund Flow KR
    c = await db.execute(
        """SELECT COUNT(*) as cnt,
                  MIN(trade_date) as earliest,
                  MAX(trade_date) as latest,
                  COUNT(DISTINCT symbol) as symbols
           FROM fund_flow_kr"""
    )
    tables["fund_flow_kr"] = _safe_dict(await c.fetchone(), {"cnt": 0, "earliest": None, "latest": None, "symbols": 0})

    # Technical Indicators
    c = await db.execute(
        """SELECT COUNT(*) as cnt,
                  MAX(trade_date) as latest
           FROM technical_indicators"""
    )
    tables["technical_indicators"] = _safe_dict(await c.fetchone(), {"cnt": 0, "latest": None})

    # Watchlist
    c = await db.execute("SELECT COUNT(*) as cnt FROM watchlist WHERE is_active = 1")
    row = await c.fetchone()
    tables["watchlist_active"] = {"cnt": row[0] if row else 0}

    # Market Briefings
    c = await db.execute(
        """SELECT COUNT(*) as cnt, MAX(briefing_date) as latest
           FROM market_briefings"""
    )
    tables["market_briefings"] = _safe_dict(await c.fetchone(), {"cnt": 0, "latest": None})

    # LLM Reviews
    c = await db.execute(
        """SELECT COUNT(*) as cnt, MAX(review_date) as latest
           FROM llm_reviews"""
    )
    tables["llm_reviews"] = _safe_dict(await c.fetchone(), {"cnt": 0, "latest": None})

    return {"tables": tables}


@router.get("/reports/monthly")
async def get_monthly_reports(limit: int = Query(12, ge=1, le=24)):
    """Get recent monthly reports."""
    reports = await repo.get_monthly_reports(limit=limit)
    return {"reports": reports, "count": len(reports)}


@router.post("/reports/monthly/generate")
async def generate_monthly_report_endpoint(
    report_month: str | None = Query(None),
    market: str = Query("ALL"),
):
    """Generate a monthly report for the given month."""
    from app.reports.monthly_report import generate_monthly_report

    content = await generate_monthly_report(report_month, market)
    return {"status": "ok", "report": content}


@router.get("/reports/weekly")
async def get_weekly_reports(limit: int = Query(12, ge=1, le=52)):
    """Get recent weekly reports."""
    from app.database.connection import get_db
    import json as _json

    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM weekly_reports ORDER BY week_start DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    reports = []
    for row in rows:
        r = dict(row)
        try:
            r["content"] = _json.loads(r.get("report_json", "{}"))
        except Exception:
            r["content"] = {}
        reports.append(r)
    return {"reports": reports, "count": len(reports)}


@router.post("/reports/weekly/generate")
async def generate_weekly_report_endpoint(
    week_start: str | None = Query(None),
    market: str = Query("ALL"),
):
    """Generate a weekly report for the given week (Monday date)."""
    from app.reports.weekly_report import generate_weekly_report

    content = await generate_weekly_report(week_start, market)
    return {"status": "ok", "report": content}
