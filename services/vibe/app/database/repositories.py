import json
from datetime import datetime, timedelta, timezone

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


async def get_watchlist_item(symbol: str, market: str) -> dict | None:
    """Get a single watchlist item by symbol and market."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM watchlist WHERE symbol = ? AND market = ?",
            (symbol, market),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
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


async def get_symbol_names(market: str) -> dict[str, str]:
    """Return {symbol: name} mapping for active symbols in a market."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT symbol, name FROM watchlist WHERE market = ? AND is_active = 1",
            (market,),
        )
        rows = await cursor.fetchall()
        return {r["symbol"]: r["name"] for r in rows}
    finally:
        await db.close()


# ── Price History ──


async def upsert_price_history(rows: list[dict]) -> int:
    if not rows:
        return 0
    db = await get_db()
    try:
        await db.executemany(
            """INSERT OR REPLACE INTO price_history
               (symbol, market, trade_date, open, high, low, close, volume, adjusted_close)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    r["symbol"], r["market"], r["trade_date"],
                    r.get("open"), r.get("high"), r.get("low"),
                    r["close"], r.get("volume"), r.get("adjusted_close"),
                )
                for r in rows
            ],
        )
        await db.commit()
        return len(rows)
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
    if not rows:
        return 0
    db = await get_db()
    try:
        await db.executemany(
            """INSERT OR REPLACE INTO technical_indicators
               (symbol, market, trade_date, rsi_14, ma_5, ma_20, ma_60, ma_120,
                macd, macd_signal, macd_histogram,
                bollinger_upper, bollinger_middle, bollinger_lower,
                disparity_20, volume_ratio)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    r["symbol"], r["market"], r["trade_date"],
                    r.get("rsi_14"), r.get("ma_5"), r.get("ma_20"),
                    r.get("ma_60"), r.get("ma_120"),
                    r.get("macd"), r.get("macd_signal"), r.get("macd_histogram"),
                    r.get("bollinger_upper"), r.get("bollinger_middle"), r.get("bollinger_lower"),
                    r.get("disparity_20"), r.get("volume_ratio"),
                )
                for r in rows
            ],
        )
        await db.commit()
        return len(rows)
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
    if not rows:
        return 0
    db = await get_db()
    try:
        await db.executemany(
            """INSERT OR REPLACE INTO fund_flow_kr
               (symbol, trade_date, foreign_net_buy, institution_net_buy,
                individual_net_buy, pension_net_buy, foreign_holding_ratio)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    r["symbol"], r["trade_date"],
                    r.get("foreign_net_buy"), r.get("institution_net_buy"),
                    r.get("individual_net_buy"), r.get("pension_net_buy"),
                    r.get("foreign_holding_ratio"),
                )
                for r in rows
            ],
        )
        await db.commit()
        return len(rows)
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
    if not rows:
        return 0
    db = await get_db()
    try:
        await db.executemany(
            """INSERT OR REPLACE INTO signals
               (run_id, symbol, market, signal_date,
                raw_signal, raw_score, hard_limit_triggered, hard_limit_reason,
                final_signal, confidence, red_team_warning,
                rsi_value, disparity_value, macro_score, technical_score, fund_flow_score,
                rationale, explanation_rule, explanation_llm)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    r["run_id"], r["symbol"], r["market"], r["signal_date"],
                    r["raw_signal"], r["raw_score"],
                    1 if r.get("hard_limit_triggered") else 0,
                    r.get("hard_limit_reason"),
                    r["final_signal"], r.get("confidence"), r.get("red_team_warning"),
                    r.get("rsi_value"), r.get("disparity_value"),
                    r.get("macro_score"), r.get("technical_score"), r.get("fund_flow_score"),
                    r.get("rationale"), r.get("explanation_rule"), r.get("explanation_llm"),
                )
                for r in rows
            ],
        )
        await db.commit()
        return len(rows)
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


# ── Backtest Runs ──


