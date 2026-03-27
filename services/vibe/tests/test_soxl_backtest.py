"""
Tests for SOXL backtest router (app/routers/soxl_backtest.py).

Covers:
- POST /soxl/backtest/run       — mode A/B/C/D, invalid mode 422
- POST /soxl/backtest/compare   — 4-mode comparison, metric keys
- POST /soxl/backtest/ai-strategy — LLM mock, response keys
- GET  /soxl/backtest/results   — empty, after run
- GET  /soxl/backtest/results/{id} — existing id, missing id 404
- DELETE /soxl/backtest/results — cleanup then empty
- GET  /soxl/backtest/presets   — 5 preset names
- GET  /soxl/backtest/export/{id} — CSV Content-Type
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI

from app.routers.soxl_backtest import router as soxl_bt_router


# ════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def bt_client(setup_db):
    """Async HTTP client with soxl_backtest router + seeded price data."""
    app = FastAPI()
    app.include_router(soxl_bt_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_bt_client(setup_db):
    """bt_client with synthetic SOXL price + macro + geo data pre-seeded."""
    from app.database.connection import get_db
    db = await get_db()

    # Seed 200 days of SOXL prices
    base_price = 20.0
    for i in range(200):
        dt = f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        noise = (i % 7 - 3) * 0.5
        close = round(base_price + i * 0.05 + noise, 2)
        high = round(close + 1.5, 2)
        low = round(close - 1.5, 2)
        open_ = round(close + noise * 0.2, 2)
        volume = 5_000_000 + i * 10_000
        await db.execute(
            """INSERT OR IGNORE INTO price_history
               (symbol, market, trade_date, open, high, low, close, volume)
               VALUES ('SOXL', 'US', ?, ?, ?, ?, ?, ?)""",
            (dt, open_, high, low, close, volume),
        )

    # Seed macro data
    for i in range(200):
        dt = f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        vix = 18.0 + (i % 10)
        await db.execute(
            """INSERT OR IGNORE INTO macro_indicators
               (indicator_date, vix, dxy_index, us_10y_yield, us_2y_yield,
                us_yield_spread, wti_crude, gold_price, usd_krw)
               VALUES (?, ?, 104.0, 4.3, 4.8, -0.5, 70.0, 2000.0, 1350.0)""",
            (dt, vix),
        )

    # Seed geo event
    await db.execute(
        """INSERT OR IGNORE INTO geopolitical_events
           (event_date, event_text, detail, impact)
           VALUES ('2024-03-15', 'Test event', 'Test detail', 'negative')"""
    )
    await db.commit()

    app = FastAPI()
    app.include_router(soxl_bt_router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup
    for table in ["soxl_backtest_trades", "soxl_backtest_runs"]:
        await db.execute(f"DELETE FROM {table}")
    await db.execute("DELETE FROM price_history WHERE symbol='SOXL'")
    await db.execute("DELETE FROM macro_indicators")
    await db.execute("DELETE FROM geopolitical_events")
    await db.commit()


# Helper: run a backtest and return the backtest_id
async def _run_one(client, mode="A", start="2024-03-01", end="2024-06-01"):
    resp = await client.post("/soxl/backtest/run", json={
        "mode": mode, "start_date": start, "end_date": end,
    })
    return resp


# ════════════════════════════════════════════════════════════════
# POST /soxl/backtest/run
# ════════════════════════════════════════════════════════════════

class TestBacktestRun:
    @pytest.mark.asyncio
    async def test_mode_a(self, seeded_bt_client):
        resp = await _run_one(seeded_bt_client, mode="A")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")
        if data["status"] == "completed":
            assert data["mode"] == "A"
            assert "metrics" in data

    @pytest.mark.asyncio
    async def test_mode_b(self, seeded_bt_client):
        resp = await _run_one(seeded_bt_client, mode="B")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")

    @pytest.mark.asyncio
    async def test_mode_c(self, seeded_bt_client):
        resp = await _run_one(seeded_bt_client, mode="C")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")

    @pytest.mark.asyncio
    async def test_mode_d(self, seeded_bt_client):
        resp = await _run_one(seeded_bt_client, mode="D")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")
        if data["status"] == "completed":
            assert "leverage_decay_total" in data
            assert "transaction_costs" in data

    @pytest.mark.asyncio
    async def test_invalid_mode_422(self, seeded_bt_client):
        resp = await seeded_bt_client.post("/soxl/backtest/run", json={
            "mode": "Z", "start_date": "2024-03-01", "end_date": "2024-06-01",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_with_preset(self, seeded_bt_client):
        resp = await seeded_bt_client.post("/soxl/backtest/run", json={
            "mode": "A", "start_date": "2024-03-01", "end_date": "2024-06-01",
            "preset": "conservative",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_with_custom_params(self, seeded_bt_client):
        resp = await seeded_bt_client.post("/soxl/backtest/run", json={
            "mode": "A", "start_date": "2024-03-01", "end_date": "2024-06-01",
            "params": {"rsi_entry": 30.0, "stop_loss_pct": -5.0},
        })
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════
# POST /soxl/backtest/compare
# ════════════════════════════════════════════════════════════════

class TestBacktestCompare:
    @pytest.mark.asyncio
    async def test_compare_returns_4_modes(self, seeded_bt_client):
        resp = await seeded_bt_client.post("/soxl/backtest/compare", json={
            "start_date": "2024-03-01", "end_date": "2024-06-01",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "comparison" in data
        assert len(data["comparison"]) == 4

        modes_found = {r["mode"] for r in data["comparison"]}
        assert modes_found == {"A", "B", "C", "D"}

    @pytest.mark.asyncio
    async def test_compare_has_metric_keys(self, seeded_bt_client):
        resp = await seeded_bt_client.post("/soxl/backtest/compare", json={
            "start_date": "2024-03-01", "end_date": "2024-06-01",
        })
        data = resp.json()
        for result in data["comparison"]:
            assert "metrics" in result
            assert "mode_label" in result
            assert "mode_description" in result
            assert "trades_count" in result

    @pytest.mark.asyncio
    async def test_compare_has_best_fields(self, seeded_bt_client):
        resp = await seeded_bt_client.post("/soxl/backtest/compare", json={
            "start_date": "2024-03-01", "end_date": "2024-06-01",
        })
        data = resp.json()
        # These keys should always be present (may be None if no completed runs)
        assert "best_mode" in data
        assert "best_risk_adjusted" in data
        assert "best_sortino" in data
        assert "best_drawdown" in data
        assert "benchmark_return" in data


# ════════════════════════════════════════════════════════════════
# POST /soxl/backtest/ai-strategy
# ════════════════════════════════════════════════════════════════

class TestBacktestAIStrategy:
    @pytest.mark.asyncio
    async def test_no_api_key_503(self, seeded_bt_client):
        """Without LLM_API_KEY, should return 503."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.LLM_API_KEY = None
            resp = await seeded_bt_client.post("/soxl/backtest/ai-strategy")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_ai_strategy_with_mock_llm(self, seeded_bt_client):
        """Mock the anthropic client and verify response keys."""
        # First run a backtest so there's data for the AI to analyze
        await _run_one(seeded_bt_client, mode="A")

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="## 최적 전략\n\n모드 D를 추천합니다.")]

        mock_anthropic_client = AsyncMock()
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_msg)

        with patch("app.config.settings") as mock_settings:
            mock_settings.LLM_API_KEY = "test-key"
            mock_settings.LLM_MODEL = "claude-sonnet-4-20250514"
            with patch("anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
                resp = await seeded_bt_client.post("/soxl/backtest/ai-strategy")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "strategy" in data
        assert len(data["strategy"]) > 0
        assert "backtest_summary" in data
        assert "current_context" in data
        assert "generated_at" in data
        assert "model" in data


# ════════════════════════════════════════════════════════════════
# GET /soxl/backtest/results
# ════════════════════════════════════════════════════════════════

class TestBacktestResults:
    @pytest.mark.asyncio
    async def test_empty_results(self, bt_client):
        resp = await bt_client.get("/soxl/backtest/results")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    async def test_results_after_run(self, seeded_bt_client):
        # Run a backtest first
        run_resp = await _run_one(seeded_bt_client, mode="A")
        run_data = run_resp.json()

        resp = await seeded_bt_client.get("/soxl/backtest/results")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1

        # Check result fields
        result = data["results"][0]
        assert "backtest_id" in result
        assert "mode" in result
        assert "mode_label" in result
        assert "status" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_filter_by_mode(self, seeded_bt_client):
        await _run_one(seeded_bt_client, mode="A")
        await _run_one(seeded_bt_client, mode="B")

        resp = await seeded_bt_client.get("/soxl/backtest/results", params={"mode": "A"})
        data = resp.json()
        for r in data["results"]:
            assert r["mode"] == "A"

    @pytest.mark.asyncio
    async def test_filter_by_status(self, seeded_bt_client):
        await _run_one(seeded_bt_client, mode="A")

        resp = await seeded_bt_client.get("/soxl/backtest/results", params={"status": "completed"})
        data = resp.json()
        for r in data["results"]:
            assert r["status"] == "completed"


# ════════════════════════════════════════════════════════════════
# GET /soxl/backtest/results/{id}
# ════════════════════════════════════════════════════════════════

class TestBacktestResultDetail:
    @pytest.mark.asyncio
    async def test_existing_id(self, seeded_bt_client):
        run_resp = await _run_one(seeded_bt_client, mode="A")
        bt_id = run_resp.json()["backtest_id"]

        resp = await seeded_bt_client.get(f"/soxl/backtest/results/{bt_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["backtest_id"] == bt_id
        assert "metrics" in data
        assert "trades" in data
        assert isinstance(data["trades"], list)
        assert "equity_curve" in data
        assert "mode_label" in data
        assert "params" in data
        assert "exit_reason_stats" in data
        assert "monthly_returns" in data

    @pytest.mark.asyncio
    async def test_missing_id_404(self, bt_client):
        resp = await bt_client.get("/soxl/backtest/results/nonexistent-id-12345")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════
# DELETE /soxl/backtest/results
# ════════════════════════════════════════════════════════════════

class TestBacktestCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_empty(self, bt_client):
        """Deleting when no runs exist should return deleted=0."""
        resp = await bt_client.delete("/soxl/backtest/results", params={"keep": 1})
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_keeps_recent(self, seeded_bt_client):
        # Run 3 backtests
        for mode in ("A", "B", "C"):
            await _run_one(seeded_bt_client, mode=mode)

        # Keep only 1
        del_resp = await seeded_bt_client.delete("/soxl/backtest/results", params={"keep": 1})
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] == 2

        # Verify only 1 remains
        list_resp = await seeded_bt_client.get("/soxl/backtest/results")
        assert len(list_resp.json()["results"]) == 1


# ════════════════════════════════════════════════════════════════
# GET /soxl/backtest/presets
# ════════════════════════════════════════════════════════════════

class TestBacktestPresets:
    @pytest.mark.asyncio
    async def test_presets_returns_5(self, bt_client):
        resp = await bt_client.get("/soxl/backtest/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        names = set(data["presets"].keys())
        assert names == {"default", "aggressive", "conservative", "scalper", "swing"}

    @pytest.mark.asyncio
    async def test_preset_has_params(self, bt_client):
        resp = await bt_client.get("/soxl/backtest/presets")
        data = resp.json()
        # Each preset should have full parameter set
        for name, params in data["presets"].items():
            assert "rsi_entry" in params
            assert "stop_loss_pct" in params
            assert "take_profit_pct" in params
            assert "max_hold_days" in params

    @pytest.mark.asyncio
    async def test_conservative_has_tighter_stops(self, bt_client):
        resp = await bt_client.get("/soxl/backtest/presets")
        presets = resp.json()["presets"]
        # Conservative should have tighter stop loss than aggressive
        assert presets["conservative"]["stop_loss_pct"] > presets["aggressive"]["stop_loss_pct"]


# ════════════════════════════════════════════════════════════════
# GET /soxl/backtest/stats/{id}
# ════════════════════════════════════════════════════════════════

class TestBacktestStats:
    @pytest.mark.asyncio
    async def test_stats_existing_id(self, seeded_bt_client):
        run_resp = await _run_one(seeded_bt_client, mode="A")
        bt_id = run_resp.json()["backtest_id"]

        resp = await seeded_bt_client.get(f"/soxl/backtest/stats/{bt_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["backtest_id"] == bt_id
        assert "metrics" in data
        assert "monthly_returns" in data
        assert "exit_reason_stats" in data
        assert "drawdown_periods" in data
        assert "return_distribution" in data
        assert "holding_days_distribution" in data
        assert "rsi_win_rate_analysis" in data

    @pytest.mark.asyncio
    async def test_stats_missing_id_404(self, bt_client):
        resp = await bt_client.get("/soxl/backtest/stats/nonexistent-id")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════
# GET /soxl/backtest/export/{id} — CSV
# ════════════════════════════════════════════════════════════════

class TestBacktestExport:
    @pytest.mark.asyncio
    async def test_export_csv(self, seeded_bt_client):
        run_resp = await _run_one(seeded_bt_client, mode="A")
        bt_id = run_resp.json()["backtest_id"]

        resp = await seeded_bt_client.get(f"/soxl/backtest/export/{bt_id}")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "content-disposition" in resp.headers
        assert "attachment" in resp.headers["content-disposition"]
        assert ".csv" in resp.headers["content-disposition"]

        # Verify CSV content has header row
        text = resp.text
        lines = text.strip().split("\n")
        assert len(lines) >= 1  # At least the header
        header = lines[0]
        assert "Entry Date" in header
        assert "Exit Reason" in header
        assert "Return %" in header

    @pytest.mark.asyncio
    async def test_export_missing_id_404(self, bt_client):
        resp = await bt_client.get("/soxl/backtest/export/nonexistent-id")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════
# SOXS Hedge Simulation
# ════════════════════════════════════════════════════════════════

class TestHedgeMode:
    @pytest.mark.asyncio
    async def test_hedge_run_has_hedge_stats(self, seeded_bt_client):
        """hedge_mode=true → response contains hedge_stats with expected keys."""
        resp = await seeded_bt_client.post("/soxl/backtest/run", json={
            "mode": "A", "start_date": "2024-03-01", "end_date": "2024-06-01",
            "hedge_mode": True, "hedge_ratio": 0.2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")
        if data["status"] == "completed":
            assert "hedge_stats" in data
            hs = data["hedge_stats"]
            assert hs["hedge_mode"] is True
            assert hs["hedge_ratio"] == 0.2
            assert "hedge_pnl" in hs
            assert "base_max_drawdown" in hs
            assert "hedged_max_drawdown" in hs
            assert "drawdown_reduction" in hs
            assert "hedged_equity_curve" in hs

    @pytest.mark.asyncio
    async def test_hedge_off_no_hedge_stats(self, seeded_bt_client):
        """hedge_mode=false (default) → no hedge_stats key."""
        resp = await seeded_bt_client.post("/soxl/backtest/run", json={
            "mode": "A", "start_date": "2024-03-01", "end_date": "2024-06-01",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "hedge_stats" not in data

    @pytest.mark.asyncio
    async def test_hedge_ratio_out_of_range_422(self, seeded_bt_client):
        """hedge_ratio > 0.5 should be rejected with 422."""
        resp = await seeded_bt_client.post("/soxl/backtest/run", json={
            "mode": "A", "start_date": "2024-03-01", "end_date": "2024-06-01",
            "hedge_mode": True, "hedge_ratio": 0.6,
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_hedge_ratio_negative_422(self, seeded_bt_client):
        """hedge_ratio < 0.0 should be rejected with 422."""
        resp = await seeded_bt_client.post("/soxl/backtest/run", json={
            "mode": "A", "start_date": "2024-03-01", "end_date": "2024-06-01",
            "hedge_mode": True, "hedge_ratio": -0.1,
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_hedge_drawdown_fields_computed(self, seeded_bt_client):
        """Hedge stats include both base and hedged drawdown for comparison."""
        resp = await seeded_bt_client.post("/soxl/backtest/run", json={
            "mode": "A", "start_date": "2024-03-01", "end_date": "2024-06-01",
            "hedge_mode": True, "hedge_ratio": 0.3,
        })
        data = resp.json()
        if data["status"] == "completed" and "hedge_stats" in data:
            hs = data["hedge_stats"]
            # Both drawdowns should be non-negative and finite
            assert hs["base_max_drawdown"] >= 0
            assert hs["hedged_max_drawdown"] >= 0
            # drawdown_reduction = base - hedged (can be negative if hedge hurts)
            assert hs["drawdown_reduction"] == pytest.approx(
                hs["base_max_drawdown"] - hs["hedged_max_drawdown"], abs=0.001
            )


# ════════════════════════════════════════════════════════════════
# GET /soxl/backtest/optimize — Random Search Optimizer
# ════════════════════════════════════════════════════════════════

class TestBacktestOptimize:
    @pytest.mark.asyncio
    async def test_optimize_returns_top_n(self, seeded_bt_client):
        """GET /optimize?mode=A&top_n=3&max_iter=10 → results list, length <= 3."""
        resp = await seeded_bt_client.get(
            "/soxl/backtest/optimize",
            params={"mode": "A", "top_n": 3, "max_iter": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "results" in data
        assert len(data["results"]) <= 3
        assert data["mode"] == "A"
        assert data["total_evaluated"] == 10
        # Each result has params and metrics
        for r in data["results"]:
            assert "params" in r
            assert "metrics" in r
            assert "sharpe_ratio" in r["metrics"]

    @pytest.mark.asyncio
    async def test_optimize_max_iter_out_of_range(self, seeded_bt_client):
        """max_iter > 200 should be rejected with 422."""
        resp = await seeded_bt_client.get(
            "/soxl/backtest/optimize",
            params={"mode": "A", "max_iter": 300},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_optimize_results_sorted_by_sharpe(self, seeded_bt_client):
        """Results should be sorted by Sharpe ratio descending."""
        resp = await seeded_bt_client.get(
            "/soxl/backtest/optimize",
            params={"mode": "A", "top_n": 5, "max_iter": 15},
        )
        data = resp.json()
        if data["status"] == "ok" and len(data["results"]) >= 2:
            sharpes = [r["metrics"]["sharpe_ratio"] for r in data["results"]
                       if r["metrics"]["sharpe_ratio"] is not None]
            # Verify descending order
            for i in range(len(sharpes) - 1):
                assert sharpes[i] >= sharpes[i + 1]


# ════════════════════════════════════════════════════════════════
# GET /soxl/backtest/optimize-history
# ════════════════════════════════════════════════════════════════

class TestOptimizeHistory:
    @pytest.mark.asyncio
    async def test_empty_history(self, bt_client):
        """No optimize results → empty array, total=0."""
        resp = await bt_client.get("/soxl/backtest/optimize-history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []

    @pytest.mark.asyncio
    async def test_mode_filter(self, seeded_bt_client):
        """Insert results for modes A and D, filter by A → only A returned."""
        import json as _json
        from app.database.connection import get_db
        db = await get_db()
        for mode in ("A", "A", "D"):
            await db.execute(
                """INSERT INTO soxl_optimize_results
                   (run_at, mode, params_json, sharpe, sortino, max_drawdown, total_return)
                   VALUES ('2024-03-10T00:00:00', ?, ?, 1.0, 0.8, 0.05, 0.1)""",
                (mode, _json.dumps({"rsi_entry": 35})),
            )
        await db.commit()

        resp = await seeded_bt_client.get(
            "/soxl/backtest/optimize-history", params={"mode": "A"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["results"]) == 2
        for r in data["results"]:
            assert r["mode"] == "A"
            assert "params" in r
            assert isinstance(r["params"], dict)

        # Cleanup
        await db.execute("DELETE FROM soxl_optimize_results")
        await db.commit()

    @pytest.mark.asyncio
    async def test_limit_out_of_range(self, bt_client):
        """limit > 100 → 422."""
        resp = await bt_client.get(
            "/soxl/backtest/optimize-history", params={"limit": 200}
        )
        assert resp.status_code == 422
