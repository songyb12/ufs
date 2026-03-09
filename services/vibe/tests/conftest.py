"""
Shared test fixtures for API integration tests.

Provides:
- In-memory SQLite database (isolated per test session)
- FastAPI TestClient via httpx AsyncClient
- Sample data seeders for common test scenarios
"""

import asyncio
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import set_db_path, get_db, close_db
from app.database.schema import init_db


# ── Fixtures ──


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Initialize in-memory SQLite database with full schema.

    Shared across all tests in the session for speed.
    Each test that mutates data should clean up after itself.
    """
    set_db_path(":memory:")
    await init_db()
    yield
    await close_db()


@pytest_asyncio.fixture(scope="session")
async def client(setup_db):
    """Async HTTP client bound to a minimal FastAPI app with all routers.

    Does NOT use the full lifespan (no scheduler, no collector registry,
    no watchlist seeding) — only the routers and DB.
    """
    import httpx
    from fastapi import FastAPI
    from app.routers import (
        academy, action_plan, alerts, auth, backtest, briefing, dashboard,
        data, guru, llm_settings, macro_intel, notification_settings,
        pipeline, portfolio, portfolio_import, risk, screening, sentiment,
        signals, strategy_settings, watchlist,
    )

    test_app = FastAPI()

    # Register all routers (same as main.py)
    test_app.include_router(auth.router)
    test_app.include_router(watchlist.router)
    test_app.include_router(pipeline.router)
    test_app.include_router(signals.router)
    test_app.include_router(dashboard.router)
    test_app.include_router(backtest.router)
    test_app.include_router(risk.router)
    test_app.include_router(screening.router)
    test_app.include_router(sentiment.router)
    test_app.include_router(portfolio.router)
    test_app.include_router(portfolio_import.router)
    test_app.include_router(alerts.router)
    test_app.include_router(briefing.router)
    test_app.include_router(llm_settings.router)
    test_app.include_router(data.router)
    test_app.include_router(macro_intel.router)
    test_app.include_router(guru.router)
    test_app.include_router(action_plan.router)
    test_app.include_router(academy.router)
    test_app.include_router(notification_settings.router)
    test_app.include_router(strategy_settings.router)

    # Health endpoint (simplified)
    @test_app.get("/health")
    async def health():
        return {"status": "healthy", "service": "vibe-test"}

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Data Seeders ──


async def seed_watchlist_items():
    """Insert a minimal watchlist for testing."""
    db = await get_db()
    items = [
        ("005930", "삼성전자", "KR", "stock"),
        ("000660", "SK하이닉스", "KR", "stock"),
        ("AAPL", "Apple Inc", "US", "stock"),
        ("MSFT", "Microsoft Corp", "US", "stock"),
    ]
    for symbol, name, market, asset_type in items:
        await db.execute(
            """INSERT OR IGNORE INTO watchlist (symbol, name, market, asset_type, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            (symbol, name, market, asset_type),
        )
    await db.commit()


async def seed_portfolio_positions(portfolio_id: int = 1):
    """Insert sample portfolio positions with price data for P&L testing."""
    db = await get_db()

    # Ensure default portfolio group exists
    await db.execute(
        """INSERT OR IGNORE INTO portfolio_groups (id, name, description, is_default)
           VALUES (?, '테스트 포트폴리오', 'Test portfolio', 1)""",
        (portfolio_id,),
    )

    # Portfolio positions
    positions = [
        (portfolio_id, "005930", "KR", 5_000_000, "2025-01-10", 56000),
        (portfolio_id, "AAPL", "US", 3_000, "2025-02-01", 230),
    ]
    for pid, sym, mkt, size, entry_date, entry_price in positions:
        await db.execute(
            """INSERT OR REPLACE INTO portfolio_state
               (portfolio_id, symbol, market, position_size, entry_date, entry_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pid, sym, mkt, size, entry_date, entry_price),
        )

    # Latest price data (for P&L calculation)
    prices = [
        ("005930", "KR", "2025-06-01", 60000),  # +7.14%
        ("AAPL", "US", "2025-06-01", 250),       # +8.70%
    ]
    for sym, mkt, date, close in prices:
        await db.execute(
            """INSERT OR REPLACE INTO price_history
               (symbol, market, trade_date, close, open, high, low, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sym, mkt, date, close, close, close, close, 1000000),
        )

    await db.commit()


async def seed_signals():
    """Insert sample signals for testing."""
    db = await get_db()
    signals_data = [
        ("run-001", "005930", "KR", "2025-06-01", "BUY", 2.5, "BUY", 0, 35.0, 2.0, 1.8, 1.5, 0.8),
        ("run-001", "000660", "KR", "2025-06-01", "HOLD", 0.3, "HOLD", 0, 55.0, 0.5, 0.2, 0.3, 0.1),
        ("run-001", "AAPL", "US", "2025-06-01", "BUY", 1.8, "BUY", 0, 40.0, 1.5, 1.0, 1.2, 0.5),
        ("run-001", "MSFT", "US", "2025-06-01", "SELL", -1.5, "SELL", 1, 70.0, -1.0, -0.5, -0.8, 0.0),
    ]
    for row in signals_data:
        await db.execute(
            """INSERT OR IGNORE INTO signals
               (run_id, symbol, market, signal_date, raw_signal, raw_score,
                final_signal, hard_limit_triggered, rsi_value,
                technical_score, macro_score, fund_flow_score, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            row,
        )
    await db.commit()


async def cleanup_all():
    """Remove all test data from key tables."""
    db = await get_db()
    for table in [
        "portfolio_state", "portfolio_groups", "position_exits",
        "price_history", "signals", "watchlist",
        "alert_config", "alert_history", "screening_candidates",
        "runtime_config",
    ]:
        await db.execute(f"DELETE FROM {table}")  # noqa: S608 — test-only
    await db.commit()
