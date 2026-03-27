"""Tests for scheduler.py — market hours detection and scheduler lifecycle."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from app.scheduler import (
    US_EASTERN,
    is_extended_hours,
    is_market_hours,
    start_scheduler,
    stop_scheduler,
)


class TestIsMarketHours:
    def test_weekday_10am_et_true(self):
        """Wednesday 10:00 ET → market open."""
        dt = datetime(2026, 3, 25, 10, 0, tzinfo=US_EASTERN)  # Wednesday
        assert is_market_hours(dt) is True

    def test_weekday_930am_et_true(self):
        """Exact market open 9:30 ET → True."""
        dt = datetime(2026, 3, 25, 9, 30, tzinfo=US_EASTERN)
        assert is_market_hours(dt) is True

    def test_weekday_4pm_et_true(self):
        """Exact market close 16:00 ET → True (inclusive)."""
        dt = datetime(2026, 3, 25, 16, 0, tzinfo=US_EASTERN)
        assert is_market_hours(dt) is True

    def test_saturday_false(self):
        """Saturday 12:00 ET → False."""
        dt = datetime(2026, 3, 28, 12, 0, tzinfo=US_EASTERN)  # Saturday
        assert is_market_hours(dt) is False

    def test_sunday_false(self):
        """Sunday 10:00 ET → False."""
        dt = datetime(2026, 3, 29, 10, 0, tzinfo=US_EASTERN)  # Sunday
        assert is_market_hours(dt) is False

    def test_weekday_8pm_et_false(self):
        """Wednesday 20:00 ET → market closed."""
        dt = datetime(2026, 3, 25, 20, 0, tzinfo=US_EASTERN)
        assert is_market_hours(dt) is False

    def test_weekday_before_open_false(self):
        """Wednesday 9:00 ET → before market open."""
        dt = datetime(2026, 3, 25, 9, 0, tzinfo=US_EASTERN)
        assert is_market_hours(dt) is False


class TestIsExtendedHours:
    def test_premarket_5am_true(self):
        """Wednesday 5:00 ET → pre-market."""
        dt = datetime(2026, 3, 25, 5, 0, tzinfo=US_EASTERN)
        assert is_extended_hours(dt) is True

    def test_afterhours_17_true(self):
        """Wednesday 17:00 ET → after-hours."""
        dt = datetime(2026, 3, 25, 17, 0, tzinfo=US_EASTERN)
        assert is_extended_hours(dt) is True

    def test_regular_hours_false(self):
        """Wednesday 12:00 ET → regular hours, not extended."""
        dt = datetime(2026, 3, 25, 12, 0, tzinfo=US_EASTERN)
        assert is_extended_hours(dt) is False

    def test_weekend_false(self):
        """Saturday 5:00 ET → weekend, no extended hours."""
        dt = datetime(2026, 3, 28, 5, 0, tzinfo=US_EASTERN)
        assert is_extended_hours(dt) is False


class TestSchedulerLifecycle:
    def test_start_and_stop(self):
        """start_scheduler and stop_scheduler run without error."""
        start_scheduler()
        stop_scheduler()

    def test_stop_when_not_started(self):
        """stop_scheduler is safe to call when scheduler is None."""
        stop_scheduler()  # Should not raise
