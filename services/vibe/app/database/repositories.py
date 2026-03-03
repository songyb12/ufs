import json
from datetime import datetime, timezone

from app.database.connection import get_db


# ── Watchlist ──


async def get_watchlist(market: str | None = None, active_only: bool = True) -> list[dict]:
    db = await get_db()
    try:
        query = "SELECT * FROM watchlist WHERE 1=1"
        params: list = []
        if market:
            query += " AND market = ?"
            params.append(market)
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY market, symbol"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def add_watchlist_item(symbol: str, name: str, market: str, asset_type: str = "stock") -> dict | None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR IGNORE INTO watchlist (symbol, name, market, asset_type)
               VALUES (?, ?, ?, ?)""",
            (symbol, name, market, asset_type),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM watchlist WHERE symbol = ? AND market = ?",
            (symbol, market),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def add_watchlist_bulk(items: list[dict]) -> int:
    db = await get_db()
    try:
        count = 0
        for item in items:
            cursor = await db.execute(
                """INSERT OR IGNORE INTO watchlist (symbol, name, market, asset_type)
                   VALUES (?, ?, ?, ?)""",
                (item["symbol"], item["name"], item["market"], item.get("asset_type", "stock")),
            )
            count += cursor.rowcount
        await db.commit()
        return count
    finally:
        await db.close()


async def remove_watchlist_item(symbol: str, market: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE watchlist SET is_active = 0, updated_at = datetime('now') WHERE symbol = ? AND market = ?",
            (symbol, market),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_active_symbols(market: str) -> list[str]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT symbol FROM watchlist WHERE market = ? AND is_active = 1 ORDER BY symbol",
            (market,),
        )
        rows = await cursor.fetchall()
        return [r["symbol"] for r in rows]
    finally:
        await db.close()


# ── Price History ──


async def upsert_price_history(rows: list[dict]) -> int:
    db = await get_db()
    try:
        count = 0
        for r in rows:
            cursor = await db.execute(
                """INSERT OR REPLACE INTO price_history
                   (symbol, market, trade_date, open, high, low, close, volume, adjusted_close)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["symbol"], r["market"], r["trade_date"],
                    r.get("open"), r.get("high"), r.get("low"),
                    r["close"], r.get("volume"), r.get("adjusted_close"),
                ),
            )
            count += cursor.rowcount
        await db.commit()
        return count
    finally:
        await db.close()


async def get_price_history(symbol: str, market: str, limit: int = 200) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM price_history
               WHERE symbol = ? AND market = ?
               ORDER BY trade_date DESC LIMIT ?""",
            (symbol, market, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Technical Indicators ──


async def upsert_technical_indicators(rows: list[dict]) -> int:
    db = await get_db()
    try:
        count = 0
        for r in rows:
            cursor = await db.execute(
                """INSERT OR REPLACE INTO technical_indicators
                   (symbol, market, trade_date, rsi_14, ma_5, ma_20, ma_60, ma_120,
                    macd, macd_signal, macd_histogram,
                    bollinger_upper, bollinger_middle, bollinger_lower,
                    disparity_20, volume_ratio)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["symbol"], r["market"], r["trade_date"],
                    r.get("rsi_14"), r.get("ma_5"), r.get("ma_20"),
                    r.get("ma_60"), r.get("ma_120"),
                    r.get("macd"), r.get("macd_signal"), r.get("macd_histogram"),
                    r.get("bollinger_upper"), r.get("bollinger_middle"), r.get("bollinger_lower"),
                    r.get("disparity_20"), r.get("volume_ratio"),
                ),
            )
            count += cursor.rowcount
        await db.commit()
        return count
    finally:
        await db.close()


# ── Macro Indicators ──


async def upsert_macro_indicators(row: dict) -> bool:
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO macro_indicators
               (indicator_date, us_10y_yield, us_2y_yield, us_yield_spread,
                fed_funds_rate, dxy_index, vix, fear_greed_index,
                kr_base_rate, usd_krw, wti_crude, gold_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["indicator_date"],
                row.get("us_10y_yield"), row.get("us_2y_yield"), row.get("us_yield_spread"),
                row.get("fed_funds_rate"), row.get("dxy_index"),
                row.get("vix"), row.get("fear_greed_index"),
                row.get("kr_base_rate"), row.get("usd_krw"),
                row.get("wti_crude"), row.get("gold_price"),
            ),
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def get_latest_macro() -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM macro_indicators ORDER BY indicator_date DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ── Fund Flow KR ──


