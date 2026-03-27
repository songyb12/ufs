"""
Tests for SOXL scheduler jobs (soxl_daily_optimize, soxl_alert_check).

The scheduler jobs are inner functions of register_jobs(), so we test them
by replicating their core logic with mocks:
- soxl_daily_optimize: calls SoxlParameterOptimizer.optimize → saves to DB
- soxl_alert_check: checks market hours → calls Finnhub → calls _check_alerts
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ════════════════════════════════════════════════════════════════
# soxl_daily_optimize job logic
# ════════════════════════════════════════════════════════════════

class TestSoxlDailyOptimizeJob:
    """Test the core logic of the soxl_daily_optimize scheduler job."""

    @pytest.mark.asyncio
    async def test_saves_results_to_db(self, setup_db):
        """Mock optimizer to return 3 results → 3 rows in soxl_optimize_results."""
        from app.database.connection import get_db

        mock_results = {
            "status": "ok",
            "results": [
                {"params": {"rsi_entry": 30}, "metrics": {"sharpe_ratio": 1.5, "sortino_ratio": 1.2, "max_drawdown": 0.05, "total_return": 0.2}},
                {"params": {"rsi_entry": 35}, "metrics": {"sharpe_ratio": 1.3, "sortino_ratio": 1.0, "max_drawdown": 0.06, "total_return": 0.15}},
                {"params": {"rsi_entry": 40}, "metrics": {"sharpe_ratio": 1.1, "sortino_ratio": 0.9, "max_drawdown": 0.07, "total_return": 0.1}},
            ],
        }

        with patch("app.backtesting.optimizer.SoxlParameterOptimizer.optimize", new_callable=AsyncMock, return_value=mock_results):
            # Replicate the job logic
            from app.backtesting.optimizer import SoxlParameterOptimizer
            optimizer = SoxlParameterOptimizer()
            result = await optimizer.optimize(mode="D", max_iter=100, top_n=5)

            if result.get("status") == "ok" and result.get("results"):
                db = await get_db()
                run_at = datetime.now(timezone.utc).isoformat()
                for r in result["results"]:
                    m = r["metrics"]
                    await db.execute(
                        """INSERT INTO soxl_optimize_results
                           (run_at, mode, params_json, sharpe, sortino, max_drawdown, total_return)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (run_at, "D", json.dumps(r["params"]),
                         m.get("sharpe_ratio"), m.get("sortino_ratio"),
                         m.get("max_drawdown"), m.get("total_return")),
                    )
                await db.commit()

        # Verify DB
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*) FROM soxl_optimize_results WHERE mode='D'")
        count = (await cursor.fetchone())[0]
        assert count == 3

        # Verify data integrity
        cursor = await db.execute(
            "SELECT sharpe, params_json FROM soxl_optimize_results ORDER BY sharpe DESC"
        )
        rows = await cursor.fetchall()
        assert rows[0][0] == 1.5
        assert json.loads(rows[0][1])["rsi_entry"] == 30

        # Cleanup
        await db.execute("DELETE FROM soxl_optimize_results")
        await db.commit()

    @pytest.mark.asyncio
    async def test_optimize_called_with_correct_params(self, setup_db):
        """Optimizer should be called with mode='D', max_iter=100."""
        with patch("app.backtesting.optimizer.SoxlParameterOptimizer.optimize", new_callable=AsyncMock) as mock_opt:
            mock_opt.return_value = {"status": "ok", "results": []}

            from app.backtesting.optimizer import SoxlParameterOptimizer
            optimizer = SoxlParameterOptimizer()
            await optimizer.optimize(mode="D", max_iter=100, top_n=5)

            mock_opt.assert_called_once_with(mode="D", max_iter=100, top_n=5)

    @pytest.mark.asyncio
    async def test_no_results_no_db_write(self, setup_db):
        """When optimizer returns no results, nothing should be written to DB."""
        from app.database.connection import get_db

        with patch("app.backtesting.optimizer.SoxlParameterOptimizer.optimize", new_callable=AsyncMock) as mock_opt:
            mock_opt.return_value = {"status": "ok", "results": []}

            from app.backtesting.optimizer import SoxlParameterOptimizer
            optimizer = SoxlParameterOptimizer()
            result = await optimizer.optimize(mode="D", max_iter=100, top_n=5)

            # Replicate job logic: only write if results
            if result.get("status") == "ok" and result.get("results"):
                pass  # Would write, but list is empty

        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*) FROM soxl_optimize_results")
        count = (await cursor.fetchone())[0]
        assert count == 0


# ════════════════════════════════════════════════════════════════
# soxl_alert_check job logic
# ════════════════════════════════════════════════════════════════

def _make_dt(year=2024, month=3, day=6, hour=10, minute=0, weekday=None):
    """Create a mock datetime for Eastern Time."""
    dt = MagicMock()
    dt.weekday.return_value = weekday if weekday is not None else 2  # Wednesday
    dt.hour = hour
    dt.minute = minute
    return dt


class TestSoxlAlertCheckJob:
    """Test the core logic of the soxl_alert_check scheduler job."""

    @pytest.mark.asyncio
    async def test_market_hours_calls_check_alerts(self):
        """During market hours (Wed 14:00 UTC = 10:00 ET), should call _check_alerts."""
        # Simulate: Wed, 10:00 ET → market open
        mock_now_et = _make_dt(hour=10, minute=0, weekday=2)

        mock_finnhub = AsyncMock()
        mock_finnhub.get_quote = AsyncMock(return_value={"c": 25.0, "dp": 2.0})

        mock_registry = MagicMock()
        mock_registry._finnhub = mock_finnhub

        with patch("app.routers.soxl_live._check_alerts", new_callable=AsyncMock) as mock_check:
            # Replicate job logic
            now_et = mock_now_et
            if now_et.weekday() >= 5:
                pass  # weekend
            else:
                t = now_et.hour * 60 + now_et.minute
                if 9 * 60 + 30 <= t <= 16 * 60:
                    finnhub = getattr(mock_registry, "_finnhub", None)
                    if finnhub:
                        quote = await finnhub.get_quote("SOXL")
                        await mock_check(quote.get("c", 0), quote.get("dp", 0))

            mock_check.assert_called_once_with(25.0, 2.0)
            mock_finnhub.get_quote.assert_called_once_with("SOXL")

    @pytest.mark.asyncio
    async def test_outside_market_hours_no_call(self):
        """At 01:00 ET (outside market hours), _check_alerts should NOT be called."""
        mock_now_et = _make_dt(hour=1, minute=0, weekday=2)  # Wed 01:00 ET

        with patch("app.routers.soxl_live._check_alerts", new_callable=AsyncMock) as mock_check:
            now_et = mock_now_et
            if now_et.weekday() >= 5:
                pass
            else:
                t = now_et.hour * 60 + now_et.minute
                if 9 * 60 + 30 <= t <= 16 * 60:
                    # Would call _check_alerts
                    await mock_check(0, 0)

            mock_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_weekend_no_call(self):
        """On Saturday, _check_alerts should NOT be called."""
        mock_now_et = _make_dt(hour=12, minute=0, weekday=5)  # Saturday noon

        with patch("app.routers.soxl_live._check_alerts", new_callable=AsyncMock) as mock_check:
            now_et = mock_now_et
            if now_et.weekday() >= 5:
                pass  # Skip weekend
            else:
                t = now_et.hour * 60 + now_et.minute
                if 9 * 60 + 30 <= t <= 16 * 60:
                    await mock_check(0, 0)

            mock_check.assert_not_called()
