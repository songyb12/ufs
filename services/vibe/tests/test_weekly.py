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