async def insert_backtest_run(
    backtest_id: str, market: str, start_date: str, end_date: str, config_snapshot: dict,
) -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO backtest_runs
               (backtest_id, market, start_date, end_date, config_snapshot, status, started_at)
               VALUES (?, ?, ?, ?, ?, 'running', ?)""",
            (backtest_id, market, start_date, end_date,
             json.dumps(config_snapshot), datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
    finally:
        await db.close()


async def update_backtest_run(backtest_id: str, status: str, metrics: dict | None = None) -> None:
    db = await get_db()
    try:
        completed_at = datetime.now(timezone.utc).isoformat() if status != "running" else None
        if metrics:
            await db.execute(
                """UPDATE backtest_runs
                   SET status = ?, completed_at = ?, total_trades = ?,
                       hit_rate = ?, avg_return = ?, sharpe_ratio = ?,
                       max_drawdown = ?, profit_factor = ?, win_loss_ratio = ?,
                       total_return = ?, results_json = ?
                   WHERE backtest_id = ?""",
                (status, completed_at,
                 metrics.get("total_trades", 0),
                 metrics.get("hit_rate"), metrics.get("avg_return"),
                 metrics.get("sharpe_ratio"), metrics.get("max_drawdown"),
                 metrics.get("profit_factor"), metrics.get("win_loss_ratio"),
                 metrics.get("total_return"),
                 json.dumps(metrics, default=str),
                 backtest_id),
            )
        else:
            await db.execute(
                "UPDATE backtest_runs SET status = ?, completed_at = ? WHERE backtest_id = ?",
                (status, completed_at, backtest_id),
            )
        await db.commit()
    finally:
        await db.close()


async def get_backtest_runs(limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM backtest_runs ORDER BY started_at DESC LIMIT ?", (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_backtest_run(backtest_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM backtest_runs WHERE backtest_id = ?", (backtest_id,),
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            if result.get("results_json"):
                result["results_json"] = json.loads(result["results_json"])
            return result
        return None
    finally:
        await db.close()


async def insert_backtest_trades(trades: list[dict]) -> int:
    if not trades:
        return 0
    db = await get_db()
    try:
        await db.executemany(
            """INSERT INTO backtest_trades
               (backtest_id, symbol, market, entry_date, entry_price,
                entry_signal, entry_score, exit_date, exit_price,
                exit_reason, return_pct, holding_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (t["backtest_id"], t["symbol"], t["market"],
                 t["entry_date"], t["entry_price"],
                 t["entry_signal"], t["entry_score"],
                 t.get("exit_date"), t.get("exit_price"),
                 t.get("exit_reason"), t.get("return_pct"), t.get("holding_days"))
                for t in trades
            ],
        )
        await db.commit()
        return len(trades)
    finally:
        await db.close()


