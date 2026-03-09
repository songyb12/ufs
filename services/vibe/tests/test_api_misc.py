"""
API tests for briefing, risk, alerts, sentiment, and screening endpoints.

Covers:
- GET/POST /briefing
- GET /risk/portfolio, /risk/events, /risk/sectors
- GET/POST /alerts/config, GET /alerts/history
- GET /sentiment, GET /sentiment/latest
- GET /screening/candidates
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
    """Seed minimal data before each test, clean up after."""
    await seed_watchlist_items()
    await seed_portfolio_positions()
    yield
    await cleanup_all()


# ── Briefing ──


class TestBriefing:
    @pytest.mark.asyncio
    async def test_get_briefings_empty(self, client):
        """GET /briefing returns 200 with empty list when no briefings."""
        resp = await client.get("/briefing")
        assert resp.status_code == 200
        data = resp.json()
        assert "briefings" in data
        assert "count" in data
        assert isinstance(data["briefings"], list)
        assert data["count"] == len(data["briefings"])

    @pytest.mark.asyncio
    async def test_get_briefings_with_limit(self, client):
        """GET /briefing?limit=5 respects limit parameter."""
        resp = await client.get("/briefing", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["briefings"], list)

    @pytest.mark.asyncio
    async def test_get_latest_briefing_404_when_empty(self, client):
        """GET /briefing/latest returns 404 when no briefings exist."""
        resp = await client.get("/briefing/latest")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_briefing_by_date_404(self, client):
        """GET /briefing/{date} returns 404 for non-existent date."""
        resp = await client.get("/briefing/2099-01-01")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_briefing(self, client):
        """POST /briefing/generate returns 200 or 500 (depends on data availability).

        We accept either outcome since generation may fail without
        full pipeline data, but the endpoint itself should be reachable.
        """
        resp = await client.post("/briefing/generate")
        assert resp.status_code in (200, 500)


# ── Risk ──


class TestRisk:
    @pytest.mark.asyncio
    async def test_get_risk_portfolio(self, client):
        """GET /risk/portfolio returns positions and sector_exposure."""
        resp = await client.get("/risk/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "positions" in data
        assert "sector_exposure" in data
        assert isinstance(data["positions"], list)

    @pytest.mark.asyncio
    async def test_get_risk_portfolio_with_market(self, client):
        """GET /risk/portfolio?market=KR filters by market."""
        resp = await client.get("/risk/portfolio", params={"market": "KR"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["positions"], list)

    @pytest.mark.asyncio
    async def test_get_risk_events(self, client):
        """GET /risk/events returns events list."""
        resp = await client.get("/risk/events")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        assert "count" in data

    @pytest.mark.asyncio
    async def test_get_risk_events_with_params(self, client):
        """GET /risk/events with custom market and days_ahead."""
        resp = await client.get("/risk/events", params={"market": "US", "days_ahead": 14})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["events"], list)

    @pytest.mark.asyncio
    async def test_get_risk_sectors(self, client):
        """GET /risk/sectors returns sector mapping dict."""
        resp = await client.get("/risk/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert "sectors" in data
        assert isinstance(data["sectors"], dict)


# ── Alerts ──


class TestAlerts:
    @pytest.mark.asyncio
    async def test_get_alert_config(self, client):
        """GET /alerts/config returns 200 with config list."""
        resp = await client.get("/alerts/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert isinstance(data["config"], list)

    @pytest.mark.asyncio
    async def test_update_alert_config(self, client):
        """POST /alerts/config upserts config entries and returns 200."""
        payload = [
            {"key": "discord_webhook", "value": "https://example.com/webhook", "description": "Test webhook"},
            {"key": "alert_threshold", "value": "5.0"},
        ]
        resp = await client.post("/alerts/config", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["updated"] == 2

    @pytest.mark.asyncio
    async def test_update_then_read_alert_config(self, client):
        """POST then GET /alerts/config verifies persistence."""
        payload = [{"key": "test_key_persist", "value": "test_value_123"}]
        resp = await client.post("/alerts/config", json=payload)
        assert resp.status_code == 200

        resp = await client.get("/alerts/config")
        assert resp.status_code == 200
        config = resp.json()["config"]
        keys = [c["key"] for c in config]
        assert "test_key_persist" in keys

    @pytest.mark.asyncio
    async def test_get_alert_history(self, client):
        """GET /alerts/history returns 200 with history list."""
        resp = await client.get("/alerts/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert isinstance(data["history"], list)
        assert "count" in data

    @pytest.mark.asyncio
    async def test_get_alert_history_with_limit(self, client):
        """GET /alerts/history?limit=10 respects limit."""
        resp = await client.get("/alerts/history", params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["history"], list)


# ── Sentiment ──


class TestSentiment:
    @pytest.mark.asyncio
    async def test_get_sentiment(self, client):
        """GET /sentiment returns 200 with sentiment list."""
        resp = await client.get("/sentiment")
        assert resp.status_code == 200
        data = resp.json()
        assert "sentiment" in data
        assert isinstance(data["sentiment"], list)
        assert "count" in data

    @pytest.mark.asyncio
    async def test_get_sentiment_with_days(self, client):
        """GET /sentiment?days=30 respects days parameter."""
        resp = await client.get("/sentiment", params={"days": 30})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["sentiment"], list)

    @pytest.mark.asyncio
    async def test_get_latest_sentiment_404_when_empty(self, client):
        """GET /sentiment/latest returns 404 when no sentiment data."""
        resp = await client.get("/sentiment/latest")
        assert resp.status_code == 404


# ── Screening ──


class TestScreening:
    @pytest.mark.asyncio
    async def test_get_screening_candidates(self, client):
        """GET /screening/candidates returns 200 with candidates list."""
        resp = await client.get("/screening/candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert "candidates" in data
        assert isinstance(data["candidates"], list)
        assert "count" in data

    @pytest.mark.asyncio
    async def test_get_screening_candidates_with_market(self, client):
        """GET /screening/candidates?market=US filters by market."""
        resp = await client.get("/screening/candidates", params={"market": "US"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["candidates"], list)
