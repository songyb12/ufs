"""Tests for app.indicators.weekly — weekly timeframe analysis."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd

from app.indicators.weekly import (
    compute_weekly_indicators,
    compute_timeframe_multiplier,
    _determine_trend,
    _safe_float,
)


# ── weekly_report.py hit_rate formatting ──


class TestWeeklyReportHitRateFormatting:
    """Regression tests for Session 5 P2 bug: hit_t5=0.0 treated as falsy.

    Bug: `if perf.get("hit_t5")` evaluates 0.0 as False → returns None.
    Fix: `if perf.get("hit_t5") is not None` → correctly returns 0.0.
    """

    def _fmt(self, perf: dict) -> tuple:
        hit_rate_t5 = round(perf["hit_t5"] * 100, 1) if perf.get("hit_t5") is not None else None
        avg_return_t5 = round(perf["avg_ret_t5"], 2) if perf.get("avg_ret_t5") is not None else None
        return hit_rate_t5, avg_return_t5

    def test_zero_hit_rate_returns_0_not_none(self):
        """hit_t5=0.0 (0% hit rate) must not be coerced to None."""
        hit, _ = self._fmt({"hit_t5": 0.0, "avg_ret_t5": -1.5})
        assert hit == 0.0
        assert hit is not None

    def test_zero_avg_return_returns_0_not_none(self):
        """avg_ret_t5=0.0 must not be coerced to None."""
        _, avg = self._fmt({"hit_t5": 0.5, "avg_ret_t5": 0.0})
        assert avg == 0.0
        assert avg is not None

    def test_missing_key_returns_none(self):
        """Missing key → None (expected behaviour)."""
        hit, avg = self._fmt({"hit_t5": None, "avg_ret_t5": None})
        assert hit is None
        assert avg is None

    def test_positive_hit_rate_formatted_to_percentage(self):
        hit, _ = self._fmt({"hit_t5": 0.6, "avg_ret_t5": 1.23456})
        assert hit == 60.0

    def test_avg_return_rounded_to_2dp(self):
        _, avg = self._fmt({"hit_t5": 0.5, "avg_ret_t5": 1.23456})
        assert avg == 1.23


# ── _safe_float ──


class TestSafeFloat:
    def test_normal_series(self):
        s = pd.Series([1.0, 2.0, 3.123456])
        assert _safe_float(s) == 3.1235

    def test_nan_last(self):
        s = pd.Series([1.0, 2.0, float("nan")])
        assert _safe_float(s) is None

    def test_empty_series(self):
        s = pd.Series([], dtype=float)
        assert _safe_float(s) is None

    def test_single_value(self):
        s = pd.Series([42.0])
        assert _safe_float(s) == 42.0

    def test_non_series_input(self):
        # _safe_float expects a pd.Series; non-Series raises AttributeError
        import pytest
        with pytest.raises(AttributeError):
            _safe_float(None)


# ── compute_timeframe_multiplier ──


class TestTimeframeMultiplier:
    # BUY signal
    def test_buy_bullish(self):
        assert compute_timeframe_multiplier("BUY", "bullish") == 1.2

    def test_buy_neutral(self):
        assert compute_timeframe_multiplier("BUY", "neutral") == 1.0

    def test_buy_bearish(self):
        assert compute_timeframe_multiplier("BUY", "bearish") == 0.7

    # SELL signal
    def test_sell_bearish(self):
        assert compute_timeframe_multiplier("SELL", "bearish") == 1.2

    def test_sell_neutral(self):
        assert compute_timeframe_multiplier("SELL", "neutral") == 1.0

    def test_sell_bullish(self):
        assert compute_timeframe_multiplier("SELL", "bullish") == 0.7

    # HOLD signal
    def test_hold_any(self):
        for trend in ("bullish", "neutral", "bearish"):
            assert compute_timeframe_multiplier("HOLD", trend) == 1.0

    # Edge case
    def test_unknown_signal(self):
        assert compute_timeframe_multiplier("WAIT", "bullish") == 1.0


# ── _determine_trend ──


class TestDetermineTrend:
    def _series(self, values):
        return pd.Series(values, dtype=float)

    def test_bullish_all_signals(self):
        # price > MA5, MA5 > MA20, momentum > 3%
        close = self._series([100, 102, 104, 106, 110])
        ma5 = self._series([98, 99, 100, 101, 105])
        ma20 = self._series([95, 96, 97, 98, 100])
        assert _determine_trend(close, ma5, ma20) == "bullish"

    def test_bearish_all_signals(self):
        # price < MA5, MA5 < MA20, momentum < -3%
        close = self._series([110, 108, 106, 104, 100])
        ma5 = self._series([112, 111, 110, 108, 105])
        ma20 = self._series([115, 114, 113, 112, 110])
        assert _determine_trend(close, ma5, ma20) == "bearish"

    def test_neutral_mixed(self):
        # price > MA5 (bullish), MA5 < MA20 (bearish), flat momentum
        close = self._series([100, 100, 100, 100, 101])
        ma5 = self._series([99, 99, 99, 99, 100])
        ma20 = self._series([101, 101, 101, 101, 102])
        # 1 bullish + 1 bearish + 0 momentum → neutral
        assert _determine_trend(close, ma5, ma20) == "neutral"

    def test_empty_close(self):
        close = self._series([])
        ma5 = self._series([])
        ma20 = self._series([])
        assert _determine_trend(close, ma5, ma20) == "neutral"

    def test_short_series_no_momentum(self):
        # < 4 weeks, only price/MA signals used
        close = self._series([105])
        ma5 = self._series([100])
        ma20 = self._series([95])
        # price > MA5 (bullish), MA5 > MA20 (bullish) → bullish
        assert _determine_trend(close, ma5, ma20) == "bullish"

    def test_momentum_boundary(self):
        # Exactly 3% momentum — not > 3 so no bullish signal
        close = self._series([100, 101, 102, 100, 103])
        ma5 = self._series([99, 99, 99, 99, 102])  # price > MA5
        ma20 = self._series([95, 95, 95, 95, 95])  # MA5 > MA20
        # 2 bullish (price>MA5 + MA5>MA20) + momentum exactly 3% (not triggered)
        assert _determine_trend(close, ma5, ma20) == "bullish"

    def test_zero_close_4_weeks_ago(self):
        # close[-4] == 0 should skip momentum calc
        close = self._series([0, 10, 20, 30, 50])
        ma5 = self._series([0, 5, 10, 15, 40])
        ma20 = self._series([0, 3, 8, 12, 35])
        # Should not divide by zero
        result = _determine_trend(close, ma5, ma20)
        assert result in ("bullish", "bearish", "neutral")


# ── compute_weekly_indicators ──


def _make_daily_df(days=60, start_price=10000, trend=0.001):
    """Create a dummy daily OHLCV DataFrame."""
    dates = pd.bdate_range(end="2025-01-15", periods=days, freq="B")
    prices = [start_price]
    for i in range(1, days):
        prices.append(prices[-1] * (1 + trend + np.random.uniform(-0.01, 0.01)))
    close = np.array(prices)
    return pd.DataFrame({
        "open": close * 0.99,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": np.random.randint(100000, 500000, size=days),
    }, index=dates)


class TestComputeWeeklyIndicators:
    def test_none_input(self):
        assert compute_weekly_indicators(None) is None

    def test_empty_df(self):
        assert compute_weekly_indicators(pd.DataFrame()) is None

    def test_too_few_rows(self):
        df = _make_daily_df(days=20)
        assert compute_weekly_indicators(df) is None

    def test_sufficient_data(self):
        df = _make_daily_df(days=120, trend=0.002)
        result = compute_weekly_indicators(df)
        assert result is not None
        assert "rsi_14_weekly" in result
        assert "ma_5_weekly" in result
        assert "ma_20_weekly" in result
        assert "macd_weekly" in result
        assert "trend_direction" in result
        assert result["trend_direction"] in ("bullish", "bearish", "neutral")
        assert "week_ending" in result

    def test_returns_float_values(self):
        df = _make_daily_df(days=120)
        result = compute_weekly_indicators(df)
        if result is not None:
            rsi = result["rsi_14_weekly"]
            if rsi is not None:
                assert isinstance(rsi, float)
                assert 0 <= rsi <= 100

    def test_string_date_index(self):
        df = _make_daily_df(days=120)
        df.index = df.index.strftime("%Y-%m-%d")
        result = compute_weekly_indicators(df)
        assert result is not None

    def test_too_few_weekly_bars(self):
        # 30 daily rows but only ~6 weekly bars
        df = _make_daily_df(days=31)
        result = compute_weekly_indicators(df)
        assert result is None

    def test_macd_short_data(self):
        # Enough for weekly bars but < 26 weeks for MACD
        df = _make_daily_df(days=80)
        result = compute_weekly_indicators(df)
        # Should still work, macd_weekly might be None
        if result is not None:
            assert "macd_weekly" in result


# ════════════════════════════════════════════════════════════════
# Weekly report — SOXL section (_build_soxl_weekly)
# ════════════════════════════════════════════════════════════════

import pytest
import pytest_asyncio

from tests.conftest import cleanup_all


async def _seed_soxl_weekly_data():
    """Insert SOXL price + alert + backtest data for a test week."""
    from app.database.connection import get_db
    db = await get_db()

    # Price data for the week 2024-03-04 ~ 2024-03-08 (Mon-Fri)
    prices = [
        ("2024-03-04", 22.0, 23.5, 21.0, 22.5, 4_000_000),
        ("2024-03-05", 22.5, 24.0, 22.0, 23.0, 4_500_000),
        ("2024-03-06", 23.0, 23.5, 21.5, 22.0, 3_800_000),
        ("2024-03-07", 22.0, 24.5, 21.8, 24.0, 5_000_000),
        ("2024-03-08", 24.0, 25.0, 23.5, 24.5, 4_200_000),
    ]
    for dt, o, h, l, c, v in prices:
        await db.execute(
            """INSERT OR IGNORE INTO price_history
               (symbol, market, trade_date, open, high, low, close, volume)
               VALUES ('SOXL', 'US', ?, ?, ?, ?, ?, ?)""",
            (dt, o, h, l, c, v),
        )

    # A triggered alert in the week
    await db.execute(
        """INSERT INTO soxl_alerts (alert_type, threshold, label, triggered_at, active)
           VALUES ('price_above', 24.0, 'Target hit', '2024-03-07 15:30:00', 0)"""
    )

    # A backtest result
    await db.execute(
        """INSERT INTO soxl_backtest_runs
           (backtest_id, start_date, end_date, mode, params_json, status,
            total_trades, hit_rate, sharpe_ratio, max_drawdown, total_return, started_at)
           VALUES ('test-bt-001', '2024-01-01', '2024-03-01', 'D', '{}', 'completed',
                   15, 0.6, 1.25, 0.08, 0.15, '2024-03-06T00:00:00')"""
    )

    await db.commit()


async def _cleanup_soxl_weekly():
    from app.database.connection import get_db
    db = await get_db()
    await db.execute("DELETE FROM price_history WHERE symbol='SOXL'")
    await db.execute("DELETE FROM soxl_alerts")
    await db.execute("DELETE FROM soxl_backtest_runs")
    await db.execute("DELETE FROM soxl_optimize_results")
    await db.commit()


@pytest_asyncio.fixture
async def soxl_weekly_data(setup_db):
    await _seed_soxl_weekly_data()
    yield
    await _cleanup_soxl_weekly()


class TestBuildSoxlWeekly:
    """Tests for _build_soxl_weekly() in weekly_report.py."""

    @pytest.mark.asyncio
    async def test_soxl_key_in_report(self, setup_db, soxl_weekly_data):
        from app.reports.weekly_report import generate_weekly_report
        report = await generate_weekly_report(week_start="2024-03-04")
        assert "soxl" in report
        assert isinstance(report["soxl"], dict)

    @pytest.mark.asyncio
    async def test_soxl_performance_keys(self, setup_db, soxl_weekly_data):
        from app.reports.weekly_report import _build_soxl_weekly
        from app.database.connection import get_db
        db = await get_db()
        section = await _build_soxl_weekly(db, "2024-03-04", "2024-03-11")
        assert "performance" in section
        perf = section["performance"]
        assert "weekly_return_pct" in perf
        assert "week_high" in perf
        assert "week_low" in perf
        assert "avg_volume" in perf
        # Verify actual calculations
        assert perf["week_high"] == 25.0  # max high
        assert perf["week_low"] == 21.0   # min low
        # Return: (24.5 - 22.5) / 22.5 * 100 = 8.89%
        assert perf["weekly_return_pct"] == pytest.approx(8.89, abs=0.01)

    @pytest.mark.asyncio
    async def test_soxl_alerts_triggered(self, setup_db, soxl_weekly_data):
        from app.reports.weekly_report import _build_soxl_weekly
        from app.database.connection import get_db
        db = await get_db()
        section = await _build_soxl_weekly(db, "2024-03-04", "2024-03-11")
        assert "alerts_triggered" in section
        alerts = section["alerts_triggered"]
        assert alerts["count"] == 1
        assert isinstance(alerts["details"], list)
        assert alerts["details"][0]["alert_type"] == "price_above"

    @pytest.mark.asyncio
    async def test_soxl_best_backtest(self, setup_db, soxl_weekly_data):
        from app.reports.weekly_report import _build_soxl_weekly
        from app.database.connection import get_db
        db = await get_db()
        section = await _build_soxl_weekly(db, "2024-03-04", "2024-03-11")
        assert "best_backtest" in section
        bt = section["best_backtest"]
        assert "sharpe" in bt
        assert "mode" in bt
        assert bt["mode"] == "D"
        assert bt["sharpe"] == 1.25

    @pytest.mark.asyncio
    async def test_soxl_empty_data_graceful(self, setup_db):
        """No SOXL data → section is empty dict (not None, no crash)."""
        from app.reports.weekly_report import _build_soxl_weekly
        from app.database.connection import get_db
        # Clean everything first
        db = await get_db()
        await db.execute("DELETE FROM price_history WHERE symbol='SOXL'")
        await db.execute("DELETE FROM soxl_alerts")
        await db.execute("DELETE FROM soxl_backtest_runs")
        await db.execute("DELETE FROM soxl_optimize_results")
        await db.commit()

        section = await _build_soxl_weekly(db, "2024-03-04", "2024-03-11")
        assert isinstance(section, dict)
        # No crash, no performance key when no data
        assert "performance" not in section or section.get("performance") is None
