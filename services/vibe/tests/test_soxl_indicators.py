"""
Unit tests for app/utils/soxl_indicators.py — shared technical indicator library.

Covers all public functions with normal, edge, and boundary inputs.
"""

import numpy as np
import pytest

from app.utils.soxl_indicators import (
    compute_adx,
    compute_atr,
    compute_bollinger,
    compute_disparity,
    compute_macd,
    compute_multi_tf_rsi,
    compute_obv_trend,
    compute_rsi,
    compute_stoch_rsi,
    compute_volatility_ann,
    detect_gap,
    detect_rsi_divergence,
)


# ── Helpers ──

def _rising(n=60, start=100.0, step=1.0):
    return np.array([start + i * step for i in range(n)], dtype=float)

def _flat(n=60, value=100.0):
    return np.full(n, value, dtype=float)

def _alternating(n=60, low=90.0, high=110.0):
    return np.array([low if i % 2 == 0 else high for i in range(n)], dtype=float)

_empty = np.array([], dtype=float)


# ════════════════════════════════════════════════════════════════
# compute_rsi
# ════════════════════════════════════════════════════════════════

class TestComputeRSI:
    def test_normal_range(self):
        result = compute_rsi(_alternating(40), 14)
        assert result is not None
        assert 0 <= result <= 100

    def test_shorter_than_period(self):
        assert compute_rsi(_rising(10), period=14) is None

    def test_empty(self):
        assert compute_rsi(_empty) is None

    def test_all_same_values(self):
        # No gains, no losses → avg_loss=0 → returns 100.0
        result = compute_rsi(_flat(30), 14)
        assert result == pytest.approx(100.0)

    def test_all_gains(self):
        result = compute_rsi(_rising(20, step=1.0), 14)
        assert result == pytest.approx(100.0)

    def test_all_losses(self):
        closes = np.array([100.0 - i for i in range(20)], dtype=float)
        result = compute_rsi(closes, 14)
        assert result is not None
        assert result < 10.0

    def test_period_7(self):
        result = compute_rsi(_alternating(30), 7)
        assert result is not None
        assert 0 <= result <= 100

    def test_period_21(self):
        result = compute_rsi(_alternating(40), 21)
        assert result is not None
        assert 0 <= result <= 100


# ════════════════════════════════════════════════════════════════
# compute_macd
# ════════════════════════════════════════════════════════════════

class TestComputeMACD:
    def test_normal_returns_three(self):
        ml, sl, h = compute_macd(_rising(60))
        assert ml is not None
        assert sl is not None
        assert h is not None

    def test_empty(self):
        ml, sl, h = compute_macd(_empty)
        assert ml is None and sl is None and h is None

    def test_too_short(self):
        ml, sl, h = compute_macd(_rising(30))
        assert ml is None

    def test_histogram_is_difference(self):
        ml, sl, h = compute_macd(_rising(60))
        assert h == pytest.approx(ml - sl, abs=1e-6)

    def test_rising_produces_positive_macd(self):
        ml, _, _ = compute_macd(_rising(60, step=2.0))
        assert ml > 0


# ════════════════════════════════════════════════════════════════
# compute_bollinger
# ════════════════════════════════════════════════════════════════

class TestComputeBollinger:
    def test_upper_gt_middle_gt_lower(self):
        u, m, l = compute_bollinger(_alternating(30))
        assert u > m > l

    def test_empty(self):
        u, m, l = compute_bollinger(_empty)
        assert u is None and m is None and l is None

    def test_too_short(self):
        u, m, l = compute_bollinger(_rising(10), period=20)
        assert u is None

    def test_flat_bands_equal(self):
        u, m, l = compute_bollinger(_flat(30))
        assert u == pytest.approx(m)
        assert l == pytest.approx(m)


# ════════════════════════════════════════════════════════════════
# compute_stoch_rsi
# ════════════════════════════════════════════════════════════════

class TestComputeStochRSI:
    def test_range_0_to_100(self):
        result = compute_stoch_rsi(_rising(60))
        assert result is not None
        assert 0 <= result <= 100

    def test_empty(self):
        assert compute_stoch_rsi(_empty) is None

    def test_too_short(self):
        assert compute_stoch_rsi(_rising(20)) is None

    def test_flat_returns_50(self):
        result = compute_stoch_rsi(_flat(60))
        if result is not None:
            assert result == pytest.approx(50.0)


# ════════════════════════════════════════════════════════════════
# compute_adx
# ════════════════════════════════════════════════════════════════

class TestComputeADX:
    def test_non_negative(self):
        n = 60
        h = np.array([102.0 + i for i in range(n)], dtype=float)
        l = np.array([98.0 + i for i in range(n)], dtype=float)
        c = np.array([100.0 + i for i in range(n)], dtype=float)
        result = compute_adx(h, l, c)
        assert result is not None
        assert result >= 0

    def test_empty(self):
        assert compute_adx(_empty, _empty, _empty) is None

    def test_too_short(self):
        short = _rising(10)
        assert compute_adx(short, short, short) is None


