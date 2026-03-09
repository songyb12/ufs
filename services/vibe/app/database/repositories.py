import json
import logging
from datetime import datetime, timedelta, timezone

from app.database.connection import get_db

logger = logging.getLogger("vibe.database.repo")


def _safe_json_loads(value: str | None, fallback=None):
    """Parse JSON string safely, returning fallback on failure."""
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("JSON parse error: %s (value=%s...)", e, str(value)[:50])
        return fallback


# ── Watchlist ──


async def get_watchlist(market: str | None = None, active_only: bool = True) -> list[dict]:
    db = await get_db()
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


async def get_watchlist_item(symbol: str, market: str) -> dict | None:
    """Get a single watchlist item by symbol and market."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM watchlist WHERE symbol = ? AND market = ?",
        (symbol, market),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def add_watchlist_item(symbol: str, name: str, market: str, asset_type: str = "stock") -> dict | None:
    db = await get_db()
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


async def add_watchlist_bulk(items: list[dict]) -> int:
    if not items:
        return 0
    db = await get_db()
    cursor = await db.executemany(
        """INSERT OR IGNORE INTO watchlist (symbol, name, market, asset_type)
           VALUES (?, ?, ?, ?)""",
        [
            (item["symbol"], item["name"], item["market"], item.get("asset_type", "stock"))
            for item in items
        ],
    )
    await db.commit()
    # executemany rowcount returns total affected rows
    return cursor.rowcount if hasattr(cursor, 'rowcount') else len(items)


async def remove_watchlist_item(symbol: str, market: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE watchlist SET is_active = 0, updated_at = datetime('now') WHERE symbol = ? AND market = ?",
        (symbol, market),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_active_symbols(market: str) -> list[str]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT symbol FROM watchlist WHERE market = ? AND is_active = 1 ORDER BY symbol",
        (market,),
    )
    rows = await cursor.fetchall()
    return [r["symbol"] for r in rows]


async def get_symbol_names(market: str) -> dict[str, str]:
    """Return {symbol: name} mapping for active symbols in a market."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT symbol, name FROM watchlist WHERE market = ? AND is_active = 1",
        (market,),
    )
    rows = await cursor.fetchall()
    return {r["symbol"]: r["name"] for r in rows}


# ── Price History ──


async def upsert_price_history(rows: list[dict]) -> int:
    if not rows:
        return 0
    db = await get_db()
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


