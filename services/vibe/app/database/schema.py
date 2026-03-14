import logging

import aiosqlite

from app.database.connection import get_db

# Schema version — increment when adding new migrations
SCHEMA_VERSION = 7  # v1: initial, v2: portfolio_groups, v3: is_hidden, v4: copper_price, v5: signal_dedup, v6: users, v7: soxl_backtest

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
        copper_price REAL,
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
        UNIQUE(symbol, market, signal_date)
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
    # ── Portfolio Groups (Phase G) ──
    """
    CREATE TABLE IF NOT EXISTS portfolio_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        is_default INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Portfolio State (Phase B, updated Phase G+) ──
    """
    CREATE TABLE IF NOT EXISTS portfolio_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id INTEGER NOT NULL DEFAULT 1,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        position_size REAL NOT NULL DEFAULT 0,
        entry_date TEXT,
        entry_price REAL,
        sector TEXT,
        is_hidden INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(portfolio_id, symbol, market),
        FOREIGN KEY (portfolio_id) REFERENCES portfolio_groups(id)
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
    # ── Market Briefings (Phase G+) ──
    """
    CREATE TABLE IF NOT EXISTS market_briefings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        briefing_date TEXT NOT NULL,
        market TEXT NOT NULL DEFAULT 'ALL',
        content_json TEXT NOT NULL,
        llm_summary TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(briefing_date, market)
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
    # ── Users (Authentication) ──
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_login TEXT
    )
    """,
    # ── SOXL Price Alerts (Real-time) ──
    """
    CREATE TABLE IF NOT EXISTS soxl_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        threshold REAL NOT NULL,
        label TEXT,
        triggered_at TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    # ── Runtime Config (Phase G+) ──
    """
    CREATE TABLE IF NOT EXISTS runtime_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Position Exits (Phase H) ──
    """
    CREATE TABLE IF NOT EXISTS position_exits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id INTEGER NOT NULL DEFAULT 1,
        symbol TEXT NOT NULL,
        market TEXT NOT NULL,
        entry_price REAL,
        exit_price REAL,
        position_size REAL,
        entry_date TEXT,
        exit_date TEXT NOT NULL DEFAULT (date('now')),
        exit_reason TEXT NOT NULL DEFAULT 'manual',
        pnl_pct REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Forex History (Carry Trade / FX Map) ──
    """
    CREATE TABLE IF NOT EXISTS forex_history (
        pair TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        close_price REAL NOT NULL,
        PRIMARY KEY (pair, trade_date)
    )
    """,
    # ── Interest Rates (Central Bank Rates) ──
    """
    CREATE TABLE IF NOT EXISTS interest_rates (
        currency TEXT NOT NULL PRIMARY KEY,
        rate REAL NOT NULL,
        central_bank TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── Geopolitical Events ──
    """
    CREATE TABLE IF NOT EXISTS geopolitical_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL DEFAULT 'iran-us-2026',
        event_date TEXT NOT NULL,
        event_text TEXT NOT NULL,
        detail TEXT,
        impact TEXT DEFAULT 'neutral',
        category TEXT DEFAULT 'timeline',
        data_json TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """,
    # ── Weekly Reports ──
    """
    CREATE TABLE IF NOT EXISTS weekly_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start TEXT NOT NULL,
        week_end TEXT NOT NULL,
        market TEXT DEFAULT 'ALL',
        report_json TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(week_start, market)
    )
    """,
    # ── SOXL Backtest Runs ──
    """
    CREATE TABLE IF NOT EXISTS soxl_backtest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        backtest_id TEXT NOT NULL UNIQUE,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        mode TEXT NOT NULL,
        params_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        total_trades INTEGER DEFAULT 0,
        hit_rate REAL,
        avg_return REAL,
        sharpe_ratio REAL,
        max_drawdown REAL,
        profit_factor REAL,
        total_return REAL,
        leverage_decay_total REAL,
        equity_curve_json TEXT,
        results_json TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # ── SOXL Backtest Trades ──
    """
    CREATE TABLE IF NOT EXISTS soxl_backtest_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        backtest_id TEXT NOT NULL,
        entry_date TEXT NOT NULL,
        entry_price REAL NOT NULL,
        entry_signal TEXT NOT NULL,
        entry_score REAL,
        entry_rsi REAL,
        entry_vix REAL,
        entry_macro_score REAL,
        entry_geo_score REAL,
        exit_date TEXT,
        exit_price REAL,
        exit_reason TEXT,
        return_pct REAL,
        return_pct_with_decay REAL,
        holding_days INTEGER,
        position_size_mult REAL,
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
    "CREATE INDEX IF NOT EXISTS idx_portfolio_state_active ON portfolio_state(portfolio_id, market, position_size)",
    "CREATE INDEX IF NOT EXISTS idx_alert_history_fired ON alert_history(fired_at)",
    "CREATE INDEX IF NOT EXISTS idx_alert_config_key ON alert_config(key)",
    "CREATE INDEX IF NOT EXISTS idx_monthly_reports_lookup ON monthly_reports(report_month, market)",
    "CREATE INDEX IF NOT EXISTS idx_market_briefings_lookup ON market_briefings(briefing_date, market)",
    "CREATE INDEX IF NOT EXISTS idx_runtime_config_key ON runtime_config(key)",
    "CREATE INDEX IF NOT EXISTS idx_position_exits_lookup ON position_exits(portfolio_id, market, exit_date)",
    "CREATE INDEX IF NOT EXISTS idx_macro_indicators_date ON macro_indicators(indicator_date)",
    "CREATE INDEX IF NOT EXISTS idx_sentiment_data_date ON sentiment_data(indicator_date)",
    "CREATE INDEX IF NOT EXISTS idx_us_fund_flow_lookup ON us_fund_flow(symbol, trade_date, data_type)",
    "CREATE INDEX IF NOT EXISTS idx_llm_reviews_lookup ON llm_reviews(run_id, symbol, market)",
    "CREATE INDEX IF NOT EXISTS idx_dashboard_snapshots_lookup ON dashboard_snapshots(market, snapshot_date)",
    "CREATE INDEX IF NOT EXISTS idx_short_interest_lookup ON short_interest(symbol, market, report_date)",
    "CREATE INDEX IF NOT EXISTS idx_news_data_run ON news_data(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_scenarios_run ON portfolio_scenarios(market, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_forex_history_lookup ON forex_history(pair, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_soxl_bt_runs ON soxl_backtest_runs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_soxl_bt_trades ON soxl_backtest_trades(backtest_id)",
]