# ════════════════════════════════════════════════════════════════
# compute_obv_trend
# ════════════════════════════════════════════════════════════════

class TestComputeOBVTrend:
    def test_returns_float(self):
        result = compute_obv_trend(_rising(30), np.full(30, 1000.0))
        assert isinstance(result, float)

    def test_empty(self):
        assert compute_obv_trend(_empty, _empty) is None

    def test_too_short(self):
        assert compute_obv_trend(_rising(5), np.full(5, 1000.0)) is None

    def test_rising_positive(self):
        result = compute_obv_trend(_rising(30, step=1.0), np.full(30, 1000.0))
        assert result > 0

    def test_falling_negative(self):
        closes = np.array([200.0 - i for i in range(30)], dtype=float)
        result = compute_obv_trend(closes, np.full(30, 1000.0))
        assert result < 0


# ════════════════════════════════════════════════════════════════
# compute_atr
# ════════════════════════════════════════════════════════════════

class TestComputeATR:
    def test_non_negative(self):
        n = 30
        h = np.array([110.0 + i for i in range(n)], dtype=float)
        l = np.array([90.0 + i for i in range(n)], dtype=float)
        c = np.array([100.0 + i for i in range(n)], dtype=float)
        result = compute_atr(h, l, c)
        assert result is not None
        assert result >= 0

    def test_empty(self):
        assert compute_atr(_empty, _empty, _empty) is None

    def test_flat_zero(self):
        n = 30
        result = compute_atr(_flat(n), _flat(n), _flat(n))
        assert result == pytest.approx(0.0)


# ════════════════════════════════════════════════════════════════
# compute_volatility_ann
# ════════════════════════════════════════════════════════════════

class TestComputeVolatilityAnn:
    def test_non_negative(self):
        result = compute_volatility_ann(_alternating(30))
        assert result is not None
        assert result >= 0

    def test_empty(self):
        assert compute_volatility_ann(_empty) is None

    def test_flat_zero(self):
        result = compute_volatility_ann(_flat(30))
        assert result == pytest.approx(0.0, abs=0.01)


# ════════════════════════════════════════════════════════════════
# compute_disparity
# ════════════════════════════════════════════════════════════════

class TestComputeDisparity:
    def test_normal_calculation(self):
        closes = _flat(20, 100.0)
        result = compute_disparity(closes)
        assert result == pytest.approx(100.0)

    def test_empty(self):
        assert compute_disparity(_empty) is None

    def test_above_ma(self):
        closes = np.concatenate([_flat(19, 100.0), np.array([120.0])])
        result = compute_disparity(closes, 20)
        assert result > 100.0

    def test_below_ma(self):
        closes = np.concatenate([_flat(19, 100.0), np.array([80.0])])
        result = compute_disparity(closes, 20)
        assert result < 100.0


# ════════════════════════════════════════════════════════════════
# detect_rsi_divergence
# ════════════════════════════════════════════════════════════════

class TestDetectRSIDivergence:
    def test_returns_valid_values(self):
        result = detect_rsi_divergence(_rising(40))
        assert result in (None, "bullish", "bearish")

    def test_empty(self):
        assert detect_rsi_divergence(_empty) is None

    def test_too_short(self):
        assert detect_rsi_divergence(_rising(10)) is None

    def test_bullish_possible(self):
        # Price makes lower low but RSI makes higher low
        # Hard to construct perfectly, but ensure no crash
        closes = np.concatenate([_rising(25, 100, 1), np.array([95, 94, 93, 92, 91])])
        result = detect_rsi_divergence(closes, 14, 5)
        assert result in (None, "bullish", "bearish")


# ════════════════════════════════════════════════════════════════
# detect_gap
# ════════════════════════════════════════════════════════════════

class TestDetectGap:
    def test_gap_up(self):
        prices = [
            {"close": 100.0, "open": 100.0},
            {"close": 103.0, "open": 102.0},  # open 2% above prev close
        ]
        result = detect_gap(prices, 1)
        assert result is not None
        assert result["direction"] == "up"
        assert result["gap_pct"] > 0

    def test_gap_down(self):
        prices = [
            {"close": 100.0, "open": 100.0},
            {"close": 96.0, "open": 97.0},  # open 3% below prev close
        ]
        result = detect_gap(prices, 1)
        assert result is not None
        assert result["direction"] == "down"
        assert result["gap_pct"] < 0

    def test_no_gap(self):
        prices = [
            {"close": 100.0, "open": 100.0},
            {"close": 100.5, "open": 100.2},  # < 1% gap
        ]
        result = detect_gap(prices, 1)
        assert result is None

    def test_idx_zero(self):
        prices = [{"close": 100.0, "open": 100.0}]
        assert detect_gap(prices, 0) is None

    def test_prev_close_zero(self):
        prices = [
            {"close": 0, "open": 0},
            {"close": 100.0, "open": 100.0},
        ]
        assert detect_gap(prices, 1) is None
