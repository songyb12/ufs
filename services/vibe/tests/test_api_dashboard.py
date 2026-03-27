"""
API tests for dashboard endpoints.

Covers:
- GET /health
- GET /dashboard/summary
- GET /dashboard/data-status
- GET /dashboard/prices/{symbol}
- GET /dashboard/signals/history
"""

import pytest
import pytest_asyncio

from tests.conftest import (
    cleanup_all,
    seed_portfolio_positions,
    seed_signals,
    seed_watchlist_items,
)


@pytest_asyncio.fixture(autouse=True)
async def _seed_data():
    """Seed data before each test, clean up after."""
    await seed_watchlist_items()
    await seed_portfolio_positions()
    await seed_signals()
    yield
    await cleanup_all()


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestDashboardSummary:
    @pytest.mark.asyncio
    async def test_summary_returns_signal_counts(self, client):
        resp = await client.get("/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()

        # Signal breakdown
        assert "signals" in data
        sigs = data["signals"]
        assert sigs["BUY"] == 2   # 005930 + AAPL
        assert sigs["SELL"] == 1  # MSFT
        assert sigs["HOLD"] == 1  # 000660

    @pytest.mark.asyncio
    async def test_summary_returns_hard_limit_count(self, client):
        resp = await client.get("/dashboard/summary")
        data = resp.json()
        assert data["hard_limit_count"] == 1  # MSFT

    @pytest.mark.asyncio
    async def test_summary_portfolio_pnl(self, client):
        resp = await client.get("/dashboard/summary")
        data = resp.json()

        portfolio = data["portfolio"]
        assert portfolio["holdings_count"] == 2  # 005930 + AAPL
        # Check P&L is positive (prices went up in seed data)
        assert portfolio["total_pnl_pct"] > 0

        # Individual positions
        positions = portfolio["positions"]
        samsung = next(p for p in positions if p["symbol"] == "005930")
        assert samsung["pnl_pct"] == pytest.approx(7.14, abs=0.1)

        apple = next(p for p in positions if p["symbol"] == "AAPL")
        assert apple["pnl_pct"] == pytest.approx(8.70, abs=0.1)

    @pytest.mark.asyncio
    async def test_summary_data_counts(self, client):
        resp = await client.get("/dashboard/summary")
        data = resp.json()

        assert data["data"]["watchlist"] == 4      # 4 seeded items
        assert data["data"]["signals_total"] == 4   # 4 seeded signals
        assert data["data"]["prices"] >= 2          # 2 price records


class TestDataStatus:
    @pytest.mark.asyncio
    async def test_data_status_returns_tables(self, client):
        resp = await client.get("/dashboard/data-status")
        assert resp.status_code == 200
        data = resp.json()

        tables = data["tables"]
        assert "price_history" in tables
        assert "signals" in tables
        assert "watchlist_active" in tables

        assert tables["price_history"]["cnt"] >= 2
        assert tables["signals"]["cnt"] >= 4
        assert tables["watchlist_active"]["cnt"] == 4


class TestPriceChart:
    @pytest.mark.asyncio
    async def test_price_chart_returns_data(self, client):
        resp = await client.get("/dashboard/prices/005930", params={"market": "KR", "days": 60})
        assert resp.status_code == 200
        data = resp.json()

        assert data["symbol"] == "005930"
        assert data["market"] == "KR"
        assert len(data["data"]) >= 1
        assert data["data"][0]["close"] == 60000

    @pytest.mark.asyncio
    async def test_price_chart_empty_symbol(self, client):
        resp = await client.get("/dashboard/prices/NONEXIST", params={"market": "US"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0


class TestSignalHistory:
    @pytest.mark.asyncio
    async def test_signal_history_returns_all(self, client):
        resp = await client.get("/dashboard/signals/history", params={"days": 365})
        assert resp.status_code == 200
        data = resp.json()

        assert data["count"] == 4

    @pytest.mark.asyncio
    async def test_signal_history_filter_by_market(self, client):
        resp = await client.get("/dashboard/signals/history", params={"market": "KR", "days": 365})
        data = resp.json()
        assert data["count"] == 2
        assert all(s["market"] == "KR" for s in data["signals"])


class TestReportValidation:
    """Regression tests for Session 5 bug fixes: invalid report_month/week_start → 400."""

    @pytest.mark.asyncio
    async def test_monthly_generate_invalid_format_returns_400(self, client):
        resp = await client.post(
            "/dashboard/reports/monthly/generate",
            params={"report_month": "abc"},
        )
        assert resp.status_code == 400
        assert "YYYY-MM" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_monthly_generate_partial_format_returns_400(self, client):
        resp = await client.post(
            "/dashboard/reports/monthly/generate",
            params={"report_month": "2025"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_monthly_generate_no_param_accepted(self, client):
        """report_month=None is valid — generates for current month."""
        resp = await client.post("/dashboard/reports/monthly/generate")
        # May return 200 or 500 depending on DB state; must NOT be 400/422
        assert resp.status_code != 400
        assert resp.status_code != 422

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_month", ["2025-13", "2025-0", "2025-99"])
    async def test_monthly_generate_invalid_month_range_returns_400(self, client, bad_month):
        """Month outside 1-12 → 400."""
        resp = await client.post(
            "/dashboard/reports/monthly/generate",
            params={"report_month": bad_month},
        )
        assert resp.status_code == 400
        assert "YYYY-MM" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_weekly_generate_invalid_date_returns_400(self, client):
        resp = await client.post(
            "/dashboard/reports/weekly/generate",
            params={"week_start": "not-a-date"},
        )
        assert resp.status_code == 400
        assert "YYYY-MM-DD" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_weekly_generate_valid_date_accepted(self, client):
        """A valid ISO date must pass validation (not return 400)."""
        resp = await client.post(
            "/dashboard/reports/weekly/generate",
            params={"week_start": "2025-01-06"},
        )
        assert resp.status_code != 400
        assert resp.status_code != 422
