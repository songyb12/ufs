"""Tests for app.backtesting.tracker — SignalPerformanceTracker logic."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.backtesting.tracker import SignalPerformanceTracker


class TestAddTradingDays:
    """Test the _add_trading_days static method."""

    def test_add_1_trading_day(self):
        result = SignalPerformanceTracker._add_trading_days("2026-03-03", 1)
        # 1 trading day ≈ 1.4 cal days + 1 = 2 calendar days
        assert result == "2026-03-05"

    def test_add_5_trading_days(self):
        result = SignalPerformanceTracker._add_trading_days("2026-03-03", 5)
        # 5 * 1.4 + 1 = 8 calendar days → 2026-03-11
        assert result == "2026-03-11"

    def test_add_20_trading_days(self):
        result = SignalPerformanceTracker._add_trading_days("2026-03-03", 20)
        # 20 * 1.4 + 1 = 29 calendar days → 2026-04-01
        assert result == "2026-04-01"

    def test_add_0_trading_days(self):
        result = SignalPerformanceTracker._add_trading_days("2026-03-10", 0)
        # 0 * 1.4 + 1 = 1 calendar day
        assert result == "2026-03-11"

    def test_cross_month_boundary(self):
        result = SignalPerformanceTracker._add_trading_days("2026-01-29", 5)
        # Should cross into February
        assert result.startswith("2026-02")

    def test_cross_year_boundary(self):
        result = SignalPerformanceTracker._add_trading_days("2025-12-29", 5)
        # Should cross into January 2026
        assert result.startswith("2026-01")

    def test_returns_string_format(self):
        result = SignalPerformanceTracker._add_trading_days("2026-06-15", 10)
        # Should be in YYYY-MM-DD format
        parts = result.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2
        assert len(parts[2]) == 2

    def test_large_trading_days(self):
        """252 trading days ≈ 1 year."""
        result = SignalPerformanceTracker._add_trading_days("2026-01-01", 252)
        # 252 * 1.4 + 1 = 354 calendar days → roughly Dec 2026
        assert result.startswith("2026-12") or result.startswith("2027-")

    def test_consistency(self):
        """More trading days = later date."""
        d1 = SignalPerformanceTracker._add_trading_days("2026-03-01", 1)
        d5 = SignalPerformanceTracker._add_trading_days("2026-03-01", 5)
        d20 = SignalPerformanceTracker._add_trading_days("2026-03-01", 20)
        assert d1 < d5 < d20


class TestTrackerInit:
    """Test SignalPerformanceTracker initialization."""

    def test_init(self):
        tracker = SignalPerformanceTracker()
        assert hasattr(tracker, "create_performance_record")
        assert hasattr(tracker, "track_pending")
        assert hasattr(tracker, "get_hit_rate_summary")
