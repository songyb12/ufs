"""
API tests for signals and backtest endpoints.

Covers:
- GET /signals
- GET /signals/{market}
- GET /backtest/results
- GET /watchlist
"""

import pytest
import pytest_asyncio

from tests.conftest import (
    cleanup_all,
    seed_signals,
    seed_watchlist_items,
)


@pytest_asyncio.fixture(autouse=True)
async def _seed_data():
    """Seed data before each test, clean up after."""
    await seed_watchlist_items()
    await seed_signals()
    yield
    await cleanup_all()


class TestSignals:
    @pytest.mark.asyncio
    async def test_get_latest_signals(self, client):
        resp = await client.get("/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 4

    @pytest.mark.asyncio
    async def test_get_signals_by_market_kr(self, client):
        resp = await client.get("/signals/KR")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(s["market"] == "KR" for s in data)

    @pytest.mark.asyncio
    async def test_get_signals_by_market_us(self, client):
        resp = await client.get("/signals/US")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(s["market"] == "US" for s in data)

    @pytest.mark.asyncio
    async def test_signal_fields(self, client):
        resp = await client.get("/signals/KR")
        data = resp.json()
        sig = data[0]

        # Check required fields exist
        assert "symbol" in sig
        assert "market" in sig
        assert "signal_date" in sig
        assert "final_signal" in sig
        assert "raw_score" in sig
        assert "rsi_value" in sig


class TestBacktestResults:
    @pytest.mark.asyncio
    async def test_get_backtest_results_empty(self, client):
        """No backtest runs yet → returns empty list."""
        resp = await client.get("/backtest/results")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestWatchlist:
    @pytest.mark.asyncio
    async def test_get_watchlist(self, client):
        resp = await client.get("/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        # Returns plain list
        assert isinstance(data, list)
        assert len(data) == 4

    @pytest.mark.asyncio
    async def test_watchlist_has_expected_symbols(self, client):
        resp = await client.get("/watchlist")
        symbols = [item["symbol"] for item in resp.json()]
        assert "005930" in symbols
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    @pytest.mark.asyncio
    async def test_add_watchlist_item(self, client):
        resp = await client.post("/watchlist", json={
            "symbol": "AMZN",
            "name": "Amazon",
            "market": "US",
            "asset_type": "stock",
        })
        assert resp.status_code == 200

        # Verify
        list_resp = await client.get("/watchlist")
        symbols = [item["symbol"] for item in list_resp.json()]
        assert "AMZN" in symbols

    @pytest.mark.asyncio
    async def test_delete_watchlist_item(self, client):
        resp = await client.delete("/watchlist/MSFT", params={"market": "US"})
        assert resp.status_code == 200