async def get_price_history(symbol: str, market: str, limit: int = 200) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM price_history
           WHERE symbol = ? AND market = ?
           ORDER BY trade_date DESC LIMIT ?""",
        (symbol, market, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Technical Indicators ──


async def upsert_technical_indicators(rows: list[dict]) -> int:
    if not rows:
        return 0
    db = await get_db()
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


# ── Macro Indicators ──


async def upsert_macro_indicators(row: dict) -> bool:
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO macro_indicators
           (indicator_date, us_10y_yield, us_2y_yield, us_yield_spread,
            fed_funds_rate, dxy_index, vix, fear_greed_index,
            kr_base_rate, usd_krw, wti_crude, gold_price, copper_price)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            row["indicator_date"],
            row.get("us_10y_yield"), row.get("us_2y_yield"), row.get("us_yield_spread"),
            row.get("fed_funds_rate"), row.get("dxy_index"),
            row.get("vix"), row.get("fear_greed_index"),
            row.get("kr_base_rate"), row.get("usd_krw"),
            row.get("wti_crude"), row.get("gold_price"), row.get("copper_price"),
        ),
    )
    await db.commit()
    return True


async def get_latest_macro() -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM macro_indicators ORDER BY indicator_date DESC LIMIT 1"
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


# ── Fund Flow KR ──


async def upsert_fund_flow_kr(rows: list[dict]) -> int:
    if not rows:
        return 0
    db = await get_db()
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


# ── Pipeline Runs ──


async def insert_pipeline_run(run_id: str, market: str, run_type: str = "scheduled") -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO pipeline_runs (run_id, run_type, market, status, started_at)
           VALUES (?, ?, ?, 'running', ?)""",
        (run_id, run_type, market, datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()


async def update_pipeline_run(
    run_id: str,
    status: str,
    stages_completed: list[str] | None = None,
    error_message: str | None = None,
) -> None:
    db = await get_db()
    stages_json = json.dumps(stages_completed) if stages_completed else None
    completed_at = datetime.now(timezone.utc).isoformat() if status != "running" else None
    await db.execute(
        """UPDATE pipeline_runs
           SET status = ?, completed_at = ?, stages_completed = ?, error_message = ?
           WHERE run_id = ?""",
        (status, completed_at, stages_json, error_message, run_id),
    )
    await db.commit()


async def get_latest_pipeline_run(market: str | None = None) -> dict | None:
    db = await get_db()
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
        result["stages_completed"] = _safe_json_loads(result.get("stages_completed"), []) if result.get("stages_completed") else []
        return result
    return None


async def get_pipeline_runs(limit: int = 20) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    results = []
    for row in rows:
        r = dict(row)
        r["stages_completed"] = _safe_json_loads(r.get("stages_completed"), []) if r.get("stages_completed") else []
        results.append(r)
    return results


# ── Signals ──


async def insert_signals(rows: list[dict]) -> int:
    if not rows:
        return 0
    db = await get_db()
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


async def get_latest_signals(market: str | None = None) -> list[dict]:
    db = await get_db()
    if market:
        # Use market-specific max date to avoid cross-market date mismatch
        query = """
            SELECT s.*, w.name FROM signals s
            INNER JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
                AND w.is_active = 1
            WHERE s.market = ?
            AND s.signal_date = (SELECT MAX(signal_date) FROM signals WHERE market = ?)
            ORDER BY s.raw_score DESC
        """
        params: list = [market, market]
    else:
        # No market filter: get each market's latest date via correlated subquery
        query = """
            SELECT s.*, w.name FROM signals s
            INNER JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
                AND w.is_active = 1
            WHERE s.signal_date = (
                SELECT MAX(s2.signal_date) FROM signals s2 WHERE s2.market = s.market
            )
            ORDER BY s.raw_score DESC
        """
        params = []
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Dashboard Snapshots ──


async def save_dashboard_snapshot(
    run_id: str, snapshot_date: str, market: str, content: dict
) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO dashboard_snapshots (run_id, snapshot_date, market, content_json)
           VALUES (?, ?, ?, ?)""",
        (run_id, snapshot_date, market, json.dumps(content, ensure_ascii=False)),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def mark_dashboard_sent(snapshot_id: int) -> None:
    db = await get_db()
    await db.execute(
        """UPDATE dashboard_snapshots
           SET discord_sent = 1, discord_sent_at = ?
           WHERE id = ?""",
        (datetime.now(timezone.utc).isoformat(), snapshot_id),
    )
    await db.commit()


async def get_latest_dashboard(market: str | None = None) -> dict | None:
    db = await get_db()
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
        result["content_json"] = _safe_json_loads(result["content_json"], {})
        return result
    return None


# ── Backtest Runs ──


async def insert_backtest_run(
    backtest_id: str, market: str, start_date: str, end_date: str, config_snapshot: dict,
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO backtest_runs
           (backtest_id, market, start_date, end_date, config_snapshot, status, started_at)
           VALUES (?, ?, ?, ?, ?, 'running', ?)""",
        (backtest_id, market, start_date, end_date,
         json.dumps(config_snapshot), datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()


async def update_backtest_run(backtest_id: str, status: str, metrics: dict | None = None) -> None:
    db = await get_db()
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


async def get_backtest_runs(limit: int = 20) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM backtest_runs ORDER BY started_at DESC LIMIT ?", (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_backtest_run(backtest_id: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM backtest_runs WHERE backtest_id = ?", (backtest_id,),
    )
    row = await cursor.fetchone()
    if row:
        result = dict(row)
        if result.get("results_json"):
            result["results_json"] = _safe_json_loads(result["results_json"], {})
        if result.get("config_snapshot"):
            result["config_snapshot"] = _safe_json_loads(result["config_snapshot"], {})
        return result
    return None


async def insert_backtest_trades(trades: list[dict]) -> int:
    if not trades:
        return 0
    db = await get_db()
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


async def get_backtest_trades(backtest_id: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM backtest_trades WHERE backtest_id = ? ORDER BY entry_date",
        (backtest_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Signal Performance ──


async def insert_signal_performance(record: dict) -> None:
    db = await get_db()
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


async def get_pending_performance_tracking(days_horizon: int = 20) -> list[dict]:
    """Get signals that still need T+1/5/20 performance tracking."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT sp.*, s.run_id FROM signal_performance sp
           JOIN signals s ON sp.signal_id = s.id
           WHERE (sp.return_t1 IS NULL OR sp.return_t5 IS NULL OR sp.return_t20 IS NULL)
           AND sp.signal_type IN ('BUY', 'SELL')
           ORDER BY sp.signal_date""",
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


_PERF_ALLOWED_COLUMNS = frozenset({
    "return_t1", "return_t5", "return_t20",
    "price_t1", "price_t5", "price_t20",
    "is_correct_t5", "is_correct_t20",
})


async def update_signal_performance(signal_id: int, updates: dict) -> None:
    db = await get_db()
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


async def get_performance_summary(market: str | None = None, since_date: str | None = None) -> dict:
    """Get aggregate performance statistics."""
    db = await get_db()
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


# ── Price History (extended queries for backtesting) ──


async def get_price_at_date(symbol: str, market: str, target_date: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM price_history
           WHERE symbol = ? AND market = ? AND trade_date <= ?
           ORDER BY trade_date DESC LIMIT 1""",
        (symbol, market, target_date),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_price_range(
    symbol: str, market: str, start_date: str, end_date: str,
) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM price_history
           WHERE symbol = ? AND market = ? AND trade_date BETWEEN ? AND ?
           ORDER BY trade_date ASC""",
        (symbol, market, start_date, end_date),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_all_price_range(
    market: str, start_date: str, end_date: str,
) -> list[dict]:
    """Get price data for ALL active symbols in a market within date range."""
    db = await get_db()
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


async def get_macro_range(start_date: str, end_date: str) -> list[dict]:
    """Get macro indicators for a date range."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM macro_indicators
           WHERE indicator_date BETWEEN ? AND ?
           ORDER BY indicator_date ASC""",
        (start_date, end_date),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_fund_flow_range(symbol: str, start_date: str, end_date: str) -> list[dict]:
    """Get fund flow data for a symbol within date range."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM fund_flow_kr
           WHERE symbol = ? AND trade_date BETWEEN ? AND ?
           ORDER BY trade_date ASC""",
        (symbol, start_date, end_date),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_signal_id_for_performance(run_id: str, symbol: str, market: str) -> int | None:
    """Get signal row id for creating performance tracking record.

    Uses symbol+market+signal_date lookup (matches UNIQUE constraint) instead of
    run_id, which may change if the pipeline re-runs on the same day.
    """
    db = await get_db()
    # First try exact run_id match
    cursor = await db.execute(
        "SELECT id FROM signals WHERE run_id = ? AND symbol = ? AND market = ?",
        (run_id, symbol, market),
    )
    row = await cursor.fetchone()
    if row:
        return row["id"]
    # Fallback: latest signal for this symbol (handles INSERT OR REPLACE re-runs)
    cursor = await db.execute(
        "SELECT id FROM signals WHERE symbol = ? AND market = ? ORDER BY signal_date DESC LIMIT 1",
        (symbol, market),
    )
    row = await cursor.fetchone()
    return row["id"] if row else None


# ── Event Calendar (Phase B) ──


async def insert_events(events: list[dict]) -> int:
    if not events:
        return 0
    db = await get_db()
    valid_rows = []
    for e in events:
        try:
            valid_rows.append((
                e["event_date"], e["event_type"], e.get("market"),
                e.get("symbol") or "", e["description"], e.get("impact_level", "medium"),
            ))
        except (KeyError, TypeError) as exc:
            logger.debug("Event insert skipped (bad data): %s", exc)
    if not valid_rows:
        return 0
    cursor = await db.executemany(
        """INSERT OR IGNORE INTO event_calendar
           (event_date, event_type, market, symbol, description, impact_level)
           VALUES (?, ?, ?, ?, ?, ?)""",
        valid_rows,
    )
    await db.commit()
    return cursor.rowcount if hasattr(cursor, 'rowcount') else len(valid_rows)


async def get_upcoming_events(
    market: str, symbol: str | None = None, days_ahead: int = 3,
) -> list[dict]:
    db = await get_db()
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


# ── Portfolio Groups (Phase G) ──


async def get_portfolio_groups() -> list[dict]:
    """Get all portfolio groups."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM portfolio_groups ORDER BY is_default DESC, id")
    return [dict(r) for r in await cursor.fetchall()]


async def get_portfolio_group(group_id: int) -> dict | None:
    """Get a single portfolio group by id."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM portfolio_groups WHERE id = ?", (group_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_portfolio_group(name: str, description: str | None = None) -> int:
    """Create a new portfolio group. Returns the new group id."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO portfolio_groups (name, description) VALUES (?, ?)""",
        (name, description),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def update_portfolio_group(group_id: int, name: str, description: str | None = None) -> bool:
    """Update a portfolio group name/description."""
    db = await get_db()
    cursor = await db.execute(
        """UPDATE portfolio_groups SET name = ?, description = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (name, description, group_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_portfolio_group(group_id: int) -> bool:
    """Delete a portfolio group and all its positions. Cannot delete default group."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT is_default FROM portfolio_groups WHERE id = ?", (group_id,),
    )
    row = await cursor.fetchone()
    if not row or row["is_default"]:
        return False
    await db.execute("DELETE FROM portfolio_state WHERE portfolio_id = ?", (group_id,))
    await db.execute("DELETE FROM portfolio_groups WHERE id = ?", (group_id,))
    await db.commit()
    return True


# ── Portfolio State (Phase B, updated Phase G+) ──


async def get_portfolio_state(
    portfolio_id: int = 1,
    market: str | None = None,
    include_hidden: bool = False,
) -> list[dict]:
    db = await get_db()
    query = """
        SELECT ps.*, w.name,
               lp.close AS current_price,
               lp.trade_date AS price_date,
               CASE
                   WHEN ps.entry_price > 0 AND lp.close IS NOT NULL
                   THEN ROUND((lp.close - ps.entry_price) / ps.entry_price * 100, 2)
                   ELSE NULL
               END AS pnl_pct
        FROM portfolio_state ps
        LEFT JOIN watchlist w ON ps.symbol = w.symbol AND ps.market = w.market
        LEFT JOIN (
            SELECT ph.symbol, ph.market, ph.close, ph.trade_date
            FROM price_history ph
            INNER JOIN (
                SELECT symbol, market, MAX(trade_date) AS max_date
                FROM price_history
                GROUP BY symbol, market
            ) latest ON ph.symbol = latest.symbol
                    AND ph.market = latest.market
                    AND ph.trade_date = latest.max_date
        ) lp ON ps.symbol = lp.symbol AND ps.market = lp.market
        WHERE ps.portfolio_id = ? AND ps.position_size > 0
    """
    params: list = [portfolio_id]
    if not include_hidden:
        query += " AND ps.is_hidden = 0"
    if market:
        query += " AND ps.market = ?"
        params.append(market)
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def toggle_position_hidden(
    symbol: str, market: str, portfolio_id: int = 1,
) -> dict:
    """Toggle is_hidden flag for a position. Returns updated state."""
    db = await get_db()
    cursor = await db.execute(
        """UPDATE portfolio_state
           SET is_hidden = CASE WHEN is_hidden = 0 THEN 1 ELSE 0 END,
               updated_at = datetime('now')
           WHERE portfolio_id = ? AND symbol = ? AND market = ?""",
        (portfolio_id, symbol, market),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return {"found": False}
    # Return current state
    cursor = await db.execute(
        "SELECT is_hidden FROM portfolio_state WHERE portfolio_id = ? AND symbol = ? AND market = ?",
        (portfolio_id, symbol, market),
    )
    row = await cursor.fetchone()
    return {"found": True, "is_hidden": bool(row["is_hidden"])} if row else {"found": False}


async def upsert_portfolio_position(
    symbol: str, market: str, data: dict, portfolio_id: int = 1,
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO portfolio_state
           (portfolio_id, symbol, market, position_size, entry_date, entry_price, sector, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(portfolio_id, symbol, market) DO UPDATE SET
           position_size = excluded.position_size,
           entry_date = COALESCE(excluded.entry_date, portfolio_state.entry_date),
           entry_price = COALESCE(excluded.entry_price, portfolio_state.entry_price),
           sector = COALESCE(excluded.sector, portfolio_state.sector),
           updated_at = datetime('now')""",
        (portfolio_id, symbol, market, data.get("position_size", 0),
         data.get("entry_date"), data.get("entry_price"),
         data.get("sector")),
    )
    await db.commit()


async def clear_portfolio_positions(
    portfolio_id: int = 1, market: str | None = None,
) -> int:
    """Set position_size=0 for positions in a group (optionally filtered by market)."""
    db = await get_db()
    query = """UPDATE portfolio_state SET position_size = 0,
               entry_date = NULL, entry_price = NULL, sector = NULL,
               updated_at = datetime('now')
               WHERE portfolio_id = ? AND position_size > 0"""
    params: list = [portfolio_id]
    if market:
        query += " AND market = ?"
        params.append(market)
    cursor = await db.execute(query, params)
    await db.commit()
    return cursor.rowcount


# ── Position Exits (Phase H) ──


async def exit_position(
    symbol: str, market: str, exit_reason: str = "manual", portfolio_id: int = 1,
) -> dict:
    """Record a position exit and zero-out the position."""
    db = await get_db()
    # Get current position data with latest price via JOIN
    cursor = await db.execute(
        """SELECT ps.entry_price, ps.position_size, ps.entry_date,
                  lp.close AS exit_price
           FROM portfolio_state ps
           LEFT JOIN (
               SELECT ph.symbol, ph.market, ph.close
               FROM price_history ph
               INNER JOIN (
                   SELECT symbol, market, MAX(trade_date) AS max_date
                   FROM price_history GROUP BY symbol, market
               ) latest ON ph.symbol = latest.symbol
                       AND ph.market = latest.market
                       AND ph.trade_date = latest.max_date
           ) lp ON ps.symbol = lp.symbol AND ps.market = lp.market
           WHERE ps.portfolio_id = ? AND ps.symbol = ? AND ps.market = ?
           AND ps.position_size > 0""",
        (portfolio_id, symbol, market),
    )
    row = await cursor.fetchone()
    if not row:
        return {"status": "not_found"}
    r = dict(row)
    entry = r.get("entry_price") if r.get("entry_price") is not None else 0
    exit_p = r.get("exit_price") if r.get("exit_price") is not None else entry
    pnl = round((exit_p - entry) / entry * 100, 2) if entry > 0 else 0.0
    # Insert exit record
    await db.execute(
        """INSERT INTO position_exits
           (portfolio_id, symbol, market, entry_price, exit_price, position_size,
            entry_date, exit_reason, pnl_pct)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (portfolio_id, symbol, market, entry, exit_p, r.get("position_size"),
         r.get("entry_date"), exit_reason, pnl),
    )
    # Zero-out position
    await db.execute(
        """UPDATE portfolio_state SET position_size = 0, updated_at = datetime('now')
           WHERE portfolio_id = ? AND symbol = ? AND market = ?""",
        (portfolio_id, symbol, market),
    )
    await db.commit()
    return {"status": "exited", "symbol": symbol, "market": market,
            "exit_reason": exit_reason, "pnl_pct": pnl}


async def batch_exit_stop_loss(portfolio_id: int = 1, stop_pct: float = -7.0) -> int:
    """Exit all positions at or below the stop-loss threshold."""
    db = await get_db()
    # Use JOIN with latest price instead of correlated subquery per row
    cursor = await db.execute(
        """SELECT ps.symbol, ps.market, ps.entry_price, ps.position_size, ps.entry_date,
                  lp.close AS exit_price
           FROM portfolio_state ps
           LEFT JOIN (
               SELECT ph.symbol, ph.market, ph.close
               FROM price_history ph
               INNER JOIN (
                   SELECT symbol, market, MAX(trade_date) AS max_date
                   FROM price_history GROUP BY symbol, market
               ) latest ON ph.symbol = latest.symbol
                       AND ph.market = latest.market
                       AND ph.trade_date = latest.max_date
           ) lp ON ps.symbol = lp.symbol AND ps.market = lp.market
           WHERE ps.portfolio_id = ? AND ps.position_size > 0""",
        (portfolio_id,),
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    exited = 0
    for r in rows:
        entry = r.get("entry_price") if r.get("entry_price") is not None else 0
        exit_p = r.get("exit_price") if r.get("exit_price") is not None else entry
        if entry <= 0:
            continue
        pnl = (exit_p - entry) / entry * 100
        if pnl <= stop_pct:
            await db.execute(
                """INSERT INTO position_exits
                   (portfolio_id, symbol, market, entry_price, exit_price,
                    position_size, entry_date, exit_reason, pnl_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'stop_loss', ?)""",
                (portfolio_id, r["symbol"], r["market"], entry, exit_p,
                 r.get("position_size"), r.get("entry_date"), round(pnl, 2)),
            )
            await db.execute(
                """UPDATE portfolio_state SET position_size = 0, updated_at = datetime('now')
                   WHERE portfolio_id = ? AND symbol = ? AND market = ?""",
                (portfolio_id, r["symbol"], r["market"]),
            )
            exited += 1
    if exited > 0:
        await db.commit()
    return exited


async def get_exit_history(portfolio_id: int = 1, limit: int = 50) -> list[dict]:
    """Get recent position exit records."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT pe.*, w.name
           FROM position_exits pe
           LEFT JOIN watchlist w ON pe.symbol = w.symbol AND pe.market = w.market
           WHERE pe.portfolio_id = ?
           ORDER BY pe.created_at DESC LIMIT ?""",
        (portfolio_id, limit),
    )
    return [dict(r) for r in await cursor.fetchall()]


# ── Fundamental Data (Phase C) ──


async def upsert_fundamental_data(data: dict) -> None:
    db = await get_db()
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


async def upsert_weekly_indicators(rows: list[dict]) -> int:
    """Persist weekly indicator data."""
    if not rows:
        return 0
    db = await get_db()
    await db.executemany(
        """INSERT OR REPLACE INTO weekly_indicators
           (symbol, market, week_ending, rsi_14_weekly,
            ma_5_weekly, ma_20_weekly, macd_weekly, trend_direction)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (r["symbol"], r["market"], r["week_ending"],
             r.get("rsi_14_weekly"), r.get("ma_5_weekly"),
             r.get("ma_20_weekly"), r.get("macd_weekly"),
             r.get("trend_direction"))
            for r in rows
        ],
    )
    await db.commit()
    return len(rows)


async def get_latest_fundamental(symbol: str, market: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM fundamental_data
           WHERE symbol = ? AND market = ?
           ORDER BY trade_date DESC LIMIT 1""",
        (symbol, market),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


# ── Screening Candidates (Phase C) ──


async def update_screening_status(candidate_id: int, status: str) -> int:
    """Update screening candidate status (new/approved/rejected)."""
    db = await get_db()
    cursor = await db.execute(
        "UPDATE screening_candidates SET status = ? WHERE id = ?",
        (status, candidate_id),
    )
    await db.commit()
    return cursor.rowcount


async def insert_screening_candidate(data: dict) -> int:
    db = await get_db()
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


async def get_screening_candidates(
    market: str, status: str | None = None,
) -> list[dict]:
    db = await get_db()
    # Use correlated subqueries instead of full-table ROW_NUMBER scans
    # to leverage existing indexes on (symbol, market, trade_date)
    query = """
        SELECT sc.*,
               w.name,
               (SELECT ti2.rsi_14 FROM technical_indicators ti2
                WHERE ti2.symbol = sc.symbol AND ti2.market = sc.market
                ORDER BY ti2.trade_date DESC LIMIT 1) AS rsi,
               (SELECT ti3.volume_ratio FROM technical_indicators ti3
                WHERE ti3.symbol = sc.symbol AND ti3.market = sc.market
                ORDER BY ti3.trade_date DESC LIMIT 1) AS volume_ratio,
               (SELECT ph_cur.close FROM price_history ph_cur
                WHERE ph_cur.symbol = sc.symbol AND ph_cur.market = sc.market
                ORDER BY ph_cur.trade_date DESC LIMIT 1) AS current_price,
               (SELECT ph_prev.close FROM price_history ph_prev
                WHERE ph_prev.symbol = sc.symbol AND ph_prev.market = sc.market
                ORDER BY ph_prev.trade_date DESC LIMIT 1 OFFSET 1) AS prev_price
        FROM screening_candidates sc
        LEFT JOIN watchlist w ON sc.symbol = w.symbol AND sc.market = w.market
        WHERE sc.market = ?
    """
    params: list = [market]
    if status:
        query += " AND sc.status = ?"
        params.append(status)
    query += " ORDER BY sc.detected_date DESC LIMIT 100"
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        # Map screening fields to UI expectations
        d["reason"] = d.get("trigger_description") or d.get("trigger_type") or ""
        d["scan_date"] = d.get("detected_date")

        # Compute price_change from current_price and prev_price
        cur = d.get("current_price")
        prev = d.get("prev_price")
        if cur is not None and prev is not None and prev > 0:
            d["price_change"] = round((cur - prev) / prev * 100, 2)
        else:
            d["price_change"] = None

        # Compute composite conviction score (0-10) from available indicators
        _score = 0.0
        _factors = 0
        rsi = d.get("rsi")
        vol_ratio = d.get("volume_ratio")
        price_chg = d.get("price_change")
        trigger = d.get("trigger_type", "")
        if rsi is not None:
            # Lower RSI = more upside potential (inverted, 30→high score, 70→low)
            _score += max(0, min(10, (70 - rsi) / 4))
            _factors += 1
        if vol_ratio is not None:
            # Higher volume ratio = stronger conviction
            _score += max(0, min(10, vol_ratio * 2.5))
            _factors += 1
        if price_chg is not None:
            # Positive momentum contribution
            _score += max(0, min(10, price_chg * 0.8 + 3))
            _factors += 1
        # Trigger type bonus
        if trigger in ("volume_spike", "breakout"):
            _score += 2
            _factors += 1
        elif trigger == "new_high":
            _score += 1.5
            _factors += 1
        d["score"] = round(_score / max(_factors, 1), 1)
        results.append(d)
    return results


# ── Macro Intelligence Queries ──


async def get_macro_history(days: int = 30) -> list[dict]:
    """Get macro indicators for the past N days, chronological order."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM macro_indicators
           WHERE indicator_date >= date('now', ?)
           ORDER BY indicator_date ASC""",
        (f"-{days} days",),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_signal_stats_by_market() -> dict:
    """Get latest-date signal statistics grouped by market.

    Uses per-market max date to avoid cross-market date mismatch
    (e.g., KR pipeline runs at different time than US).
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT market,
                  COUNT(*) as total_count,
                  AVG(raw_score) as avg_score,
                  AVG(technical_score) as avg_technical,
                  AVG(macro_score) as avg_macro,
                  AVG(fund_flow_score) as avg_fund_flow,
                  SUM(CASE WHEN final_signal = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                  SUM(CASE WHEN final_signal = 'SELL' THEN 1 ELSE 0 END) as sell_count,
                  SUM(CASE WHEN final_signal = 'HOLD' THEN 1 ELSE 0 END) as hold_count
           FROM signals s
           WHERE signal_date = (
               SELECT MAX(s2.signal_date) FROM signals s2 WHERE s2.market = s.market
           )
           GROUP BY market"""
    )
    return {r["market"]: dict(r) for r in await cursor.fetchall()}


async def get_sector_fund_flow_kr(days: int = 5) -> list[dict]:
    """Get KR fund flow for recent N trading days (all symbols)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM fund_flow_kr
           WHERE trade_date >= date('now', ?)
           ORDER BY trade_date DESC, symbol
           LIMIT 5000""",
        (f"-{days} days",),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_us_fund_flow_recent(days: int = 5) -> list[dict]:
    """Compute US ETF proxy fund flow from price_history data.

    Uses SPY/QQQ/IWM/TLT daily price changes + volume ratios
    to derive a risk appetite score (equity up + bond down = risk-on).
    """
    db = await get_db()
    etf_symbols = ["SPY", "QQQ", "IWM", "TLT", "DIA"]
    placeholders = ",".join(["?" for _ in etf_symbols])
    # Fetch extra days for computing day-over-day changes
    cursor = await db.execute(
        f"""SELECT symbol, trade_date, close, volume
           FROM price_history
           WHERE symbol IN ({placeholders})
           AND trade_date >= date('now', ?)
           ORDER BY symbol, trade_date ASC""",
        (*etf_symbols, f"-{days + 10} days"),
    )
    rows = [dict(r) for r in await cursor.fetchall()]

    # Group by symbol
    by_symbol: dict[str, list[dict]] = {}
    for r in rows:
        by_symbol.setdefault(r["symbol"], []).append(r)

    # Compute daily returns per symbol per date
    flow_data: dict[str, dict] = {}
    for symbol, prices in by_symbol.items():
        for i in range(1, len(prices)):
            date = prices[i]["trade_date"]
            prev_close = prices[i - 1]["close"] if prices[i - 1]["close"] is not None else 0
            curr_close = prices[i]["close"] if prices[i]["close"] is not None else 0
            prev_vol = prices[i - 1]["volume"] if prices[i - 1]["volume"] is not None else 0
            curr_vol = prices[i]["volume"] if prices[i]["volume"] is not None else 0
            pct_change = ((curr_close - prev_close) / prev_close * 100) if prev_close > 0 else 0
            volume_ratio = curr_vol / prev_vol if prev_vol > 0 else 1.0

            if date not in flow_data:
                flow_data[date] = {}
            flow_data[date][symbol] = {
                "pct_change": round(pct_change, 2),
                "volume_ratio": round(volume_ratio, 2),
                "close": curr_close,
            }

    # Build results with risk appetite score
    results = []
    for date in sorted(flow_data.keys()):
        d = flow_data[date]
        spy = d.get("SPY", {})
        qqq = d.get("QQQ", {})
        iwm = d.get("IWM", {})
        tlt = d.get("TLT", {})

        # Risk-on proxy: equity ETFs up + bond down = risk on
        equity_flow = (
            spy.get("pct_change", 0) * 0.4
            + qqq.get("pct_change", 0) * 0.3
            + iwm.get("pct_change", 0) * 0.3
        )
        bond_flow = tlt.get("pct_change", 0)
        risk_appetite = round(equity_flow - bond_flow * 0.5, 2)

        results.append({
            "trade_date": date,
            "risk_appetite_score": risk_appetite,
            "spy_change": spy.get("pct_change", 0),
            "qqq_change": qqq.get("pct_change", 0),
            "iwm_change": iwm.get("pct_change", 0),
            "tlt_change": tlt.get("pct_change", 0),
            "spy_volume_ratio": spy.get("volume_ratio", 1.0),
        })

    # Return only the last N days
    if len(results) > days:
        results = results[-days:]
    return results


async def get_kr_daily_foreign_total(days: int = 30) -> list[dict]:
    """Get daily total foreign net buying across all KR symbols."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT trade_date,
                  SUM(foreign_net_buy) as total_foreign_net,
                  SUM(institution_net_buy) as total_institution_net,
                  SUM(individual_net_buy) as total_individual_net
           FROM fund_flow_kr
           WHERE trade_date >= date('now', ?)
           GROUP BY trade_date
           ORDER BY trade_date ASC""",
        (f"-{days} days",),
    )
    return [dict(r) for r in await cursor.fetchall()]


# ── Sentiment Data (Phase D) ──


async def upsert_sentiment_data(data: dict) -> None:
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO sentiment_data
           (indicator_date, fear_greed_index, put_call_ratio, vix_term_structure)
           VALUES (?, ?, ?, ?)""",
        (data["indicator_date"], data.get("fear_greed_index"),
         data.get("put_call_ratio"), data.get("vix_term_structure")),
    )
    await db.commit()


async def get_sentiment_history(days: int = 7) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM sentiment_data
           WHERE indicator_date >= date('now', ?)
           ORDER BY indicator_date DESC""",
        (f"-{days} days",),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_latest_sentiment() -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM sentiment_data ORDER BY indicator_date DESC LIMIT 1"
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


# ── US Fund Flow (Phase D) ──


async def insert_us_fund_flow(data: dict) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT OR REPLACE INTO us_fund_flow
           (symbol, trade_date, data_type, value, description, source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data["symbol"], data["trade_date"], data["data_type"],
         data.get("value"), data.get("description"), data.get("source")),
    )
    await db.commit()
    return cursor.rowcount


# ── News Data (Phase F) ──


async def insert_news_data(rows: list[dict]) -> int:
    """Store news analysis data."""
    if not rows:
        return 0
    db = await get_db()
    await db.executemany(
        """INSERT INTO news_data
           (run_id, symbol, market, trade_date, news_score,
            article_count, bullish_count, bearish_count, headlines_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (r["run_id"], r["symbol"], r["market"], r["trade_date"],
             r.get("news_score"), r.get("article_count"),
             r.get("bullish_count"), r.get("bearish_count"),
             r.get("headlines_json"))
            for r in rows
        ],
    )
    await db.commit()
    return len(rows)


async def get_latest_news(symbol: str, market: str) -> dict | None:
    """Get latest news data for a symbol."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM news_data
           WHERE symbol = ? AND market = ?
           ORDER BY trade_date DESC LIMIT 1""",
        (symbol, market),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


# ── Portfolio Scenarios (Phase E) ──


async def insert_portfolio_scenarios(scenarios: list[dict]) -> int:
    if not scenarios:
        return 0
    db = await get_db()
    await db.executemany(
        """INSERT INTO portfolio_scenarios
           (run_id, symbol, market, scenario_date, scenario_type,
            current_price, entry_price, pnl_pct,
            scenarios_json, scenario_rule, scenario_llm, target_prices_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (s["run_id"], s["symbol"], s["market"], s["scenario_date"],
             s["scenario_type"], s.get("current_price"), s.get("entry_price"),
             s.get("pnl_pct"), s.get("scenarios_json"),
             s.get("scenario_rule"), s.get("scenario_llm"),
             s.get("target_prices_json"))
            for s in scenarios
        ],
    )
    await db.commit()
    return len(scenarios)


async def get_latest_portfolio_scenarios(market: str | None = None) -> list[dict]:
    db = await get_db()
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


async def insert_llm_review(data: dict) -> int:
    db = await get_db()
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


# ── Alert Config (Phase F) ──

async def get_alert_config() -> list[dict]:
    """Get all alert configuration entries."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM alert_config ORDER BY key")
    return [dict(r) for r in await cursor.fetchall()]


async def upsert_alert_config(key: str, value: str, description: str | None = None) -> None:
    """Insert or update an alert config entry."""
    db = await get_db()
    await db.execute(
        """INSERT INTO alert_config (key, value, description, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET
           value = excluded.value,
           description = COALESCE(excluded.description, alert_config.description),
           updated_at = datetime('now')""",
        (key, value, description),
    )
    await db.commit()


async def get_alert_history(limit: int = 50) -> list[dict]:
    """Get recent alert history entries."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM alert_history ORDER BY fired_at DESC LIMIT ?", (limit,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def insert_alert_history(alert: dict) -> int:
    """Insert an alert history record."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO alert_history (alert_type, symbol, market, condition, message, sent_to)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (alert["alert_type"], alert.get("symbol"), alert.get("market"),
         alert["condition"], alert.get("message"), alert.get("sent_to", "discord")),
    )
    await db.commit()
    return cursor.lastrowid or 0


# ── Market Briefings (Phase G+) ──


async def get_market_briefings(limit: int = 10) -> list[dict]:
    """Get recent market briefings."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM market_briefings ORDER BY briefing_date DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    results = []
    for row in rows:
        r = dict(row)
        r["content"] = _safe_json_loads(r.get("content_json"), {})
        results.append(r)
    return results


async def get_market_briefing(briefing_date: str, market: str = "ALL") -> dict | None:
    """Get a specific market briefing by date."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM market_briefings WHERE briefing_date = ? AND market = ?",
        (briefing_date, market),
    )
    row = await cursor.fetchone()
    if row:
        r = dict(row)
        r["content"] = _safe_json_loads(r.get("content_json"), {})
        return r
    return None


async def upsert_market_briefing(briefing_date: str, market: str, content: dict, llm_summary: str | None = None) -> None:
    """Insert or update a market briefing."""
    db = await get_db()
    await db.execute(
        """INSERT INTO market_briefings (briefing_date, market, content_json, llm_summary)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(briefing_date, market) DO UPDATE SET
           content_json = excluded.content_json,
           llm_summary = COALESCE(excluded.llm_summary, market_briefings.llm_summary),
           created_at = datetime('now')""",
        (briefing_date, market, json.dumps(content, ensure_ascii=False), llm_summary),
    )
    await db.commit()


# ── Monthly Reports (Phase F) ──

async def get_monthly_reports(limit: int = 12) -> list[dict]:
    """Get recent monthly reports."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM monthly_reports ORDER BY report_month DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    results = []
    for row in rows:
        r = dict(row)
        r["content"] = _safe_json_loads(r.get("content_json"), {})
        results.append(r)
    return results


async def upsert_monthly_report(report_month: str, market: str, content: dict) -> None:
    """Insert or update a monthly report."""
    db = await get_db()
    await db.execute(
        """INSERT INTO monthly_reports (report_month, market, content_json)
           VALUES (?, ?, ?)
           ON CONFLICT(report_month, market) DO UPDATE SET
           content_json = excluded.content_json,
           created_at = datetime('now')""",
        (report_month, market, json.dumps(content, ensure_ascii=False)),
    )
    await db.commit()


# ── Runtime Config (Phase G+) ──


async def get_runtime_config() -> dict[str, str]:
    """Get all runtime config entries as a key-value dict."""
    db = await get_db()
    cursor = await db.execute("SELECT key, value FROM runtime_config ORDER BY key")
    rows = await cursor.fetchall()
    return {r["key"]: r["value"] for r in rows}


async def upsert_runtime_config(key: str, value: str) -> None:
    """Insert or update a runtime config entry."""
    db = await get_db()
    await db.execute(
        """INSERT INTO runtime_config (key, value, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET
           value = excluded.value,
           updated_at = datetime('now')""",
        (key, value),
    )
    await db.commit()


async def set_runtime_configs(updates: dict[str, str]) -> None:
    """Batch update runtime config entries."""
    if not updates:
        return
    db = await get_db()
    await db.executemany(
        """INSERT INTO runtime_config (key, value, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET
           value = excluded.value,
           updated_at = datetime('now')""",
        [(key, value) for key, value in updates.items()],
    )
    await db.commit()


# ── Users (Authentication) ──


async def count_users() -> int:
    """Count total users. Used to determine if setup is needed."""
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM users")
    row = await cursor.fetchone()
    return row[0] if row else 0


async def create_user(username: str, password_hash: str) -> int:
    """Create a new user. Returns the user ID."""
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def get_user_by_username(username: str) -> dict | None:
    """Get user by username. Returns dict or None."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_last_login(username: str) -> None:
    """Update user's last_login timestamp."""
    db = await get_db()
    await db.execute(
        "UPDATE users SET last_login = datetime('now') WHERE username = ?",
        (username,),
    )
    await db.commit()


async def update_user_password(username: str, new_password_hash: str) -> bool:
    """Update user's password hash. Returns True if updated."""
    db = await get_db()
    cursor = await db.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (new_password_hash, username),
    )
    await db.commit()
    return cursor.rowcount > 0


# ── Market Season / Investment Clock Support (Phase J) ──


async def get_etf_momentum() -> dict:
    """Get SPY 60-day return for market season growth proxy.

    Computes price change from ~60 trading days ago vs latest.
    Returns {"spy_return_60d": float | None}.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT close, trade_date FROM price_history
           WHERE symbol = 'SPY' AND market = 'US'
           ORDER BY trade_date DESC LIMIT 70"""
    )
    rows = await cursor.fetchall()
    if len(rows) < 30:
        return {"spy_return_60d": None}

    latest = rows[0]["close"]
    # Use the 60th row or last available
    older_idx = min(59, len(rows) - 1)
    older = rows[older_idx]["close"]
    if older and older > 0 and latest is not None:
        ret = (latest - older) / older
    else:
        ret = None
    return {"spy_return_60d": round(ret, 4) if ret is not None else None}


async def get_portfolio_season_summary() -> dict:
    """Get portfolio summary for strategy-match checks.

    Returns portfolio composition metrics for current season alignment.
    """
    db = await get_db()

    # Total positions and invested
    cursor = await db.execute(
        """SELECT market, sector, position_size, entry_price
           FROM portfolio_state
           WHERE portfolio_id = 1 AND is_hidden = 0 AND position_size > 0"""
    )
    positions = [dict(r) for r in await cursor.fetchall()]

    if not positions:
        return {
            "total_positions": 0,
            "total_invested": 0,
            "kr_pct": 0,
            "us_pct": 0,
            "tech_pct": 0,
        }

    total_invested = sum(p.get("position_size", 0) for p in positions)
    kr_invested = sum(
        p.get("position_size", 0) for p in positions if p.get("market") == "KR"
    )
    us_invested = sum(
        p.get("position_size", 0) for p in positions if p.get("market") == "US"
    )
    tech_sectors = {"Tech", "Semiconductor", "반도체", "인터넷"}
    tech_invested = sum(
        p.get("position_size", 0) for p in positions
        if p.get("sector") in tech_sectors
    )

    denom = max(total_invested, 1)
    return {
        "total_positions": len(positions),
        "total_invested": total_invested,
        "kr_pct": round(kr_invested / denom * 100, 1),
        "us_pct": round(us_invested / denom * 100, 1),
        "tech_pct": round(tech_invested / denom * 100, 1),
    }


async def get_signal_season_summary() -> dict:
    """Get latest signal buy/sell/hold counts for strategy-match.

    Returns {"buy_count": int, "sell_count": int, "hold_count": int}.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT final_signal, COUNT(*) as cnt
           FROM signals
           WHERE signal_date = (SELECT MAX(s2.signal_date) FROM signals s2 WHERE s2.market = signals.market)
           GROUP BY final_signal"""
    )
    rows = await cursor.fetchall()
    result = {"buy_count": 0, "sell_count": 0, "hold_count": 0}
    for r in rows:
        sig = (r["final_signal"] or "").upper()
        if sig == "BUY":
            result["buy_count"] = r["cnt"]
        elif sig == "SELL":
            result["sell_count"] = r["cnt"]
        else:
            result["hold_count"] = r["cnt"]
    return result


# ── Crisis Analysis Support (Phase K) ──


async def get_benchmark_prices(days: int = 200) -> dict[str, list[dict]]:
    """Get price history for benchmark symbols (KOSPI ETF 069500 + SPY).

    Returns {"KOSPI": [...], "SPY": [...]} with trade_date and close,
    sorted oldest→newest.
    """
    db = await get_db()
    result: dict[str, list[dict]] = {"KOSPI": [], "SPY": []}

    benchmarks = [("069500", "KR", "KOSPI"), ("SPY", "US", "SPY")]
    for symbol, market, key in benchmarks:
        cursor = await db.execute(
            """SELECT trade_date, close FROM price_history
               WHERE symbol = ? AND market = ?
               ORDER BY trade_date DESC LIMIT ?""",
            (symbol, market, days),
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        rows.reverse()  # oldest→newest
        result[key] = rows

    return result


async def get_symbol_returns(market: str, days: int = 20) -> dict[str, float]:
    """Compute N-day return % for all active symbols in a market.

    Returns {symbol: return_pct} where return_pct = (latest/oldest - 1) * 100.
    Uses a single batch query with ROW_NUMBER to avoid N+1 per-symbol queries.
    """
    db = await get_db()
    cursor = await db.execute(
        """WITH ranked AS (
               SELECT ph.symbol, ph.close,
                      ROW_NUMBER() OVER (PARTITION BY ph.symbol ORDER BY ph.trade_date DESC) AS rn
               FROM price_history ph
               INNER JOIN watchlist w ON ph.symbol = w.symbol AND ph.market = w.market
                   AND w.is_active = 1
               WHERE ph.market = ?
               AND ph.trade_date >= date('now', ?)
           )
           SELECT r1.symbol,
                  r1.close AS latest_close,
                  r2.close AS oldest_close
           FROM ranked r1
           INNER JOIN (
               SELECT symbol, MAX(rn) AS max_rn FROM ranked GROUP BY symbol
           ) mx ON r1.symbol = mx.symbol
           INNER JOIN ranked r2 ON r1.symbol = r2.symbol AND r2.rn = mx.max_rn
           WHERE r1.rn = 1 AND mx.max_rn >= 2""",
        (market, f"-{days + 10} days"),
    )
    rows = await cursor.fetchall()
    returns: dict[str, float] = {}
    for r in rows:
        latest = r["latest_close"]
        oldest = r["oldest_close"]
        if oldest and oldest > 0 and latest:
            ret = (latest - oldest) / oldest * 100
            returns[r["symbol"]] = round(ret, 4)
    return returns


async def get_fx_history(days: int = 200) -> list[dict]:
    """Get USD/KRW history from macro_indicators for MA computation.

    Returns list of {"indicator_date": str, "close": float} oldest→newest.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT indicator_date, usd_krw as close
           FROM macro_indicators
           WHERE usd_krw IS NOT NULL
           ORDER BY indicator_date DESC LIMIT ?""",
        (days,),
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    rows.reverse()
    return rows
