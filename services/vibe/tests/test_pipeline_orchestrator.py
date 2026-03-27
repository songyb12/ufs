"""Regression tests for PipelineOrchestrator bug fixes (Session 4)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.pipeline.orchestrator import PipelineOrchestrator


def _make_config():
    cfg = MagicMock()
    cfg.LLM_API_KEY = ""
    cfg.LLM_RED_TEAM_ENABLED = False
    cfg.RED_TEAM_ENABLED = False
    cfg.PORTFOLIO_TOTAL = 100_000_000
    return cfg


class TestStoreSignalsIsolation:
    """Regression: _store_signals exception must not overwrite 'completed' status.

    Session 4 P1/P2 bug: _store_signals() failure after update_pipeline_run("completed")
    was calling update_pipeline_run("failed") via the outer except, overwriting the status.
    Fix: _store_signals wrapped in its own inner try/except.
    """

    @pytest.mark.asyncio
    async def test_store_signals_failure_preserves_completed_status(self):
        config = _make_config()
        registry = MagicMock()
        orch = PipelineOrchestrator(config, registry)
        orch.stages = []  # No stages — pipeline reaches 'completed' immediately

        update_calls: list[tuple] = []

        async def mock_insert_pipeline_run(run_id, market, run_type):
            pass

        async def mock_get_symbol_names(market):
            return {}

        async def mock_update_pipeline_run(run_id, status, stages, error=None):
            update_calls.append(status)

        async def mock_store_signals_raises(context):
            raise RuntimeError("Simulated storage failure")

        with (
            patch("app.pipeline.orchestrator.repo.insert_pipeline_run", mock_insert_pipeline_run),
            patch("app.pipeline.orchestrator.repo.get_symbol_names", mock_get_symbol_names),
            patch("app.pipeline.orchestrator.repo.update_pipeline_run", mock_update_pipeline_run),
            patch.object(orch, "_store_signals", mock_store_signals_raises),
        ):
            context = await orch.run("KR", ["TEST"], "manual")

        # Pipeline must report completed
        assert context["status"] == "completed"
        # update_pipeline_run must have been called with "completed"
        assert "completed" in update_calls
        # "failed" must NOT appear after the "completed" call
        last_call = update_calls[-1]
        assert last_call == "completed", (
            f"Last update_pipeline_run call was '{last_call}', expected 'completed'. "
            "store_signals failure is incorrectly overwriting pipeline status."
        )

    @pytest.mark.asyncio
    async def test_store_signals_success_preserves_completed_status(self):
        """Sanity check: normal execution also ends with 'completed'."""
        config = _make_config()
        registry = MagicMock()
        orch = PipelineOrchestrator(config, registry)
        orch.stages = []

        update_calls: list[str] = []

        async def mock_insert(*_): pass
        async def mock_names(*_): return {}
        async def mock_update(run_id, status, stages, error=None):
            update_calls.append(status)
        async def mock_store(context): pass

        with (
            patch("app.pipeline.orchestrator.repo.insert_pipeline_run", mock_insert),
            patch("app.pipeline.orchestrator.repo.get_symbol_names", mock_names),
            patch("app.pipeline.orchestrator.repo.update_pipeline_run", mock_update),
            patch.object(orch, "_store_signals", mock_store),
        ):
            context = await orch.run("KR", [], "scheduled")

        assert context["status"] == "completed"
        assert update_calls[-1] == "completed"