async def upsert_fund_flow_kr(rows: list[dict]) -> int:
    db = await get_db()
    try:
        count = 0
        for r in rows:
            cursor = await db.execute(
                """INSERT OR REPLACE INTO fund_flow_kr
                   (symbol, trade_date, foreign_net_buy, institution_net_buy,
                    individual_net_buy, pension_net_buy, foreign_holding_ratio)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["symbol"], r["trade_date"],
                    r.get("foreign_net_buy"), r.get("institution_net_buy"),
                    r.get("individual_net_buy"), r.get("pension_net_buy"),
                    r.get("foreign_holding_ratio"),
                ),
            )
            count += cursor.rowcount
        await db.commit()
        return count
    finally:
        await db.close()


# ── Pipeline Runs ──


async def insert_pipeline_run(run_id: str, market: str, run_type: str = "scheduled") -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO pipeline_runs (run_id, run_type, market, status, started_at)
               VALUES (?, ?, ?, 'running', ?)""",
            (run_id, run_type, market, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
    finally:
        await db.close()


async def update_pipeline_run(
    run_id: str,
    status: str,
    stages_completed: list[str] | None = None,
    error_message: str | None = None,
) -> None:
    db = await get_db()
    try:
        stages_json = json.dumps(stages_completed) if stages_completed else None
        completed_at = datetime.now(timezone.utc).isoformat() if status != "running" else None
        await db.execute(
            """UPDATE pipeline_runs
               SET status = ?, completed_at = ?, stages_completed = ?, error_message = ?
               WHERE run_id = ?""",
            (status, completed_at, stages_json, error_message, run_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_latest_pipeline_run(market: str | None = None) -> dict | None:
    db = await get_db()
    try:
        query = "SELECT * FROM pipeline_runs"
        params: list = []
        if market:
            query += " WHERE market = ?"
            params.append(market)
        query += " ORDER BY started_at DESC LIMIT 1"
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            if result.get("stages_completed"):
                result["stages_completed"] = json.loads(result["stages_completed"])
            return result
        return None
    finally:
        await db.close()


async def get_pipeline_runs(limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            r = dict(row)
            if r.get("stages_completed"):
                r["stages_completed"] = json.loads(r["stages_completed"])
            results.append(r)
        return results
    finally:
        await db.close()


# ── Signals ──


async def insert_signals(rows: list[dict]) -> int:
    db = await get_db()
    try:
        count = 0
        for r in rows:
            cursor = await db.execute(
                """INSERT OR REPLACE INTO signals
                   (run_id, symbol, market, signal_date,
                    raw_signal, raw_score, hard_limit_triggered, hard_limit_reason,
                    final_signal, confidence, red_team_warning,
                    rsi_value, disparity_value, macro_score, technical_score, fund_flow_score,
                    rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["run_id"], r["symbol"], r["market"], r["signal_date"],
                    r["raw_signal"], r["raw_score"],
                    1 if r.get("hard_limit_triggered") else 0,
                    r.get("hard_limit_reason"),
                    r["final_signal"], r.get("confidence"), r.get("red_team_warning"),
                    r.get("rsi_value"), r.get("disparity_value"),
                    r.get("macro_score"), r.get("technical_score"), r.get("fund_flow_score"),
                    r.get("rationale"),
                ),
            )
            count += cursor.rowcount
        await db.commit()
        return count
    finally:
        await db.close()


async def get_latest_signals(market: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        query = """
            SELECT s.*, w.name FROM signals s
            LEFT JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
            WHERE s.signal_date = (SELECT MAX(signal_date) FROM signals)
        """
        params: list = []
        if market:
            query += " AND s.market = ?"
            params.append(market)
        query += " ORDER BY s.raw_score DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Dashboard Snapshots ──


async def save_dashboard_snapshot(
    run_id: str, snapshot_date: str, market: str, content: dict
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO dashboard_snapshots (run_id, snapshot_date, market, content_json)
               VALUES (?, ?, ?, ?)""",
            (run_id, snapshot_date, market, json.dumps(content, ensure_ascii=False)),
        )
        await db.commit()
        return cursor.lastrowid or 0
    finally:
        await db.close()


async def mark_dashboard_sent(snapshot_id: int) -> None:
    db = await get_db()
    try:
        await db.execute(
            """UPDATE dashboard_snapshots
               SET discord_sent = 1, discord_sent_at = ?
               WHERE id = ?""",
            (datetime.now(timezone.utc).isoformat(), snapshot_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_latest_dashboard(market: str | None = None) -> dict | None:
    db = await get_db()
    try:
        query = "SELECT * FROM dashboard_snapshots"
        params: list = []
        if market:
            query += " WHERE market = ?"
            params.append(market)
        query += " ORDER BY snapshot_date DESC LIMIT 1"
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            result["content_json"] = json.loads(result["content_json"])
            return result
        return None
    finally:
        await db.close()
