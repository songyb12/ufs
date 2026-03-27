"""Tests for app.utils.retention — data pruning logic."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest


class MockConfig:
    RETENTION_PRICE_DAYS = 365
    RETENTION_SIGNAL_DAYS = 180
    RETENTION_PIPELINE_RUNS_DAYS = 90
    RETENTION_NEWS_DAYS = 30


def _make_db(rowcount: int = 0):
    """Create a mock async DB with execute returning a cursor with given rowcount."""
    cursor = MagicMock()
    cursor.rowcount = rowcount
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=cursor)
    mock_db.commit = AsyncMock()
    return mock_db


class TestRunRetention:
    @pytest.mark.asyncio
    async def test_no_rows_deleted_returns_empty_dict(self):
        """All tables have 0 rows to delete → returns empty results dict."""
        mock_db = _make_db(rowcount=0)

        with patch("app.utils.retention.get_db", AsyncMock(return_value=mock_db)):
            from app.utils.retention import run_retention
            result = await run_retention(MockConfig())

        assert isinstance(result, dict)
        assert len(result) == 0  # No non-zero deletes

    @pytest.mark.asyncio
    async def test_deleted_rows_stored_in_result(self):
        """Table with deleted rows appears in return dict."""
        mock_db = _make_db(rowcount=50)

        with patch("app.utils.retention.get_db", AsyncMock(return_value=mock_db)):
            from app.utils.retention import run_retention
            result = await run_retention(MockConfig())

        # All tables deleted 50 rows → all entries in result
        from app.utils.retention import RETENTION_TARGETS
        assert len(result) == len(RETENTION_TARGETS)
        assert all(v == 50 for v in result.values())

    @pytest.mark.asyncio
    async def test_table_error_is_skipped_not_raised(self):
        """Exception on a table is logged and skipped, not propagated."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=Exception("table missing"))
        mock_db.commit = AsyncMock()

        with patch("app.utils.retention.get_db", AsyncMock(return_value=mock_db)):
            from app.utils.retention import run_retention
            result = await run_retention(MockConfig())

        assert isinstance(result, dict)
        assert len(result) == 0  # All tables errored → nothing stored

    @pytest.mark.asyncio
    async def test_vacuum_triggered_when_many_rows_deleted(self):
        """VACUUM is called when total deleted > 1000."""
        execute_calls = []

        async def mock_execute(sql, params=None):
            execute_calls.append(sql)
            cursor = MagicMock()
            cursor.rowcount = 100  # 100 * 21 tables = 2100 > 1000
            return cursor

        mock_db = MagicMock()
        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.utils.retention.get_db", AsyncMock(return_value=mock_db)):
            from app.utils.retention import run_retention
            await run_retention(MockConfig())

        assert any("VACUUM" in str(c) for c in execute_calls), "VACUUM should be called"

    @pytest.mark.asyncio
    async def test_vacuum_not_triggered_when_few_rows(self):
        """VACUUM is skipped when total deleted ≤ 1000."""
        execute_calls = []

        async def mock_execute(sql, params=None):
            execute_calls.append(sql)
            cursor = MagicMock()
            cursor.rowcount = 10  # 10 * 21 tables = 210 < 1000
            return cursor

        mock_db = MagicMock()
        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()

        with patch("app.utils.retention.get_db", AsyncMock(return_value=mock_db)):
            from app.utils.retention import run_retention
            await run_retention(MockConfig())

        vacuum_calls = [c for c in execute_calls if "VACUUM" in str(c)]
        assert len(vacuum_calls) == 0, "VACUUM should NOT be called"
