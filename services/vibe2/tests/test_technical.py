"""Tests for engine/technical.py — TechnicalScore calculation."""

import numpy as np
import pandas as pd
import pytest

from app.engine.technical import TechnicalScore, calculate_technical


class TestCalculateTechnical:
    def test_returns_technical_score(self, sample_ohlcv):
        result = calculate_technical(sample_ohlcv)
        assert isinstance(result, TechnicalScore)

    def test_total_in_range(self, sample_ohlcv):
        result = calculate_technical(sample_ohlcv)
        assert -1.0 <= result.total <= 1.0

    def test_oversold_rsi_positive_score(self, oversold_df):
        result = calculate_technical(oversold_df)
        assert result.rsi_score > 0, f"Expected positive rsi_score for oversold, got {result.rsi_score}"

    def test_overbought_rsi_negative_score(self, overbought_df):
        result = calculate_technical(overbought_df)
        assert result.rsi_score < 0, f"Expected negative rsi_score for overbought, got {result.rsi_score}"

    def test_price_above_all_ma_positive(self):
        """When close is above all moving averages, ma_score > 0."""
        n = 250
        dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n)
        # Steady uptrend so price is always above MAs
        close = np.linspace(10, 100, n)
        df = pd.DataFrame({
            "open": close * 0.999,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.full(n, 5_000_000),
        }, index=dates)
        result = calculate_technical(df)
        assert result.ma_score > 0, f"Expected positive ma_score, got {result.ma_score}"

    def test_price_below_all_ma_negative(self):
        """When close is below all moving averages, ma_score < 0."""
        n = 250
        dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n)
        # Steady downtrend
        close = np.linspace(100, 10, n)
        df = pd.DataFrame({
            "open": close * 1.001,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.full(n, 5_000_000),
        }, index=dates)
        result = calculate_technical(df)
        assert result.ma_score < 0, f"Expected negative ma_score, got {result.ma_score}"

    def test_details_contains_rsi(self, sample_ohlcv):
        result = calculate_technical(sample_ohlcv)
        assert "rsi_value" in result.details
        assert result.details["rsi_value"] is None or 0 <= result.details["rsi_value"] <= 100

    def test_details_contains_bb_position(self, sample_ohlcv):
        result = calculate_technical(sample_ohlcv)
        assert "bb_position" in result.details
        valid = {None, "below_lower", "below_middle", "above_middle", "above_upper"}
        assert result.details["bb_position"] in valid

    def test_insufficient_data_returns_zero(self):
        """DataFrame with < 26 rows returns zero score."""
        df = pd.DataFrame({
            "open": [1.0] * 10, "high": [1.0] * 10, "low": [1.0] * 10,
            "close": [1.0] * 10, "volume": [100] * 10,
        })
        result = calculate_technical(df)
        assert result.total == 0.0
        assert "error" in result.details

    def test_none_input_returns_zero(self):
        result = calculate_technical(None)
        assert result.total == 0.0
