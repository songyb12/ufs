"""Tests for engine/signal.py — generate_signal and run_signal_pipeline."""

import pytest

from app.engine.leverage import LeverageScore
from app.engine.macro_score import MacroScore
from app.engine.signal import generate_signal, run_signal_pipeline
from app.engine.technical import TechnicalScore
from app.models import SignalLevel


def _make_scores(tech_total, lev_total, macro_total):
    """Create score objects with given totals."""
    return (
        TechnicalScore(total=tech_total),
        LeverageScore(total=lev_total),
        MacroScore(total=macro_total),
    )


class TestGenerateSignal:
    def test_all_positive_green(self):
        t, l, m = _make_scores(0.8, 0.8, 0.8)
        result = generate_signal(t, l, m)
        assert result.signal == SignalLevel.GREEN
        assert result.score >= 0.3

    def test_all_negative_red(self):
        t, l, m = _make_scores(-0.8, -0.8, -0.8)
        result = generate_signal(t, l, m)
        assert result.signal == SignalLevel.RED
        assert result.score <= -0.3

    def test_mixed_scores_yellow(self):
        t, l, m = _make_scores(0.5, -0.3, 0.0)
        result = generate_signal(t, l, m)
        assert result.signal == SignalLevel.YELLOW

    def test_boundary_exactly_0_3_green(self):
        """Score exactly 0.3 → GREEN."""
        # Need: tech*0.4 + lev*0.3 + macro*0.3 = 0.3
        # 0.75*0.4 + 0.0*0.3 + 0.0*0.3 = 0.3
        t, l, m = _make_scores(0.75, 0.0, 0.0)
        result = generate_signal(t, l, m)
        assert result.signal == SignalLevel.GREEN

    def test_boundary_exactly_minus_0_3_yellow(self):
        """Score exactly -0.3 → still RED (<=)."""
        # -0.75*0.4 + 0*0.3 + 0*0.3 = -0.3
        t, l, m = _make_scores(-0.75, 0.0, 0.0)
        result = generate_signal(t, l, m)
        assert result.signal == SignalLevel.RED

    def test_score_in_range(self):
        t, l, m = _make_scores(1.0, 1.0, 1.0)
        result = generate_signal(t, l, m)
        assert -1.0 <= result.score <= 1.0

    def test_weights_correct(self):
        """Verify weighted sum: tech*0.4 + lev*0.3 + macro*0.3."""
        t, l, m = _make_scores(1.0, 0.0, 0.0)
        result = generate_signal(t, l, m)
        assert abs(result.score - 0.4) < 0.01

    def test_action_text_green(self):
        t, l, m = _make_scores(0.8, 0.8, 0.8)
        result = generate_signal(t, l, m)
        assert "매수" in result.action or "홀드" in result.action

    def test_action_text_red(self):
        t, l, m = _make_scores(-0.8, -0.8, -0.8)
        result = generate_signal(t, l, m)
        assert "회피" in result.action or "매도" in result.action

    def test_details_contains_weights(self):
        t, l, m = _make_scores(0.0, 0.0, 0.0)
        result = generate_signal(t, l, m)
        assert "weights" in result.details
        assert result.details["weights"]["technical"] == 0.4

    def test_risks_empty_by_default(self):
        t, l, m = _make_scores(0.0, 0.0, 0.0)
        result = generate_signal(t, l, m)
        assert result.risks == []


class TestRunSignalPipeline:
    def test_pipeline_returns_signal_result(self, mock_collectors):
        result = run_signal_pipeline()
        assert result.signal in (SignalLevel.GREEN, SignalLevel.YELLOW, SignalLevel.RED)
        assert -1.0 <= result.score <= 1.0

    def test_pipeline_calls_collectors(self, mock_collectors):
        run_signal_pipeline()
        mock_collectors["collect_all_prices"].assert_called_once()
        mock_collectors["collect_all_macro"].assert_called_once()
        mock_collectors["collect_sentiment"].assert_called_once()

    def test_pipeline_saves_signal(self, mock_collectors):
        run_signal_pipeline()
        mock_collectors["save_signal"].assert_called_once()
