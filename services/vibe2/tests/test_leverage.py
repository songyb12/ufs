"""Tests for engine/leverage.py — LeverageScore calculation."""

import numpy as np
import pandas as pd
import pytest

from app.engine.leverage import LeverageScore, calculate_leverage


def _make_df(start_price, end_price, n=30):
    """Create a simple OHLCV DataFrame with linear price movement."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n)
    close = np.linspace(start_price, end_price, n)
    return pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.005,
        "low": close * 0.995,
        "close": close,
        "volume": np.full(n, 5_000_000),
    }, index=dates)


class TestCalculateLeverage:
    def test_returns_leverage_score(self, sample_ohlcv):
        result = calculate_leverage(sample_ohlcv, sample_ohlcv, vix=20.0)
        assert isinstance(result, LeverageScore)

    def test_total_in_range(self, sample_ohlcv):
        result = calculate_leverage(sample_ohlcv, sample_ohlcv, vix=20.0)
        assert -1.0 <= result.total <= 1.0

    def test_zero_tracking_diff(self):
        """When SOXL return = SOXX return * 3, decay_score ≈ 0."""
        # SOXX goes from 100 to 110 (10% return)
        soxx = _make_df(100, 110, n=30)
        # SOXL should go from 100 to 130 (30% = 3x of 10%)
        soxl = _make_df(100, 130, n=30)
        result = calculate_leverage(soxl, soxx, vix=20.0)
        assert result.decay_score == 0.0

    def test_low_vix_positive_volatility(self):
        """VIX < 15 should give volatility_score > 0.5."""
        soxl = _make_df(50, 50, n=30)
        soxx = _make_df(50, 50, n=30)
        result = calculate_leverage(soxl, soxx, vix=12.0)
        assert result.volatility_score > 0.5

    def test_high_vix_negative_volatility(self):
        """VIX > 35 should give volatility_score < -0.5."""
        soxl = _make_df(50, 50, n=30)
        soxx = _make_df(50, 50, n=30)
        result = calculate_leverage(soxl, soxx, vix=40.0)
        assert result.volatility_score < -0.5

    def test_low_daily_vol_positive_divergence(self):
        """Low daily volatility (< 3%) → divergence_score > 0."""
        n = 30
        dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n)
        # Very stable prices — tiny daily changes
        close = 50.0 + np.random.RandomState(42).normal(0, 0.1, n).cumsum()
        close = np.maximum(close, 40.0)
        df = pd.DataFrame({
            "open": close, "high": close * 1.001, "low": close * 0.999,
            "close": close, "volume": np.full(n, 5_000_000),
        }, index=dates)
        result = calculate_leverage(df, df, vix=20.0)
        assert result.divergence_score > 0

    def test_none_vix_returns_zero_volatility(self):
        soxl = _make_df(50, 50, n=30)
        result = calculate_leverage(soxl, soxl, vix=None)
        assert result.volatility_score == 0.0

    def test_insufficient_data_zero_decay(self):
        """With < 20 rows, decay_score should be 0."""
        short = _make_df(50, 55, n=10)
        result = calculate_leverage(short, short, vix=20.0)
        assert result.decay_score == 0.0
        assert "tracking_diff_error" in result.details
