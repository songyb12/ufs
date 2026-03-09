"""Tests for app.screening.scanner — DynamicScreener trigger detection."""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.screening.scanner import DynamicScreener


def _make_df(closes, volumes=None, n=30, days_back_start=0):
    """Create a DataFrame mimicking price_history rows."""
    dates = pd.date_range(end="2026-03-10", periods=n, freq="B")
    if closes is None:
        closes = [100 + i * 0.5 for i in range(n)]
    if len(closes) < n:
        # Pad front
        pad = [closes[0]] * (n - len(closes))
        closes = pad + closes
    if volumes is None:
        volumes = [1_000_000] * n
    if len(volumes) < n:
        pad = [volumes[0]] * (n - len(volumes))
        volumes = pad + volumes
    # Create high/low around close
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]
    df = pd.DataFrame({
        "trade_date": dates[-n:],
        "close": closes[-n:],
        "high": highs[-n:],
        "low": lows[-n:],
        "open": closes[-n:],
        "volume": volumes[-n:],
    })
    return df


class TestVolumeSpikeDetection:
    def setup_method(self):
        self.scanner = DynamicScreener()

    def test_no_spike_normal_volume(self):
        """Normal volume should not trigger."""
        df = _make_df(None, volumes=[1_000_000] * 30, n=30)
        results = self.scanner._check_volume_spike(df, "TEST", days_back=5)
        assert results == []

    def test_spike_detected(self):
        """Volume > 3x avg should trigger."""
        vols = [1_000_000] * 25 + [5_000_000] * 5
        df = _make_df(None, volumes=vols, n=30)
        results = self.scanner._check_volume_spike(df, "TEST", days_back=5)
        assert len(results) > 0
        for r in results:
            assert r["trigger_type"] == "volume_spike"
            assert r["trigger_value"] > 3.0
            assert r["symbol"] == "TEST"

    def test_spike_just_below_threshold(self):
        """Volume at 2.9x should NOT trigger (threshold is 3x)."""
        vols = [1_000_000] * 25 + [2_900_000] * 5
        df = _make_df(None, volumes=vols, n=30)
        results = self.scanner._check_volume_spike(df, "TEST", days_back=5)
        assert results == []

    def test_insufficient_data(self):
        """Less than 21 rows should return empty."""
        df = _make_df(None, n=15)
        results = self.scanner._check_volume_spike(df, "TEST", days_back=5)
        assert results == []

    def test_zero_avg_volume(self):
        """Zero average volume should not crash."""
        vols = [0] * 25 + [100] * 5
        df = _make_df(None, volumes=vols, n=30)
        results = self.scanner._check_volume_spike(df, "TEST", days_back=5)
        # Should not crash, may or may not have results depending on avg
        assert isinstance(results, list)

    def test_missing_volume_column(self):
        """DataFrame without volume column should return empty."""
        df = _make_df(None, n=30)
        df = df.drop(columns=["volume"])
        results = self.scanner._check_volume_spike(df, "TEST", days_back=5)
        assert results == []

    def test_result_structure(self):
        """Verify result dict has all required keys."""
        vols = [1_000_000] * 25 + [10_000_000] * 5
        df = _make_df(None, volumes=vols, n=30)
        results = self.scanner._check_volume_spike(df, "SYM1", days_back=5)
        assert len(results) > 0
        r = results[0]
        assert "symbol" in r
        assert "detected_date" in r
        assert "trigger_type" in r
        assert "trigger_value" in r
        assert "trigger_description" in r


class TestNewHighDetection:
    def setup_method(self):
        self.scanner = DynamicScreener()

    def test_new_high_detected(self):
        """Price breaking all-time high should trigger."""
        closes = list(range(50, 80))  # 30 values, steadily rising
        closes[-1] = 200  # Spike to new high on last day
        df = _make_df(closes, n=30)
        results = self.scanner._check_new_high(df, "TEST", days_back=1)
        assert len(results) > 0
        assert results[0]["trigger_type"] == "new_high"

    def test_no_new_high(self):
        """Declining prices should not trigger."""
        closes = list(range(100, 70, -1))  # Declining
        df = _make_df(closes, n=30)
        results = self.scanner._check_new_high(df, "TEST", days_back=5)
        assert results == []

    def test_flat_prices(self):
        """Flat prices should not trigger."""
        closes = [100.0] * 30
        df = _make_df(closes, n=30)
        results = self.scanner._check_new_high(df, "TEST", days_back=5)
        assert results == []

    def test_insufficient_data(self):
        """Less than 20 rows should return empty."""
        df = _make_df(None, n=15)
        results = self.scanner._check_new_high(df, "TEST", days_back=5)
        assert results == []