async def get_backtest_trades(backtest_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM backtest_trades WHERE backtest_id = ? ORDER BY entry_date",
            (backtest_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Signal Performance ──


async def insert_signal_performance(record: dict) -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR IGNORE INTO signal_performance
               (signal_id, symbol, market, signal_date, signal_type,
                signal_score, entry_price)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (record["signal_id"], record["symbol"], record["market"],
             record["signal_date"], record["signal_type"],
             record["signal_score"], record["entry_price"]),
        )
        await db.commit()
    finally:
        await db.close()


async def get_pending_performance_tracking(days_horizon: int = 20) -> list[dict]:
    """Get signals that still need T+1/5/20 performance tracking."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT sp.*, s.run_id FROM signal_performance sp
               JOIN signals s ON sp.signal_id = s.id
               WHERE (sp.return_t1 IS NULL OR sp.return_t5 IS NULL OR sp.return_t20 IS NULL)
               AND sp.signal_type IN ('BUY', 'SELL')
               ORDER BY sp.signal_date""",
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


_PERF_ALLOWED_COLUMNS = frozenset({
    "return_t1", "return_t5", "return_t20",
    "price_t1", "price_t5", "price_t20",
    "is_correct_t5", "is_correct_t20",
})


async def update_signal_performance(signal_id: int, updates: dict) -> None:
    db = await get_db()
    try:
        set_clauses = []
        params = []
        for key, val in updates.items():
            if key not in _PERF_ALLOWED_COLUMNS:
                raise ValueError(f"Column '{key}' not allowed in signal_performance update")
            set_clauses.append(f"{key} = ?")
            params.append(val)
        if not set_clauses:
            return
        set_clauses.append("tracked_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(signal_id)
        await db.execute(
            f"UPDATE signal_performance SET {', '.join(set_clauses)} WHERE signal_id = ?",
            params,
        )
        await db.commit()
    finally:
        await db.close()


async def get_performance_summary(market: str | None = None, since_date: str | None = None) -> dict:
    """Get aggregate performance statistics."""
    db = await get_db()
    try:
        where_clauses = ["signal_type IN ('BUY', 'SELL')"]
        params: list = []
        if market:
            where_clauses.append("market = ?")
            params.append(market)
        if since_date:
            where_clauses.append("signal_date >= ?")
            params.append(since_date)
        where = " AND ".join(where_clauses)

        cursor = await db.execute(
            f"""SELECT
                COUNT(*) as total_signals,
                COALESCE(SUM(CASE WHEN signal_type = 'BUY' THEN 1 ELSE 0 END), 0) as buy_signals,
                COALESCE(SUM(CASE WHEN signal_type = 'SELL' THEN 1 ELSE 0 END), 0) as sell_signals,
                AVG(CASE WHEN is_correct_t5 IS NOT NULL THEN is_correct_t5 END) as hit_rate_t5,
                AVG(CASE WHEN is_correct_t20 IS NOT NULL THEN is_correct_t20 END) as hit_rate_t20,
                AVG(return_t5) as avg_return_t5,
                AVG(return_t20) as avg_return_t20
            FROM signal_performance WHERE {where}""",
            params,
        )
        row = await cursor.fetchone()
        return dict(row) if row else {"total_signals": 0, "buy_signals": 0, "sell_signals": 0}
    finally:
        await db.close()


# ── Price History (extended queries for backtesting) ──


async def get_price_at_date(symbol: str, market: str, target_date: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM price_history
               WHERE symbol = ? AND market = ? AND trade_date <= ?
               ORDER BY trade_date DESC LIMIT 1""",
            (symbol, market, target_date),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_price_range(
    symbol: str, market: str, start_date: str, end_date: str,
) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM price_history
               WHERE symbol = ? AND market = ? AND trade_date BETWEEN ? AND ?
               ORDER BY trade_date ASC""",
            (symbol, market, start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_all_price_range(
    market: str, start_date: str, end_date: str,
) -> list[dict]:
    """Get price data for ALL active symbols in a market within date range."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT ph.* FROM price_history ph
               JOIN watchlist w ON ph.symbol = w.symbol AND ph.market = w.market
               WHERE ph.market = ? AND ph.trade_date BETWEEN ? AND ?
               AND w.is_active = 1
               ORDER BY ph.symbol, ph.trade_date ASC""",
            (market, start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_macro_range(start_date: str, end_date: str) -> list[dict]:
    """Get macro indicators for a date range."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM macro_indicators
               WHERE indicator_date BETWEEN ? AND ?
               ORDER BY indicator_date ASC""",
            (start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_fund_flow_range(symbol: str, start_date: str, end_date: str) -> list[dict]:
    """Get fund flow data for a symbol within date range."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM fund_flow_kr
               WHERE symbol = ? AND trade_date BETWEEN ? AND ?
               ORDER BY trade_date ASC""",
            (symbol, start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_signal_id_for_performance(run_id: str, symbol: str, market: str) -> int | None:
    """Get signal row id for creating performance tracking record."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM signals WHERE run_id = ? AND symbol = ? AND market = ?",
            (run_id, symbol, market),
        )
        row = await cursor.fetchone()
        return row["id"] if row else None
    finally:
        await db.close()


# ── Event Calendar (Phase B) ──


async def insert_events(events: list[dict]) -> int:
    db = await get_db()
    try:
        count = 0
        for e in events:
            try:
                cursor = await db.execute(
                    """INSERT OR IGNORE INTO event_calendar
                       (event_date, event_type, market, symbol, description, impact_level)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (e["event_date"], e["event_type"], e.get("market"),
                     e.get("symbol") or "", e["description"], e.get("impact_level", "medium")),
                )
                count += cursor.rowcount
            except Exception as exc:
                import logging
                logging.getLogger("vibe.repo").debug("Event insert skipped: %s", exc)
        await db.commit()
        return count
    finally:
        await db.close()


async def get_upcoming_events(
    market: str, symbol: str | None = None, days_ahead: int = 3,
) -> list[dict]:
    db = await get_db()
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        future = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        query = """SELECT * FROM event_calendar
                   WHERE event_date BETWEEN ? AND ?
                   AND (market IS NULL OR market = ?)"""
        params: list = [today, future, market]
        if symbol:
            query += " AND (symbol = '' OR symbol IS NULL OR symbol = ?)"
            params.append(symbol)
        query += " ORDER BY event_date"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Portfolio State (Phase B) ──


async def get_portfolio_state(market: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        query = "SELECT * FROM portfolio_state WHERE position_size > 0"
        params: list = []
        if market:
            query += " AND market = ?"
            params.append(market)
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def upsert_portfolio_position(symbol: str, market: str, data: dict) -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO portfolio_state
               (symbol, market, position_size, entry_date, entry_price, sector, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (symbol, market, data.get("position_size", 0),
             data.get("entry_date"), data.get("entry_price"),
             data.get("sector")),
        )
        await db.commit()
    finally:
        await db.close()


# ── Fundamental Data (Phase C) ──


async def upsert_fundamental_data(data: dict) -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO fundamental_data
               (symbol, market, trade_date, per, pbr, eps, roe,
                operating_margin, div_yield, market_cap,
                fundamental_score, value_score, quality_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["symbol"], data["market"], data["trade_date"],
             data.get("per"), data.get("pbr"), data.get("eps"),
             data.get("roe"), data.get("operating_margin"),
             data.get("div_yield"), data.get("market_cap"),
             data.get("fundamental_score"), data.get("value_score"),
             data.get("quality_score")),
        )
        await db.commit()
    finally:
        await db.close()


async def upsert_weekly_indicators(rows: list[dict]) -> int:
    """Persist weekly indicator data."""
    db = await get_db()
    try:
        count = 0
        for r in rows:
            cursor = await db.execute(
                """INSERT OR REPLACE INTO weekly_indicators
                   (symbol, market, week_ending, rsi_14_weekly,
                    ma_5_weekly, ma_20_weekly, macd_weekly, trend_direction)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["symbol"], r["market"], r["week_ending"],
                 r.get("rsi_14_weekly"), r.get("ma_5_weekly"),
                 r.get("ma_20_weekly"), r.get("macd_weekly"),
                 r.get("trend_direction")),
            )
            count += cursor.rowcount
        await db.commit()
        return count
    finally:
        await db.close()


async def get_latest_fundamental(symbol: str, market: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM fundamental_data
               WHERE symbol = ? AND market = ?
               ORDER BY trade_date DESC LIMIT 1""",
            (symbol, market),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ── Screening Candidates (Phase C) ──


async def insert_screening_candidate(data: dict) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO screening_candidates
               (symbol, market, detected_date, trigger_type, trigger_value,
                trigger_description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["symbol"], data["market"], data["detected_date"],
             data["trigger_type"], data.get("trigger_value"),
             data.get("trigger_description")),
        )
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


async def get_screening_candidates(
    market: str, status: str | None = None,
) -> list[dict]:
    db = await get_db()
    try:
        query = "SELECT * FROM screening_candidates WHERE market = ?"
        params: list = [market]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY detected_date DESC LIMIT 100"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Sentiment Data (Phase D) ──


async def upsert_sentiment_data(data: dict) -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO sentiment_data
               (indicator_date, fear_greed_index, put_call_ratio, vix_term_structure)
               VALUES (?, ?, ?, ?)""",
            (data["indicator_date"], data.get("fear_greed_index"),
             data.get("put_call_ratio"), data.get("vix_term_structure")),
        )
        await db.commit()
    finally:
        await db.close()


async def get_sentiment_history(days: int = 7) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM sentiment_data
               ORDER BY indicator_date DESC LIMIT ?""",
            (days,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_latest_sentiment() -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM sentiment_data ORDER BY indicator_date DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ── US Fund Flow (Phase D) ──


async def insert_us_fund_flow(data: dict) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT OR REPLACE INTO us_fund_flow
               (symbol, trade_date, data_type, value, description, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["symbol"], data["trade_date"], data["data_type"],
             data.get("value"), data.get("description"), data.get("source")),
        )
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


# ── News Data (Phase F) ──


async def insert_news_data(rows: list[dict]) -> int:
    """Store news analysis data."""
    db = await get_db()
    try:
        count = 0
        for r in rows:
            cursor = await db.execute(
                """INSERT INTO news_data
                   (run_id, symbol, market, trade_date, news_score,
                    article_count, bullish_count, bearish_count, headlines_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["run_id"], r["symbol"], r["market"], r["trade_date"],
                 r.get("news_score"), r.get("article_count"),
                 r.get("bullish_count"), r.get("bearish_count"),
                 r.get("headlines_json")),
            )
            count += cursor.rowcount
        await db.commit()
        return count
    finally:
        await db.close()


async def get_latest_news(symbol: str, market: str) -> dict | None:
    """Get latest news data for a symbol."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM news_data
               WHERE symbol = ? AND market = ?
               ORDER BY trade_date DESC LIMIT 1""",
            (symbol, market),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ── Portfolio Scenarios (Phase E) ──


async def insert_portfolio_scenarios(scenarios: list[dict]) -> int:
    db = await get_db()
    try:
        count = 0
        for s in scenarios:
            cursor = await db.execute(
                """INSERT INTO portfolio_scenarios
                   (run_id, symbol, market, scenario_date, scenario_type,
                    current_price, entry_price, pnl_pct,
                    scenarios_json, scenario_rule, scenario_llm, target_prices_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (s["run_id"], s["symbol"], s["market"], s["scenario_date"],
                 s["scenario_type"], s.get("current_price"), s.get("entry_price"),
                 s.get("pnl_pct"), s.get("scenarios_json"),
                 s.get("scenario_rule"), s.get("scenario_llm"),
                 s.get("target_prices_json")),
            )
            count += cursor.rowcount
        await db.commit()
        return count
    finally:
        await db.close()


async def get_latest_portfolio_scenarios(market: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        # Get latest run_id that has scenarios
        sub_query = "SELECT run_id FROM portfolio_scenarios"
        params: list = []
        if market:
            sub_query += " WHERE market = ?"
            params.append(market)
        sub_query += " ORDER BY created_at DESC LIMIT 1"

        cursor = await db.execute(sub_query, params)
        row = await cursor.fetchone()
        if not row:
            return []

        run_id = row["run_id"]
        query = "SELECT * FROM portfolio_scenarios WHERE run_id = ?"
        q_params: list = [run_id]
        if market:
            query += " AND market = ?"
            q_params.append(market)
        query += " ORDER BY scenario_type, symbol"

        cursor = await db.execute(query, q_params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def insert_llm_review(data: dict) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO llm_reviews
               (run_id, symbol, market, review_date, input_context,
                llm_response, model_used, risk_flags,
                confidence_adjustment, signal_override)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["run_id"], data["symbol"], data["market"],
             data["review_date"], data.get("input_context"),
             data.get("llm_response"), data.get("model_used"),
             data.get("risk_flags"), data.get("confidence_adjustment"),
             data.get("signal_override")),
        )
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()