async def init_db() -> None:
    """Create all tables and indexes if they don't exist."""
    _logger = logging.getLogger("vibe.schema")
    db = await get_db()

    # Schema version tracking table
    await db.execute(
        """CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )

    for ddl in TABLES:
        await db.execute(ddl)
    for idx in INDEXES:
        await db.execute(idx)
    await db.commit()

    # ── Migrations (ordered) ──
    await _migrate_portfolio_groups(db)   # v2
    await _migrate_is_hidden(db)          # v3
    await _migrate_copper_price(db)       # v4
    await _migrate_signal_dedup(db)       # v5

    # Record current schema version
    await db.execute(
        """INSERT INTO schema_version (id, version, updated_at)
           VALUES (1, ?, datetime('now'))
           ON CONFLICT(id) DO UPDATE SET version = excluded.version, updated_at = datetime('now')""",
        (SCHEMA_VERSION,),
    )
    await db.commit()
    _logger.info("Schema initialized (version=%d, tables=%d, indexes=%d)",
                 SCHEMA_VERSION, len(TABLES), len(INDEXES))


async def _migrate_portfolio_groups(db) -> None:
    """Add portfolio_id column to legacy portfolio_state if needed."""
    import logging
    logger = logging.getLogger("vibe.schema.migrate")

    # Ensure default group exists
    c = await db.execute("SELECT COUNT(*) FROM portfolio_groups")
    if (await c.fetchone())[0] == 0:
        await db.execute(
            """INSERT INTO portfolio_groups (id, name, description, is_default)
               VALUES (1, '기본 포트폴리오', '기본 포트폴리오 그룹', 1)"""
        )
        logger.info("Created default portfolio group (id=1)")

    # Check if portfolio_state has portfolio_id column
    c = await db.execute("PRAGMA table_info(portfolio_state)")
    columns = [row[1] for row in await c.fetchall()]
    if "portfolio_id" not in columns:
        # Legacy table — needs migration
        logger.info("Migrating portfolio_state: adding portfolio_id column")
        await db.execute(
            """CREATE TABLE portfolio_state_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL DEFAULT 1,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                position_size REAL NOT NULL DEFAULT 0,
                entry_date TEXT,
                entry_price REAL,
                sector TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(portfolio_id, symbol, market),
                FOREIGN KEY (portfolio_id) REFERENCES portfolio_groups(id)
            )"""
        )
        await db.execute(
            """INSERT INTO portfolio_state_new
               (id, portfolio_id, symbol, market, position_size,
                entry_date, entry_price, sector, updated_at)
               SELECT id, 1, symbol, market, position_size,
                      entry_date, entry_price, sector, updated_at
               FROM portfolio_state"""
        )
        await db.execute("DROP TABLE portfolio_state")
        await db.execute("ALTER TABLE portfolio_state_new RENAME TO portfolio_state")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_portfolio_state_active "
            "ON portfolio_state(portfolio_id, market, position_size)"
        )
        logger.info("portfolio_state migration complete")
    await db.commit()


async def _migrate_is_hidden(db) -> None:
    """Add is_hidden column to portfolio_state if missing."""
    import logging
    logger = logging.getLogger("vibe.schema.migrate")

    c = await db.execute("PRAGMA table_info(portfolio_state)")
    columns = [row[1] for row in await c.fetchall()]
    if "is_hidden" not in columns:
        logger.info("Migrating portfolio_state: adding is_hidden column")
        await db.execute(
            "ALTER TABLE portfolio_state ADD COLUMN is_hidden INTEGER NOT NULL DEFAULT 0"
        )
        await db.commit()
        logger.info("is_hidden column added")


async def _migrate_copper_price(db) -> None:
    """Add copper_price column to macro_indicators if missing."""
    import logging
    logger = logging.getLogger("vibe.schema.migrate")

    c = await db.execute("PRAGMA table_info(macro_indicators)")
    columns = [row[1] for row in await c.fetchall()]
    if "copper_price" not in columns:
        logger.info("Migrating macro_indicators: adding copper_price column")
        await db.execute(
            "ALTER TABLE macro_indicators ADD COLUMN copper_price REAL"
        )
        await db.commit()
        logger.info("copper_price column added")


async def _migrate_signal_dedup(db) -> None:
    """Fix signals UNIQUE constraint: (run_id, symbol, market) -> (symbol, market, signal_date).
    Remove duplicate rows keeping only the latest run_id per (symbol, market, signal_date).
    """
    import logging
    logger = logging.getLogger("vibe.schema.migrate")

    # Check current UNIQUE constraint by inspecting CREATE TABLE SQL
    c = await db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='signals'")
    row = await c.fetchone()
    if not row:
        return  # signals table doesn't exist yet (will be created fresh)

    create_sql = row[0] or ""
    if "UNIQUE(symbol, market, signal_date)" in create_sql:
        return  # Already migrated

    if "UNIQUE(run_id, symbol, market)" not in create_sql:
        return  # Unknown schema state, skip

    logger.info("Migrating signals: changing UNIQUE constraint to (symbol, market, signal_date)")

    # Step 1: Create new table with correct constraint
    await db.execute("""
        CREATE TABLE signals_new (
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
            UNIQUE(symbol, market, signal_date)
        )
    """)

    # Step 2: Copy data, keeping only the latest run per (symbol, market, signal_date)
    await db.execute("""
        INSERT INTO signals_new
            (run_id, symbol, market, signal_date, raw_signal, raw_score,
             hard_limit_triggered, hard_limit_reason, final_signal, confidence,
             red_team_warning, rsi_value, disparity_value, macro_score,
             technical_score, fund_flow_score, rationale, explanation_rule,
             explanation_llm, created_at)
        SELECT run_id, symbol, market, signal_date, raw_signal, raw_score,
               hard_limit_triggered, hard_limit_reason, final_signal, confidence,
               red_team_warning, rsi_value, disparity_value, macro_score,
               technical_score, fund_flow_score, rationale, explanation_rule,
               explanation_llm, created_at
        FROM signals
        WHERE id IN (
            SELECT MAX(id)
            FROM signals
            GROUP BY symbol, market, signal_date
        )
    """)

    # Step 3: Count removed duplicates
    c_old = await db.execute("SELECT COUNT(*) FROM signals")
    old_count = (await c_old.fetchone())[0]
    c_new = await db.execute("SELECT COUNT(*) FROM signals_new")
    new_count = (await c_new.fetchone())[0]
    removed = old_count - new_count

    # Step 4: Swap tables
    await db.execute("DROP TABLE signals")
    await db.execute("ALTER TABLE signals_new RENAME TO signals")

    # Step 5: Recreate indexes
    await db.execute("CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(signal_date, market)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_signals_run_id ON signals(run_id)")

    await db.commit()
    logger.info("Signal dedup migration complete: %d rows kept, %d duplicates removed", new_count, removed)
