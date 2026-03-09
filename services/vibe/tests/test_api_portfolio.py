"""
API tests for portfolio endpoints.

Covers:
- GET /portfolio (list positions)
- POST /portfolio/position (add/update)
- DELETE /portfolio/position/{market}/{symbol}
- GET /portfolio/groups, POST /portfolio/groups
- POST /portfolio/position/{market}/{symbol}/exit
- GET /portfolio/exits
- P&L calculation verification (pnl_pct from SQL)
"""

import pytest
import pytest_asyncio

from tests.conftest import (
    cleanup_all,
    seed_portfolio_positions,
    seed_watchlist_items,
)


@pytest_asyncio.fixture(autouse=True)
async def _seed_data():
    """Seed data before each test, clean up after."""
    await seed_watchlist_items()
    await seed_portfolio_positions()
    yield
    await cleanup_all()


class TestPortfolioList:
    @pytest.mark.asyncio
    async def test_get_portfolio_returns_positions(self, client):
        resp = await client.get("/portfolio")
        assert resp.status_code == 200
        data = resp.json()

        assert data["portfolio_id"] == 1
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_portfolio_filter_by_market(self, client):
        resp = await client.get("/portfolio", params={"market": "KR"})
        data = resp.json()
        assert data["count"] == 1
        assert data["positions"][0]["symbol"] == "005930"

    @pytest.mark.asyncio
    async def test_portfolio_pnl_pct_computed(self, client):
        """Verify pnl_pct is computed from SQL (Item 6 bug fix)."""
        resp = await client.get("/portfolio")
        data = resp.json()

        for pos in data["positions"]:
            if pos["symbol"] == "005930":
                # Entry: 56000, Current: 60000 → +7.14%
                assert pos["pnl_pct"] is not None
                assert pos["pnl_pct"] == pytest.approx(7.14, abs=0.1)
            elif pos["symbol"] == "AAPL":
                # Entry: 230, Current: 250 → +8.70%
                assert pos["pnl_pct"] is not None
                assert pos["pnl_pct"] == pytest.approx(8.70, abs=0.1)


class TestPortfolioPositionCRUD:
    @pytest.mark.asyncio
    async def test_add_position(self, client):
        resp = await client.post("/portfolio/position", json={
            "symbol": "GOOGL",
            "market": "US",
            "position_size": 2000,
            "entry_price": 170,
            "entry_date": "2025-03-01",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Verify it appears in the list
        list_resp = await client.get("/portfolio", params={"market": "US"})
        symbols = [p["symbol"] for p in list_resp.json()["positions"]]
        assert "GOOGL" in symbols

    @pytest.mark.asyncio
    async def test_update_position_size(self, client):
        """Upsert: adding same symbol again updates the position."""
        resp = await client.post("/portfolio/position", json={
            "symbol": "005930",
            "market": "KR",
            "position_size": 10_000_000,
            "entry_price": 58000,
            "entry_date": "2025-03-15",
        })
        assert resp.status_code == 200

        # Verify updated size
        list_resp = await client.get("/portfolio", params={"market": "KR"})
        samsung = next(p for p in list_resp.json()["positions"] if p["symbol"] == "005930")
        assert samsung["position_size"] == 10_000_000

    @pytest.mark.asyncio
    async def test_delete_position(self, client):
        resp = await client.delete("/portfolio/position/KR/005930")
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

        # Position should now have size 0 (excluded from default query)
        list_resp = await client.get("/portfolio", params={"market": "KR"})
        assert list_resp.json()["count"] == 0


class TestPortfolioGroups:
    @pytest.mark.asyncio
    async def test_get_groups(self, client):
        resp = await client.get("/portfolio/groups")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_create_and_delete_group(self, client):
        # Create
        resp = await client.post("/portfolio/groups", json={
            "name": "테스트 그룹",
            "description": "Test group for API tests",
        })
        assert resp.status_code == 200
        group_id = resp.json()["id"]
        assert group_id > 1

        # Verify
        list_resp = await client.get("/portfolio/groups")
        names = [g["name"] for g in list_resp.json()["groups"]]
        assert "테스트 그룹" in names

        # Delete
        del_resp = await client.delete(f"/portfolio/groups/{group_id}")
        assert del_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_cannot_delete_default_group(self, client):
        resp = await client.delete("/portfolio/groups/1")
        assert resp.status_code == 400


class TestPositionExit:
    @pytest.mark.asyncio
    async def test_exit_position(self, client):
        resp = await client.post(
            "/portfolio/position/KR/005930/exit",
            params={"exit_reason": "manual"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "exited"

        # Position should be removed (size set to 0)
        list_resp = await client.get("/portfolio", params={"market": "KR"})
        assert list_resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_exit_history(self, client):
        # First exit a position
        await client.post(
            "/portfolio/position/US/AAPL/exit",
            params={"exit_reason": "profit_taking"},
        )

        # Check exit history
        resp = await client.get("/portfolio/exits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert data["exits"][0]["symbol"] == "AAPL"
        assert data["exits"][0]["exit_reason"] == "profit_taking"

    @pytest.mark.asyncio
    async def test_exit_nonexistent_position(self, client):
        resp = await client.post(
            "/portfolio/position/KR/NONEXIST/exit",
            params={"exit_reason": "manual"},
        )
        assert resp.status_code == 404


class TestBulkAdd:
    @pytest.mark.asyncio
    async def test_bulk_add_positions(self, client):
        resp = await client.post("/portfolio/bulk", json={
            "portfolio_id": 1,
            "items": [
                {"symbol": "TSLA", "market": "US", "position_size": 1000,
                 "entry_price": 200, "entry_date": "2025-04-01"},
                {"symbol": "NVDA", "market": "US", "position_size": 2000,
                 "entry_price": 800, "entry_date": "2025-04-01"},
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["registered"] == 2

        # Verify
        list_resp = await client.get("/portfolio", params={"market": "US"})
        symbols = [p["symbol"] for p in list_resp.json()["positions"]]
        assert "TSLA" in symbols
        assert "NVDA" in symbols