class TestBreakoutDetection:
    def setup_method(self):
        self.scanner = DynamicScreener()

    def test_bb_breakout_detected(self):
        """Price above BB upper with high volume should trigger."""
        closes = [100.0] * 25  # Stable for 25 days
        closes += [120.0, 130.0, 140.0, 150.0, 160.0]  # Big breakout
        vols = [1_000_000] * 25 + [3_000_000] * 5  # 3x volume
        df = _make_df(closes, volumes=vols, n=30)
        results = self.scanner._check_breakout(df, "TEST", days_back=5)
        # With std ~0 for first 25 days, BB upper would be near 100
        # so 120+ should break out
        assert len(results) > 0
        assert results[0]["trigger_type"] == "breakout"

    def test_no_breakout_normal(self):
        """Normal price within BB should not trigger."""
        closes = [100 + np.sin(i / 3) for i in range(30)]  # Gentle oscillation
        df = _make_df(closes, n=30)
        results = self.scanner._check_breakout(df, "TEST", days_back=5)
        assert results == []

    def test_insufficient_data(self):
        """Less than 21 rows should return empty."""
        df = _make_df(None, n=15)
        results = self.scanner._check_breakout(df, "TEST", days_back=5)
        assert results == []


class TestCapitulationDetection:
    def setup_method(self):
        self.scanner = DynamicScreener()

    def test_capitulation_detected(self):
        """Volume > 2x + price drop > 3% should trigger."""
        closes = [100.0] * 25 + [96.0, 95.0, 94.0, 93.0, 92.0]  # Declining
        vols = [1_000_000] * 25 + [3_000_000] * 5  # 3x volume
        df = _make_df(closes, volumes=vols, n=30)
        results = self.scanner._check_capitulation(df, "TEST", days_back=5)
        assert len(results) > 0
        assert results[0]["trigger_type"] == "capitulation"

    def test_no_capitulation_price_up(self):
        """Volume spike with rising prices should not trigger."""
        closes = [100.0] * 25 + [105.0, 106.0, 107.0, 108.0, 109.0]
        vols = [1_000_000] * 25 + [3_000_000] * 5
        df = _make_df(closes, volumes=vols, n=30)
        results = self.scanner._check_capitulation(df, "TEST", days_back=5)
        assert results == []

    def test_no_capitulation_low_volume(self):
        """Price drop with normal volume should not trigger."""
        closes = [100.0] * 25 + [90.0, 89.0, 88.0, 87.0, 86.0]
        vols = [1_000_000] * 30  # Normal volume
        df = _make_df(closes, volumes=vols, n=30)
        results = self.scanner._check_capitulation(df, "TEST", days_back=5)
        assert results == []

    def test_insufficient_data(self):
        """Less than 25 rows should return empty."""
        df = _make_df(None, n=20)
        results = self.scanner._check_capitulation(df, "TEST", days_back=5)
        assert results == []

    def test_zero_close_5d_ago(self):
        """Zero close price 5 days ago should not crash."""
        closes = [0.0] * 25 + [1.0, 1.0, 1.0, 1.0, 1.0]
        vols = [1_000_000] * 25 + [3_000_000] * 5
        df = _make_df(closes, volumes=vols, n=30)
        results = self.scanner._check_capitulation(df, "TEST", days_back=5)
        assert isinstance(results, list)

    def test_nan_close_5d_ago(self):
        """NaN close should not crash."""
        closes = [100.0] * 30
        vols = [1_000_000] * 25 + [3_000_000] * 5
        df = _make_df(closes, volumes=vols, n=30)
        # Force NaN at specific position
        df.loc[df.index[20], "close"] = np.nan
        results = self.scanner._check_capitulation(df, "TEST", days_back=5)
        assert isinstance(results, list)
