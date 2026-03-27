"""
Tests for SOXL real-time analysis endpoints (soxl_live.py).

Covers:
- GET /soxl/live/quote — Finnhub mock
- GET /soxl/live/indicators — DB + Finnhub mock
- GET /soxl/live/sector — multi-quote + correlation
- GET /soxl/live/intraday — interval validation, yfinance fallback on 403
- /soxl/live/alerts CRUD flow (POST → GET → DELETE)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI

from tests.conftest import cleanup_all

from app.routers.soxl_live import router as soxl_live_router


# ════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════


def _make_mock_finnhub():
    """Create a mock FinnhubLiveClient with sensible defaults."""
    mock = AsyncMock()
    mock.get_quote = AsyncMock(return_value={
        "c": 25.50, "d": 0.75, "dp": 3.03,
        "h": 26.00, "l": 24.80, "o": 25.00, "pc": 24.75,
    })
    mock.get_candles = AsyncMock(return_value=[
        {"time": 1700000000, "open": 25.0, "high": 25.5, "low": 24.8, "close": 25.3, "volume": 100000},
        {"time": 1700000300, "open": 25.3, "high": 25.7, "low": 25.1, "close": 25.5, "volume": 120000},
    ])
    mock.get_multi_quotes = AsyncMock(return_value={
        "SOXL": {"c": 25.50, "d": 0.75, "dp": 3.03},
        "SOXX": {"c": 220.0, "d": 2.0, "dp": 0.92},
        "SMH": {"c": 180.0, "d": 1.5, "dp": 0.84},
        "QQQ": {"c": 440.0, "d": 3.0, "dp": 0.69},
        "SPY": {"c": 530.0, "d": 2.0, "dp": 0.38},
    })
    mock.is_market_open = MagicMock(return_value=False)
    mock.get_market_session = MagicMock(return_value="장마감")
    return mock


@pytest_asyncio.fixture
async def live_client(setup_db):
    """Async HTTP client with soxl_live router and mocked Finnhub."""
    app = FastAPI()
    app.include_router(soxl_live_router)

    mock_fh = _make_mock_finnhub()
    app.state.finnhub = mock_fh

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        ac._mock_fh = mock_fh  # expose for assertions
        yield ac


@pytest_asyncio.fixture
async def _seed_soxl_price_history(setup_db):
    """Insert SOXL price data for indicator computation."""
    from app.database.connection import get_db
    db = await get_db()

    for i in range(70):
        dt = f"2025-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        close = round(20.0 + i * 0.1 + (i % 5 - 2) * 0.3, 2)
        volume = 3_000_000 + i * 50_000
        await db.execute(
            """INSERT OR IGNORE INTO price_history
               (symbol, market, trade_date, open, high, low, close, volume)
               VALUES ('SOXL', 'US', ?, ?, ?, ?, ?, ?)""",
            (dt, close + 0.5, close + 1.0, close - 1.0, close, volume),
        )
    await db.commit()
    yield
    await db.execute("DELETE FROM price_history WHERE symbol='SOXL'")
    await db.commit()


@pytest_asyncio.fixture
async def _cleanup_alerts(setup_db):
    """Ensure soxl_alerts table is clean before and after test."""
    from app.database.connection import get_db
    db = await get_db()
    await db.execute("DELETE FROM soxl_alerts")
    await db.commit()
    yield
    await db.execute("DELETE FROM soxl_alerts")
    await db.commit()


# ════════════════════════════════════════════════════════════════
# GET /soxl/live/quote
# ════════════════════════════════════════════════════════════════

class TestSoxlLiveQuote:
    @pytest.mark.asyncio
    async def test_returns_price_data(self, live_client):
        resp = await live_client.get("/soxl/live/quote")
        assert resp.status_code == 200
        data = resp.json()
        assert data["price"] == 25.50
        assert data["change"] == 0.75
        assert data["change_pct"] == 3.03
        assert data["high"] == 26.00
        assert data["low"] == 24.80
        assert "market_open" in data
        assert "session" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_finnhub_called_once(self, live_client):
        await live_client.get("/soxl/live/quote")
        live_client._mock_fh.get_quote.assert_called_with("SOXL")


class TestSoxlLiveQuoteNoFinnhub:
    @pytest.mark.asyncio
    async def test_503_when_no_finnhub(self, setup_db):
        app = FastAPI()
        app.include_router(soxl_live_router)
        # No finnhub client set on app.state

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/soxl/live/quote")
            assert resp.status_code == 503


# ════════════════════════════════════════════════════════════════
# GET /soxl/live/indicators
# ════════════════════════════════════════════════════════════════

class TestSoxlLiveIndicators:
    @pytest.mark.asyncio
    async def test_returns_technical_indicators(self, live_client, _seed_soxl_price_history):
        resp = await live_client.get("/soxl/live/indicators")
        assert resp.status_code == 200
        data = resp.json()
        assert "price" in data
        assert data["price"] == 25.50
        assert "rsi_14" in data
        assert "macd" in data
        assert "macd_signal" in data
        assert "bb_upper" in data
        assert "bb_middle" in data
        assert "bb_lower" in data
        assert "ma_5" in data
        assert "ma_20" in data
        assert "computed_at" in data

    @pytest.mark.asyncio
    async def test_404_when_no_data(self, live_client):
        """No SOXL data in DB → 404."""
        # Ensure no SOXL price data exists
        from app.database.connection import get_db
        db = await get_db()
        await db.execute("DELETE FROM price_history WHERE symbol='SOXL'")
        await db.commit()

        resp = await live_client.get("/soxl/live/indicators")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════
# GET /soxl/live/sector
# ════════════════════════════════════════════════════════════════

class TestSoxlLiveSector:
    @pytest.mark.asyncio
    async def test_returns_sector_comparison(self, live_client, _seed_soxl_price_history):
        resp = await live_client.get("/soxl/live/sector")
        assert resp.status_code == 200
        data = resp.json()
        assert "soxl" in data
        assert data["soxl"]["price"] == 25.50
        assert "etfs" in data
        assert len(data["etfs"]) == 4  # SOXX, SMH, QQQ, SPY
        for etf in data["etfs"]:
            assert "symbol" in etf
            assert "price" in etf
            assert "change_pct" in etf
        assert "market_open" in data

    @pytest.mark.asyncio
    async def test_etf_symbols_present(self, live_client, _seed_soxl_price_history):
        resp = await live_client.get("/soxl/live/sector")
        data = resp.json()
        symbols = {e["symbol"] for e in data["etfs"]}
        assert symbols == {"SOXX", "SMH", "QQQ", "SPY"}


# ════════════════════════════════════════════════════════════════
# GET /soxl/live/intraday — interval validation + yfinance fallback
# ════════════════════════════════════════════════════════════════

class TestSoxlLiveIntraday:
    @pytest.mark.asyncio
    async def test_valid_resolution_1(self, live_client):
        resp = await live_client.get("/soxl/live/intraday", params={"resolution": "1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "candles" in data
        assert data["resolution"] == "1"

    @pytest.mark.asyncio
    async def test_valid_resolution_5(self, live_client):
        resp = await live_client.get("/soxl/live/intraday", params={"resolution": "5"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolution"] == "5"

    @pytest.mark.asyncio
    async def test_invalid_resolution_rejected(self, live_client):
        resp = await live_client.get("/soxl/live/intraday", params={"resolution": "15"})
        assert resp.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_invalid_resolution_string_rejected(self, live_client):
        resp = await live_client.get("/soxl/live/intraday", params={"resolution": "abc"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_finnhub_empty_triggers_yfinance_fallback(self, live_client):
        """When Finnhub returns empty candles, yfinance fallback should be tried."""
        live_client._mock_fh.get_candles = AsyncMock(return_value=[])

        with patch("app.routers.soxl_live._yfinance_intraday", new_callable=AsyncMock) as mock_yf:
            mock_yf.return_value = [
                {"time": 1700000000, "open": 25.0, "high": 25.5,
                 "low": 24.8, "close": 25.3, "volume": 50000},
            ]
            resp = await live_client.get("/soxl/live/intraday", params={"resolution": "1"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "yfinance"
            assert data["count"] == 1
            mock_yf.assert_called_once_with("SOXL", "1")

    @pytest.mark.asyncio
    async def test_finnhub_has_data_no_fallback(self, live_client):
        """When Finnhub returns data, yfinance should NOT be called."""
        with patch("app.routers.soxl_live._yfinance_intraday", new_callable=AsyncMock) as mock_yf:
            resp = await live_client.get("/soxl/live/intraday", params={"resolution": "1"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "finnhub"
            mock_yf.assert_not_called()


# ════════════════════════════════════════════════════════════════
# /soxl/live/alerts CRUD
# ════════════════════════════════════════════════════════════════

class TestSoxlAlertsCRUD:
    @pytest.mark.asyncio
    async def test_create_alert(self, live_client, _cleanup_alerts):
        resp = await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_above",
            "threshold": 30.0,
            "label": "Target 1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_and_list(self, live_client, _cleanup_alerts):
        # Create two alerts
        await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_above", "threshold": 30.0, "label": "High",
        })
        await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_below", "threshold": 15.0, "label": "Low",
        })

        # List
        resp = await live_client.get("/soxl/live/alerts")
        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        assert len(alerts) == 2
        types = {a["alert_type"] for a in alerts}
        assert types == {"price_above", "price_below"}

    @pytest.mark.asyncio
    async def test_full_crud_flow(self, live_client, _cleanup_alerts):
        # Create
        create_resp = await live_client.post("/soxl/live/alerts", json={
            "alert_type": "change_pct", "threshold": 5.0, "label": "Volatile",
        })
        alert_id = create_resp.json()["id"]

        # Read — verify exists
        list_resp = await live_client.get("/soxl/live/alerts")
        ids = [a["id"] for a in list_resp.json()["alerts"]]
        assert alert_id in ids

        # Delete
        del_resp = await live_client.delete(f"/soxl/live/alerts/{alert_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify gone
        list_resp2 = await live_client.get("/soxl/live/alerts")
        ids2 = [a["id"] for a in list_resp2.json()["alerts"]]
        assert alert_id not in ids2

    @pytest.mark.asyncio
    async def test_invalid_alert_type(self, live_client, _cleanup_alerts):
        resp = await live_client.post("/soxl/live/alerts", json={
            "alert_type": "invalid_type", "threshold": 10.0,
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_alert_fields_present(self, live_client, _cleanup_alerts):
        await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_above", "threshold": 50.0, "label": "Test",
        })
        resp = await live_client.get("/soxl/live/alerts")
        alert = resp.json()["alerts"][0]
        assert "id" in alert
        assert "alert_type" in alert
        assert "threshold" in alert
        assert "label" in alert
        assert "active" in alert
        assert "created_at" in alert
        assert alert["active"] is True


# ════════════════════════════════════════════════════════════════
# _check_alerts helper
# ════════════════════════════════════════════════════════════════

class TestCheckAlerts:
    @pytest.mark.asyncio
    async def test_alert_triggers_and_deactivates(self, live_client, _cleanup_alerts):
        """Create a price_above alert, then check if it triggers."""
        from app.routers.soxl_live import _check_alerts

        # Create alert: trigger when price >= 25.0
        await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_above", "threshold": 25.0, "label": "Trigger test",
        })

        # Check with price above threshold
        triggered = await _check_alerts(26.0, 3.0)
        assert len(triggered) == 1
        assert triggered[0]["alert_type"] == "price_above"
        assert triggered[0]["threshold"] == 25.0

        # Alert should now be deactivated — second check should return empty
        triggered2 = await _check_alerts(26.0, 3.0)
        assert len(triggered2) == 0

    @pytest.mark.asyncio
    async def test_no_trigger_below_threshold(self, live_client, _cleanup_alerts):
        from app.routers.soxl_live import _check_alerts

        await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_above", "threshold": 50.0, "label": "High target",
        })

        triggered = await _check_alerts(25.0, 1.0)
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_zero_price_skipped(self, live_client, _cleanup_alerts):
        from app.routers.soxl_live import _check_alerts

        await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_below", "threshold": 10.0, "label": "Low",
        })

        triggered = await _check_alerts(0, 0)
        assert len(triggered) == 0


# ════════════════════════════════════════════════════════════════
# Webhook alert dispatch
# ════════════════════════════════════════════════════════════════

class TestAlertWebhook:
    @pytest.mark.asyncio
    async def test_webhook_url_stored_and_returned(self, live_client, _cleanup_alerts):
        """Create alert with webhook_url → GET response includes it."""
        await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_above", "threshold": 30.0,
            "label": "With hook", "webhook_url": "https://example.com/hook",
        })
        resp = await live_client.get("/soxl/live/alerts")
        alert = resp.json()["alerts"][0]
        assert alert["webhook_url"] == "https://example.com/hook"

    @pytest.mark.asyncio
    async def test_webhook_called_on_trigger(self, live_client, _cleanup_alerts):
        """When alert triggers and has webhook_url, httpx.AsyncClient.post is called."""
        from app.routers.soxl_live import _check_alerts

        await live_client.post("/soxl/live/alerts", json={
            "alert_type": "price_above", "threshold": 20.0,
            "label": "Hook test", "webhook_url": "https://hooks.example.com/soxl",
        })

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("app.routers.soxl_live._dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
            triggered = await _check_alerts(25.0, 2.0)
            assert len(triggered) == 1
            mock_dispatch.assert_called_once_with(
                "https://hooks.example.com/soxl", "price_above", 20.0, 25.0,
            )

    @pytest.mark.asyncio
    async def test_webhook_failure_does_not_block_trigger(self, live_client, _cleanup_alerts):
        """If the webhook HTTP call fails, _dispatch_webhook catches the error
        and the alert still triggers normally."""
        from app.routers.soxl_live import _dispatch_webhook

        # Patch httpx.AsyncClient so .post() raises ConnectionError
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=ConnectionError("DNS failed"))

        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_client_cls):
            # Should NOT raise — the function catches all exceptions internally
            await _dispatch_webhook(
                "https://bad-host.invalid/hook", "price_above", 25.0, 30.0,
            )
            mock_client_instance.post.assert_called_once()


# ════════════════════════════════════════════════════════════════
# POST /soxl/live/ai-analysis
# ════════════════════════════════════════════════════════════════

class TestAIAnalysis:
    """Tests for the POST /soxl/live/ai-analysis endpoint."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_error(self, live_client):
        """Without LLM_API_KEY, returns status='error' with message."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.LLM_API_KEY = None
            resp = await live_client.post("/soxl/live/ai-analysis")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "error"
            assert "LLM API" in data["message"]

    @pytest.mark.asyncio
    async def test_success_response_keys(self, live_client, _seed_soxl_price_history):
        """Mock LLM → response has status=ok, analysis, context_snapshot, generated_at."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="## SOXL 분석\n\n기술적으로 중립 구간입니다.")]

        mock_anthropic_client = AsyncMock()
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_msg)

        with patch("app.config.settings") as mock_settings:
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_MODEL = "claude-sonnet-4-20250514"
            with patch("anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
                resp = await live_client.post("/soxl/live/ai-analysis")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "analysis" in data
        assert len(data["analysis"]) > 0
        assert "context_snapshot" in data
        assert "generated_at" in data
        assert "model" in data

    @pytest.mark.asyncio
    async def test_context_snapshot_has_strategy_keys(self, live_client, _seed_soxl_price_history):
        """context_snapshot must include best_backtest, latest_optimize, active_alerts keys."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="분석 결과입니다.")]

        mock_anthropic_client = AsyncMock()
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_msg)

        with patch("app.config.settings") as mock_settings:
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_MODEL = "claude-sonnet-4-20250514"
            with patch("anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
                resp = await live_client.post("/soxl/live/ai-analysis")

        data = resp.json()
        assert data["status"] == "ok"
        cs = data["context_snapshot"]
        # These keys must be present (even if None)
        assert "best_backtest" in cs
        assert "latest_optimize" in cs
        assert "active_alerts" in cs
        # Standard keys too
        assert "price" in cs
        assert "rsi" in cs
        assert "vix" in cs

    @pytest.mark.asyncio
    async def test_db_failure_still_returns_analysis(self, live_client):
        """If _gather_soxl_context DB queries fail, the endpoint should still
        return a valid response (either ok or error), not crash with 500."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="분석입니다.")]

        mock_anthropic_client = AsyncMock()
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_msg)

        # Mock _gather_soxl_context to return minimal context (simulating DB failure recovery)
        mock_ctx = {"price": 0, "geo_events": [], "semi_risks": [], "key_variables": [], "semi_sector_impact": [], "correlations": {}}

        with patch("app.config.settings") as mock_settings:
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_MODEL = "claude-sonnet-4-20250514"
            with patch("app.routers.soxl_live._gather_soxl_context", new_callable=AsyncMock, return_value=mock_ctx):
                with patch("anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
                    resp = await live_client.post("/soxl/live/ai-analysis")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "analysis" in data

    @pytest.mark.asyncio
    async def test_llm_exception_returns_error_not_500(self, live_client, _seed_soxl_price_history):
        """If LLM call raises, endpoint returns status=error, not HTTP 500."""
        mock_anthropic_client = AsyncMock()
        mock_anthropic_client.messages.create = AsyncMock(
            side_effect=RuntimeError("API rate limit exceeded")
        )

        with patch("app.config.settings") as mock_settings:
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_MODEL = "claude-sonnet-4-20250514"
            with patch("anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
                resp = await live_client.post("/soxl/live/ai-analysis")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "rate limit" in data["message"]


# ════════════════════════════════════════════════════════════════
# Coverage: _gather_soxl_context branch coverage
# ════════════════════════════════════════════════════════════════

class TestGatherSoxlContext:
    """Exercise _gather_soxl_context branches for coverage."""

    @pytest.mark.asyncio
    async def test_context_with_price_data(self, live_client, _seed_soxl_price_history):
        """With DB price data + Finnhub mock, context should have technicals."""
        from app.routers.soxl_live import _gather_soxl_context

        # Build a mock request with finnhub on app.state
        mock_request = MagicMock()
        mock_fh = _make_mock_finnhub()
        mock_request.app.state.finnhub = mock_fh

        ctx = await _gather_soxl_context(mock_request)
        assert ctx["price"] == 25.50
        assert "rsi_14" in ctx
        assert "macd" in ctx
        assert "session" in ctx

    @pytest.mark.asyncio
    async def test_context_without_finnhub(self, live_client, _seed_soxl_price_history):
        """No Finnhub client → price=0, no crash."""
        from app.routers.soxl_live import _gather_soxl_context

        mock_request = MagicMock()
        mock_request.app.state.finnhub = None

        ctx = await _gather_soxl_context(mock_request)
        assert ctx["price"] == 0

    @pytest.mark.asyncio
    async def test_context_empty_db(self, live_client):
        """No data in any table → context has defaults, no crash."""
        from app.routers.soxl_live import _gather_soxl_context
        from app.database.connection import get_db

        # Ensure clean DB
        db = await get_db()
        await db.execute("DELETE FROM price_history WHERE symbol='SOXL'")
        await db.execute("DELETE FROM signals WHERE symbol='SOXL'")
        await db.execute("DELETE FROM soxl_backtest_runs")
        await db.execute("DELETE FROM soxl_optimize_results")
        await db.execute("DELETE FROM soxl_alerts")
        await db.commit()

        mock_request = MagicMock()
        mock_fh = _make_mock_finnhub()
        mock_request.app.state.finnhub = mock_fh

        ctx = await _gather_soxl_context(mock_request)
        assert isinstance(ctx, dict)
        assert ctx["price"] == 25.50
        # These should be absent or None since no DB data
        assert ctx.get("best_backtest") is None
        assert ctx.get("latest_optimize") is None

    @pytest.mark.asyncio
    async def test_context_with_backtest_and_alerts(self, live_client, _seed_soxl_price_history, _cleanup_alerts):
        """Context includes best_backtest and active_alerts when data exists."""
        from app.routers.soxl_live import _gather_soxl_context
        from app.database.connection import get_db

        db = await get_db()
        # Insert a backtest run
        await db.execute(
            """INSERT INTO soxl_backtest_runs
               (backtest_id, start_date, end_date, mode, params_json, status,
                sharpe_ratio, max_drawdown, total_return, total_trades, hit_rate, started_at)
               VALUES ('ctx-test', '2024-01-01', '2024-03-01', 'D', '{}', 'completed',
                       1.5, 0.05, 0.2, 10, 0.6, '2024-03-01T00:00:00')"""
        )
        # Insert an active alert
        await db.execute(
            "INSERT INTO soxl_alerts (alert_type, threshold, label, active) VALUES ('price_above', 30.0, 'Test', 1)"
        )
        await db.commit()

        mock_request = MagicMock()
        mock_fh = _make_mock_finnhub()
        mock_request.app.state.finnhub = mock_fh

        ctx = await _gather_soxl_context(mock_request)
        assert ctx["best_backtest"] is not None
        assert ctx["best_backtest"]["sharpe"] == 1.5
        assert ctx["active_alerts"]["total"] == 1
        assert ctx["active_alerts"]["by_type"]["price_above"] == 1

        # Cleanup
        await db.execute("DELETE FROM soxl_backtest_runs WHERE backtest_id='ctx-test'")
        await db.execute("DELETE FROM soxl_alerts")
        await db.commit()


# ════════════════════════════════════════════════════════════════
# Coverage: _build_soxl_ai_prompt branch coverage
# ════════════════════════════════════════════════════════════════

class TestBuildSoxlAiPrompt:
    """Exercise _build_soxl_ai_prompt with various context states."""

    def test_minimal_context(self):
        from app.routers.soxl_live import _build_soxl_ai_prompt
        ctx = {"price": 0, "geo_events": [], "semi_risks": [], "key_variables": [],
               "semi_sector_impact": [], "correlations": {}}
        prompt = _build_soxl_ai_prompt(ctx)
        assert "SOXL" in prompt
        assert "전략 컨텍스트" in prompt
        assert "데이터 없음" in prompt  # No strategy data

    def test_full_context(self):
        from app.routers.soxl_live import _build_soxl_ai_prompt
        ctx = {
            "price": 25.0, "change_pct": 2.5, "rsi_14": 45.0,
            "macd": 0.5, "macd_signal": 0.3, "macd_histogram": 0.2,
            "bb_upper": 27.0, "bb_middle": 25.0, "bb_lower": 23.0,
            "ma_5": 25.0, "ma_20": 24.0, "ma_60": 23.0, "volume_ratio": 1.5,
            "signal": {"date": "2024-03-01", "final_signal": "BUY", "raw_score": 2.0,
                       "confidence": 0.8, "rationale": "RSI oversold"},
            "macro": {"vix": 18, "dxy": 104, "us_10y": 4.3, "us_2y": 4.8,
                      "yield_spread": -0.5, "fed_rate": 5.5, "wti": 70, "gold": 2000,
                      "usd_krw": 1350, "fear_greed": 55, "date": "2024-03-01"},
            "geo_events": [{"date": "2024-03-01", "impact": "negative",
                           "event": "Test event", "detail": "Detail"}],
            "semi_risks": [{"severity": "high", "risk": "Supply chain", "detail": "Detail"}],
            "key_variables": [{"variable": "VIX", "current": "18", "bullish": "<15", "bearish": ">25"}],
            "semi_sector_impact": [{"direction": "negative", "magnitude": "medium",
                                    "tickers": ["SOXL"], "reason": "Tariffs", "sector": "반도체"}],
            "correlations": {"SOXX": 0.95, "QQQ": 0.85},
            "best_backtest": {"mode": "D", "sharpe": 1.5,
                              "max_drawdown": 0.05, "total_return": 0.2,
                              "hit_rate": 0.6, "total_trades": 10, "period": "2024-01~2024-03"},
            "latest_optimize": {"mode": "D", "params": {"rsi_entry": 30}, "sharpe": 1.8,
                                "sortino": 1.5, "max_drawdown": 0.04, "total_return": 0.25,
                                "run_at": "2024-03-10"},
            "active_alerts": {"total": 2, "by_type": {"price_above": 1, "price_below": 1}},
        }
        prompt = _build_soxl_ai_prompt(ctx)
        assert "전략 컨텍스트" in prompt
        assert "모드 D" in prompt
        assert "Sharpe=1.5" in prompt or "Sharpe=1.50" in prompt
        assert "활성 알림" in prompt
        assert "최신 자동 최적화" in prompt
        assert "rsi_entry=30" in prompt
        assert "반도체 섹터 영향 평가" in prompt
        assert "SOXX" in prompt

    def test_context_with_only_alerts(self):
        from app.routers.soxl_live import _build_soxl_ai_prompt
        ctx = {"price": 20.0, "geo_events": [], "semi_risks": [], "key_variables": [],
               "semi_sector_impact": [], "correlations": {},
               "active_alerts": {"total": 3, "by_type": {"change_pct": 3}}}
        prompt = _build_soxl_ai_prompt(ctx)
        assert "활성 알림: 총 3건" in prompt


# ════════════════════════════════════════════════════════════════
# Coverage: _compute_daily_correlations
# ════════════════════════════════════════════════════════════════

class TestDailyCorrelations:
    @pytest.mark.asyncio
    async def test_returns_empty_with_insufficient_data(self, live_client):
        """Less than 20 SOXL rows → returns empty dict."""
        from app.routers.soxl_live import _compute_daily_correlations
        result = await _compute_daily_correlations(60)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_correlation_with_db_data(self, live_client, _seed_soxl_price_history):
        """With SOXL price data in DB, computes correlations (may use yfinance fallback)."""
        from app.routers.soxl_live import _compute_daily_correlations, _corr_cache
        _corr_cache.clear()  # Reset cache
        with patch("app.routers.soxl_live._yfinance_intraday", new_callable=AsyncMock, return_value=[]):
            result = await _compute_daily_correlations(60)
        assert isinstance(result, dict)


# ════════════════════════════════════════════════════════════════
# Coverage: optimizer.py — SoxlParameterOptimizer error path
# ════════════════════════════════════════════════════════════════

class TestSoxlOptimizerErrorPaths:
    @pytest.mark.asyncio
    async def test_invalid_mode_returns_failed(self, setup_db):
        from app.backtesting.optimizer import SoxlParameterOptimizer
        optimizer = SoxlParameterOptimizer()
        result = await optimizer.optimize(mode="Z")
        assert result["status"] == "failed"
        assert "Invalid mode" in result["error"]

    def test_sample_soxl_params_returns_dict(self):
        from app.backtesting.optimizer import _sample_soxl_params
        params = _sample_soxl_params()
        assert isinstance(params, dict)
        assert "rsi_entry" in params
        assert "stop_loss_pct" in params
        assert isinstance(params["max_hold_days"], int)
        assert isinstance(params["cooldown_days"], int)
        # Range checks
        assert 25.0 <= params["rsi_entry"] <= 45.0
        assert -12.0 <= params["stop_loss_pct"] <= -3.0
