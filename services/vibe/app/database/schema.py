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
        explanation_rule TEXT,
        explanation_llm TEXT,
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
    # ── Backtest Runs ──
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        backtest_id TEXT NOT NULL UNIQUE,
        market TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        config_snapshot TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        total_trades INTEGER DEFAULT 0,
        hit_rate REAL,
        avg_return REAL,
        sharpe_ratio REAL,
        max_drawdown REAL,
        profit_factor REAL,
        win_loss_ratio REAL,
        total_return REAL,
        results_json TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Backtest Trades ──
    """
    CREATE TABLE IF NOT EXISTS backtest_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        backtest_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        entry_date TEXT NOT NULL,
        entry_price REAL NOT NULL,
        entry_signal TEXT NOT NULL,
        entry_score REAL NOT NULL,
        exit_date TEXT,
        exit_price REAL,
        exit_reason TEXT,
        return_pct REAL,
        holding_days INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Signal Performance Tracking ──
    """
    CREATE TABLE IF NOT EXISTS signal_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id INTEGER NOT NULL UNIQUE,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        signal_type TEXT NOT NULL,
        signal_score REAL NOT NULL,
        entry_price REAL NOT NULL,
        price_t1 REAL,
        price_t5 REAL,
        price_t20 REAL,
        return_t1 REAL,
        return_t5 REAL,
        return_t20 REAL,
        is_correct_t5 INTEGER,
        is_correct_t20 INTEGER,
        tracked_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Symbol Metadata (Phase B) ──
    """
    CREATE TABLE IF NOT EXISTS symbol_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        sector TEXT,
        industry TEXT,
        market_cap REAL,
        next_earnings_date TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, market)
    )
    """,
    # ── Event Calendar (Phase B) ──
    """
    CREATE TABLE IF NOT EXISTS event_calendar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_date TEXT NOT NULL,
        event_type TEXT NOT NULL,
        market TEXT,
        symbol TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL,
        impact_level TEXT NOT NULL DEFAULT 'medium',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(event_date, event_type, symbol)
    )
    """,
    # ── Portfolio State (Phase B) ──
    """
    CREATE TABLE IF NOT EXISTS portfolio_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        position_size REAL NOT NULL DEFAULT 0,
        entry_date TEXT,
        entry_price REAL,
        sector TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, market)
    )
    """,
    # ── Fundamental Data (Phase C) ──
    """
    CREATE TABLE IF NOT EXISTS fundamental_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        per REAL,
        pbr REAL,
        eps REAL,
        roe REAL,
        operating_margin REAL,
        div_yield REAL,
        market_cap REAL,
        fundamental_score REAL,
        value_score REAL,
        quality_score REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, market, trade_date)
    )
    """,
    # ── Weekly Indicators (Phase C) ──
    """
    CREATE TABLE IF NOT EXISTS weekly_indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        week_ending TEXT NOT NULL,
        rsi_14_weekly REAL,
        ma_5_weekly REAL,
        ma_20_weekly REAL,
        macd_weekly REAL,
        trend_direction TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, market, week_ending)
    )
    """,
    # ── Screening Candidates (Phase C) ──
    """
    CREATE TABLE IF NOT EXISTS screening_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        detected_date TEXT NOT NULL,
        trigger_type TEXT NOT NULL,
        trigger_value REAL,
        trigger_description TEXT,
        status TEXT NOT NULL DEFAULT 'new',
        added_to_watchlist INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Sentiment Data (Phase D) ──
    """
    CREATE TABLE IF NOT EXISTS sentiment_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator_date TEXT NOT NULL,
        fear_greed_index INTEGER,
        put_call_ratio REAL,
        vix_term_structure TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(indicator_date)
    )
    """,
    # ── US Fund Flow (Phase D) ──
    """
    CREATE TABLE IF NOT EXISTS us_fund_flow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        data_type TEXT NOT NULL,
        value REAL,
        description TEXT,
        source TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, trade_date, data_type)
    )
    """,
    # ── Short Interest (Phase D) ──
    """
    CREATE TABLE IF NOT EXISTS short_interest (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL DEFAULT 'US',
        report_date TEXT NOT NULL,
        short_interest_shares INTEGER,
        short_ratio REAL,
        short_pct_float REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(symbol, market, report_date)
    )
    """,
    # ── Portfolio Scenarios (Phase E) ──
    """
    CREATE TABLE IF NOT EXISTS portfolio_scenarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        scenario_date TEXT NOT NULL,
        scenario_type TEXT NOT NULL,
        current_price REAL,
        entry_price REAL,
        pnl_pct REAL,
        scenarios_json TEXT,
        scenario_rule TEXT,
        scenario_llm TEXT,
        target_prices_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── News Data (Phase F) ──
    """
    CREATE TABLE IF NOT EXISTS news_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        news_score REAL,
        article_count INTEGER DEFAULT 0,
        bullish_count INTEGER DEFAULT 0,
        bearish_count INTEGER DEFAULT 0,
        headlines_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── LLM Reviews (Phase D) ──
    """
    CREATE TABLE IF NOT EXISTS llm_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        review_date TEXT NOT NULL,
        input_context TEXT,
        llm_response TEXT,
        model_used TEXT,
        risk_flags TEXT,
        confidence_adjustment REAL,
        signal_override TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Alert Config (Phase F) ──
    """
    CREATE TABLE IF NOT EXISTS alert_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Alert History (Phase F) ──
    """
    CREATE TABLE IF NOT EXISTS alert_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        symbol TEXT,
        market TEXT,
        condition TEXT NOT NULL,
        message TEXT,
        fired_at TEXT NOT NULL DEFAULT (datetime('now')),
        sent_to TEXT DEFAULT 'discord'
    )
    """,
    # ── Monthly Reports (Phase F) ──
    """
    CREATE TABLE IF NOT EXISTS monthly_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_month TEXT NOT NULL,
        market TEXT NOT NULL DEFAULT 'ALL',
        content_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(report_month, market)
    )
    """,
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_price_history_lookup ON price_history(symbol, market, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_technical_lookup ON technical_indicators(symbol, market, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(signal_date, market)",
    "CREATE INDEX IF NOT EXISTS idx_fund_flow_lookup ON fund_flow_kr(symbol, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status, started_at)",
    "CREATE INDEX IF NOT EXISTS idx_backtest_trades_lookup ON backtest_trades(backtest_id, symbol)",
    "CREATE INDEX IF NOT EXISTS idx_signal_performance_lookup ON signal_performance(symbol, market, signal_date)",
    "CREATE INDEX IF NOT EXISTS idx_signal_performance_tracking ON signal_performance(return_t20)",
    "CREATE INDEX IF NOT EXISTS idx_event_calendar_lookup ON event_calendar(event_date, market)",
    "CREATE INDEX IF NOT EXISTS idx_symbol_metadata_lookup ON symbol_metadata(symbol, market)",
    "CREATE INDEX IF NOT EXISTS idx_fundamental_lookup ON fundamental_data(symbol, market, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_weekly_indicators_lookup ON weekly_indicators(symbol, market, week_ending)",
    "CREATE INDEX IF NOT EXISTS idx_screening_candidates_lookup ON screening_candidates(market, status, detected_date)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_scenarios_lookup ON portfolio_scenarios(run_id, market, scenario_type)",
    "CREATE INDEX IF NOT EXISTS idx_news_data_lookup ON news_data(symbol, market, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_signals_run_id ON signals(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_watchlist_active_market ON watchlist(market, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_state_active ON portfolio_state(market, position_size)",
    "CREATE INDEX IF NOT EXISTS idx_alert_history_fired ON alert_history(fired_at)",
    "CREATE INDEX IF NOT EXISTS idx_alert_config_key ON alert_config(key)",
    "CREATE INDEX IF NOT EXISTS idx_monthly_reports_lookup ON monthly_reports(report_month, market)",
]


async def init_db() -> None:
    """Create all tables and indexes if they don't exist."""
    db = await get_db()
    for ddl in TABLES:
        await db.execute(ddl)
    for idx in INDEXES:
        await db.execute(idx)
    await db.commit()
