import aiosqlite

from app.database.connection import get_db

TABLES = [
    # ── Watchlist ──
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL,
        market TEXT NOT NULL,
        asset_type TEXT NOT NULL DEFAULT 'stock',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, market)
    )
    """,
    # ── Price History ──
    """
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL NOT NULL,
        volume INTEGER,
        adjusted_close REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, market, trade_date)
    )
    """,
    # ── Technical Indicators ──
    """
    CREATE TABLE IF NOT EXISTS technical_indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        rsi_14 REAL,
        ma_5 REAL,
        ma_20 REAL,
        ma_60 REAL,
        ma_120 REAL,
        macd REAL,
        macd_signal REAL,
        macd_histogram REAL,
        bollinger_upper REAL,
        bollinger_middle REAL,
        bollinger_lower REAL,
        disparity_20 REAL,
        volume_ratio REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, market, trade_date)
    )
    """,
    # ── Macro Indicators ──
    """
    CREATE TABLE IF NOT EXISTS macro_indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator_date TEXT NOT NULL,
        us_10y_yield REAL,
        us_2y_yield REAL,
        us_yield_spread REAL,
        fed_funds_rate REAL,
        dxy_index REAL,
        vix REAL,
        fear_greed_index REAL,
        kr_base_rate REAL,
        usd_krw REAL,
        wti_crude REAL,
        gold_price REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(indicator_date)
    )
    """,
    # ── Fund Flow (KR only) ──
    """
    CREATE TABLE IF NOT EXISTS fund_flow_kr (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        foreign_net_buy REAL,
        institution_net_buy REAL,
        individual_net_buy REAL,
        pension_net_buy REAL,
        foreign_holding_ratio REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, trade_date)
    )
    """,
    # ── Pipeline Runs ──
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL UNIQUE,
        run_type TEXT NOT NULL DEFAULT 'scheduled',
        market TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        started_at TEXT NOT NULL,
        completed_at TEXT,
        stages_completed TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Signals ──
    """
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        raw_signal TEXT NOT NULL,
        raw_score REAL NOT NULL,
        hard_limit_triggered INTEGER NOT NULL DEFAULT 0,
        hard_limit_reason TEXT,
        final_signal TEXT NOT NULL,
        confidence REAL,
        red_team_warning TEXT,
        rsi_value REAL,
        disparity_value REAL,
        macro_score REAL,
        technical_score REAL,
        fund_flow_score REAL,
        rationale TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(run_id, symbol, market)
    )
    """,
    # ── Dashboard Snapshots ──
    """
    CREATE TABLE IF NOT EXISTS dashboard_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        market TEXT NOT NULL,
        content_json TEXT NOT NULL,
        discord_sent INTEGER NOT NULL DEFAULT 0,
        discord_sent_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_price_history_lookup ON price_history(symbol, market, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_technical_lookup ON technical_indicators(symbol, market, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(signal_date, market)",
    "CREATE INDEX IF NOT EXISTS idx_fund_flow_lookup ON fund_flow_kr(symbol, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status, started_at)",
]


async def init_db() -> None:
    """Create all tables and indexes if they don't exist."""
    db = await get_db()
    try:
        for ddl in TABLES:
            await db.execute(ddl)
        for idx in INDEXES:
            await db.execute(idx)
        await db.commit()
    finally:
        await db.close()
