"""Tests for technical indicator calculations."""

import pytest
import pandas as pd
import numpy as np

from app.indicators.technical import compute_all_indicators, compute_indicators_series, _safe_float


def _make_ohlcv(n=100, base_price=50000, trend=0):
    """Generate synthetic OHLCV DataFrame for testing.

    Args:
        n: Number of rows
        base_price: Starting price
        trend: Daily price change (positive=uptrend, negative=downtrend)
    """
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(42)
    noise = np.random.randn(n) * (base_price * 0.01)
    close = base_price + np.cumsum(noise) + np.arange(n) * trend
    close = np.maximum(close, base_price * 0.5)  # Floor at 50% of base

    df = pd.DataFrame({
        "open": close * (1 + np.random.randn(n) * 0.005),
        "high": close * (1 + abs(np.random.randn(n) * 0.01)),
        "low": close * (1 - abs(np.random.randn(n) * 0.01)),
        "close": close,
        "volume": np.random.randint(100000, 1000000, n),
    }, index=dates)
    return df


class TestComputeAllIndicators:
    """Test compute_all_indicators function."""

    def test_returns_all_indicator_keys(self):
        df = _make_ohlcv(100)
        result = compute_all_indicators(df)
        expected_keys = [
            "rsi_14", "ma_5", "ma_20", "ma_60", "ma_120",
            "macd", "macd_signal", "macd_histogram",
            "bollinger_upper", "bollinger_middle", "bollinger_lower",
            "disparity_20", "volume_ratio",
        ]
        for key in expected_keys:
            assert key in result, f"Missing indicator: {key}"

    def test_rsi_in_valid_range(self):
        df = _make_ohlcv(100)
        result = compute_all_indicators(df)
        rsi = result["rsi_14"]
        assert rsi is not None
        assert 0 <= rsi <= 100, f"RSI {rsi} out of range [0, 100]"

    def test_disparity_around_100(self):
        df = _make_ohlcv(100)
        result = compute_all_indicators(df)
        disp = result["disparity_20"]
        assert disp is not None
        assert 80 < disp < 120, f"Disparity {disp} unreasonably far from 100"

    def test_bollinger_band_order(self):
        df = _make_ohlcv(100)
        result = compute_all_indicators(df)
        assert result["bollinger_lower"] < result["bollinger_middle"] < result["bollinger_upper"]

    def test_ma_order_with_uptrend(self):
        df = _make_ohlcv(200, trend=100)
        result = compute_all_indicators(df)
        # In strong uptrend, shorter MAs should be above longer MAs
        assert result["ma_5"] is not None
        assert result["ma_20"] is not None

    def test_empty_dataframe_returns_empty(self):
        df = pd.DataFrame()
        result = compute_all_indicators(df)
        assert result == {}

    def test_too_short_dataframe_returns_empty(self):
        df = _make_ohlcv(10)
        result = compute_all_indicators(df)
        assert result == {}

    def test_exactly_20_rows(self):
        df = _make_ohlcv(20)
        result = compute_all_indicators(df)
        assert "rsi_14" in result
        assert "ma_20" in result

    def test_volume_ratio_positive(self):
        df = _make_ohlcv(100)
        result = compute_all_indicators(df)
        vr = result["volume_ratio"]
        assert vr is not None
        assert vr > 0, "Volume ratio should be positive"

    def test_missing_high_low_columns(self):
        """Should handle DataFrame with only close and volume."""
        df = _make_ohlcv(100)[["close", "volume"]]
        result = compute_all_indicators(df)
        assert "rsi_14" in result
        assert result["rsi_14"] is not None


class TestComputeIndicatorsSeries:
    """Test compute_indicators_series function."""

    def test_returns_dataframe(self):
        df = _make_ohlcv(100)
        result = compute_indicators_series(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(df)

    def test_empty_returns_empty_df(self):
        df = pd.DataFrame()
        result = compute_indicators_series(df)
        assert result.empty

    def test_short_returns_empty_df(self):
        df = _make_ohlcv(10)
        result = compute_indicators_series(df)
        assert result.empty

    def test_has_expected_columns(self):
        df = _make_ohlcv(100)
        result = compute_indicators_series(df)
        expected = ["rsi_14", "ma_5", "ma_20", "macd", "bollinger_upper", "disparity_20"]
        for col in expected:
            assert col in result.columns


class TestSafeFloat:
    """Test _safe_float helper."""

    def test_normal_value(self):
        s = pd.Series([1.0, 2.5, 3.7])
        assert _safe_float(s, -1) == 3.7

    def test_nan_returns_none(self):
        s = pd.Series([1.0, float("nan")])
        assert _safe_float(s, -1) is None

    def test_out_of_bounds_returns_none(self):
        s = pd.Series([1.0])
        assert _safe_float(s, 5) is None

    def test_rounds_to_4_decimals(self):
        s = pd.Series([1.123456789])
        result = _safe_float(s, 0)
        assert result == 1.1235
