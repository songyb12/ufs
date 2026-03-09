"""Tests for app.risk.correlation — return correlation analysis."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd

from app.risk.correlation import (
    compute_return_correlation,
    check_concurrent_signals,
)


# ── compute_return_correlation ──


def _make_price_df(prices):
    """Build a simple DataFrame with a 'close' column."""
    return pd.DataFrame({"close": prices})


class TestComputeReturnCorrelation:
    def test_empty_input(self):
        assert compute_return_correlation({}) == {}

    def test_single_symbol(self):
        prices = list(range(100, 200))
        assert compute_return_correlation({"A": _make_price_df(prices)}) == {}

    def test_insufficient_data(self):
        # 60-window needs > 60 closes
        short = list(range(50))
        assert compute_return_correlation({
            "A": _make_price_df(short),
            "B": _make_price_df(short),
        }) == {}

    def test_two_identical_series(self):
        # Identical series → correlation ≈ 1.0
        np.random.seed(42)
        prices = np.cumsum(np.random.randn(100)) + 100
        result = compute_return_correlation({
            "A": _make_price_df(prices),
            "B": _make_price_df(prices),
        }, window=30)
        assert abs(result["A"]["B"] - 1.0) < 0.01
        assert result["A"]["A"] == 1.0

    def test_two_uncorrelated_series(self):
        np.random.seed(42)
        a_prices = np.cumsum(np.random.randn(200)) + 100
        np.random.seed(123)
        b_prices = np.cumsum(np.random.randn(200)) + 100
        result = compute_return_correlation({
            "A": _make_price_df(a_prices),
            "B": _make_price_df(b_prices),
        }, window=60)
        # Uncorrelated → |corr| should be < 0.5
        assert abs(result["A"]["B"]) < 0.5

    def test_inverse_series(self):
        np.random.seed(42)
        rets = np.random.randn(200) * 0.02
        a_prices = 100 * np.cumprod(1 + rets)
        b_prices = 100 * np.cumprod(1 - rets)
        result = compute_return_correlation({
            "A": _make_price_df(a_prices),
            "B": _make_price_df(b_prices),
        }, window=60)
        # Inverse → correlation ≈ -1.0
        assert result["A"]["B"] < -0.9

    def test_none_df_ignored(self):
        np.random.seed(42)
        prices = np.cumsum(np.random.randn(100)) + 100
        result = compute_return_correlation({
            "A": _make_price_df(prices),
            "B": None,
        })
        assert result == {}

    def test_empty_df_ignored(self):
        np.random.seed(42)
        prices = np.cumsum(np.random.randn(100)) + 100
        result = compute_return_correlation({
            "A": _make_price_df(prices),
            "B": pd.DataFrame(),
        })
        assert result == {}

    def test_missing_close_column(self):
        np.random.seed(42)
        prices = np.cumsum(np.random.randn(100)) + 100
        result = compute_return_correlation({
            "A": _make_price_df(prices),
            "B": pd.DataFrame({"open": prices}),  # no 'close'
        })
        assert result == {}

    def test_symmetric(self):
        np.random.seed(42)
        a = np.cumsum(np.random.randn(100)) + 100
        np.random.seed(99)
        b = np.cumsum(np.random.randn(100)) + 100
        result = compute_return_correlation({
            "A": _make_price_df(a),
            "B": _make_price_df(b),
        }, window=30)
        assert abs(result["A"]["B"] - result["B"]["A"]) < 0.0001

    def test_three_symbols(self):
        np.random.seed(42)
        a = np.cumsum(np.random.randn(100)) + 100
        b = np.cumsum(np.random.randn(100)) + 200
        c = np.cumsum(np.random.randn(100)) + 150
        result = compute_return_correlation({
            "A": _make_price_df(a),
            "B": _make_price_df(b),
            "C": _make_price_df(c),
        }, window=30)
        assert "A" in result
        assert "B" in result["A"]
        assert "C" in result["A"]
        assert result["A"]["A"] == 1.0
        assert result["B"]["B"] == 1.0
        assert result["C"]["C"] == 1.0


# ── check_concurrent_signals ──


class TestCheckConcurrentSignals:
    def test_empty(self):
        assert check_concurrent_signals([], {}) == []

    def test_single_symbol(self):
        assert check_concurrent_signals(["A"], {"A": {"A": 1.0}}) == []

    def test_high_correlation_warning(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.85},
            "B": {"A": 0.85, "B": 1.0},
        }
        warnings = check_concurrent_signals(["A", "B"], matrix, threshold=0.8)
        assert len(warnings) == 1
        assert "A-B" in warnings[0]
        assert "concentrated risk" in warnings[0]

    def test_low_correlation_no_warning(self):
        matrix = {
            "A": {"A": 1.0, "B": 0.3},
            "B": {"A": 0.3, "B": 1.0},
        }
        warnings = check_concurrent_signals(["A", "B"], matrix, threshold=0.8)
        assert len(warnings) == 0

    def test_missing_pair_no_warning(self):
        # Symbol not in matrix → default 0
        warnings = check_concurrent_signals(["A", "B"], {}, threshold=0.8)
        assert len(warnings) == 0

    def test_negative_correlation(self):
        matrix = {
            "A": {"A": 1.0, "B": -0.9},
            "B": {"A": -0.9, "B": 1.0},
        }
        warnings = check_concurrent_signals(["A", "B"], matrix, threshold=0.8)
        # abs(-0.9) >= 0.8 → warning
        assert len(warnings) == 1

    def test_no_duplicate_warnings(self):
        matrix = {
            "A": {"B": 0.9, "C": 0.85},
            "B": {"A": 0.9, "C": 0.2},
            "C": {"A": 0.85, "B": 0.2},
        }
        warnings = check_concurrent_signals(["A", "B", "C"], matrix, threshold=0.8)
        assert len(warnings) == 2  # A-B and A-C
