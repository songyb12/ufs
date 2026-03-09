"""Tests for app.utils — shared utilities."""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.utils.formatting import fmt_float
from app.utils.retry import async_retry


# ── fmt_float ──


class TestFmtFloat:
    def test_normal(self):
        assert fmt_float(3.14159) == "3.1"

    def test_none(self):
        assert fmt_float(None) == "N/A"

    def test_zero(self):
        assert fmt_float(0.0) == "0.0"

    def test_negative(self):
        assert fmt_float(-5.678) == "-5.7"

    def test_custom_decimals(self):
        assert fmt_float(3.14159, decimals=3) == "3.142"

    def test_integer_value(self):
        assert fmt_float(42, decimals=2) == "42.00"


# ── async_retry ──


class TestAsyncRetry:
    def test_succeeds_first_try(self):
        call_count = 0

        @async_retry(max_attempts=3, base_delay=0.01)
        async def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(fn())
        assert result == "ok"
        assert call_count == 1

    def test_retries_then_succeeds(self):
        call_count = 0

        @async_retry(max_attempts=3, base_delay=0.01)
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(fn())
        assert result == "ok"
        assert call_count == 3

    def test_exhausts_retries(self):
        call_count = 0

        @async_retry(max_attempts=2, base_delay=0.01)
        async def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fail")

        import pytest
        with pytest.raises(ValueError, match="always fail"):
            asyncio.get_event_loop().run_until_complete(fn())
        assert call_count == 2

    def test_only_catches_specified_exceptions(self):
        @async_retry(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        async def fn():
            raise TypeError("wrong type")

        import pytest
        with pytest.raises(TypeError):
            asyncio.get_event_loop().run_until_complete(fn())

    def test_preserves_function_name(self):
        @async_retry()
        async def my_function():
            return 42

        assert my_function.__name__ == "my_function"
