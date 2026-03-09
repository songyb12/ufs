"""Tests for app.indicators.fear_gauge — fear phase classification."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.indicators.fear_gauge import (
    compute_fear_gauge,
    _compute_metrics,
    _classify_phase,
    PHASE_LABELS,
)


# ── Helpers ──

def _macro_history(vix_values):
    """Build macro_history from a list of VIX values."""
    return [{"vix": v, "indicator_date": f"2025-01-{i+1:02d}"}
            for i, v in enumerate(vix_values)]


def _sentiment_history(fg_values, pcr=None, vts=None):
    """Build sentiment_history from F&G values."""
    result = []
    for i, fg in enumerate(fg_values):
        row = {"fear_greed_index": fg}
        if pcr is not None:
            row["put_call_ratio"] = pcr
        if vts is not None:
            row["vix_term_structure"] = vts
        result.append(row)
    return result


# ── PHASE_LABELS ──


class TestPhaseLabels:
    def test_all_phases_present(self):
        for phase in ("calm", "initial_panic", "peak_fear", "post_peak"):
            assert phase in PHASE_LABELS
            assert "en" in PHASE_LABELS[phase]
            assert "kr" in PHASE_LABELS[phase]
            assert "action_kr" in PHASE_LABELS[phase]


# ── _compute_metrics ──


class TestComputeMetrics:
    def test_empty_inputs(self):
        m = _compute_metrics([], [])
        assert m["vix_current"] is None
        assert m["fg_current"] is None
        assert m["put_call_spike"] is False
        assert m["backwardation_streak"] == 0

    def test_vix_current(self):
        macro = _macro_history([15, 16, 17, 18, 19, 20])
        m = _compute_metrics(macro, [])
        assert m["vix_current"] == 20

    def test_vix_velocity(self):
        # 6 values: velocity = (last - first) / first
        vix = [20, 21, 22, 23, 24, 30]
        macro = _macro_history(vix)
        m = _compute_metrics(macro, [])
        assert m["vix_velocity_5d"] is not None
        # (30 - 20) / 20 = 0.5
        assert abs(m["vix_velocity_5d"] - 0.5) < 0.01

    def test_vix_acceleration(self):
        # 11 values needed
        vix = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 35]
        macro = _macro_history(vix)
        m = _compute_metrics(macro, [])
        assert m["vix_acceleration"] is not None

    def test_fg_current(self):
        sent = _sentiment_history([45, 50, 55, 60, 65, 70])
        m = _compute_metrics([], sent)
        assert m["fg_current"] == 70

    def test_fg_momentum_5d(self):
        fg = [50, 48, 46, 44, 42, 30]
        sent = _sentiment_history(fg)
        m = _compute_metrics([], sent)
        assert m["fg_momentum_5d"] == 30 - 50  # -20

    def test_fg_momentum_10d(self):
        fg = list(range(60, 49, -1))  # 60, 59, ..., 50 (11 values)
        sent = _sentiment_history(fg)
        m = _compute_metrics([], sent)
        assert m["fg_momentum_10d"] == 50 - 60  # -10

    def test_put_call_spike(self):
        sent = _sentiment_history([50], pcr=1.3)
        m = _compute_metrics([], sent)
        assert m["put_call_spike"] is True

    def test_put_call_no_spike(self):
        sent = _sentiment_history([50], pcr=0.8)
        m = _compute_metrics([], sent)
        assert m["put_call_spike"] is False

    def test_backwardation_streak(self):
        sent = [
            {"fear_greed_index": 30, "vix_term_structure": "contango"},
            {"fear_greed_index": 28, "vix_term_structure": "backwardation"},
            {"fear_greed_index": 25, "vix_term_structure": "backwardation"},
            {"fear_greed_index": 22, "vix_term_structure": "backwardation"},
        ]
        m = _compute_metrics([], sent)
        assert m["backwardation_streak"] == 3

    def test_backwardation_streak_broken(self):
        sent = [
            {"fear_greed_index": 30, "vix_term_structure": "backwardation"},
            {"fear_greed_index": 28, "vix_term_structure": "contango"},
            {"fear_greed_index": 25, "vix_term_structure": "backwardation"},
        ]
        m = _compute_metrics([], sent)
        assert m["backwardation_streak"] == 1


# ── _classify_phase ──


class TestClassifyPhase:
    def test_missing_vix_defaults_calm(self):
        phase, conf = _classify_phase({"vix_current": None, "fg_current": 50})
        assert phase == "calm"
        assert conf == 0.3

    def test_missing_fg_defaults_calm(self):
        phase, conf = _classify_phase({"vix_current": 15, "fg_current": None})
        assert phase == "calm"
        assert conf == 0.3

    def test_calm_low_vix_high_fg(self):
        phase, conf = _classify_phase({
            "vix_current": 14,
            "fg_current": 55,
            "vix_velocity_5d": 0.02,
        })
        assert phase == "calm"

    def test_initial_panic(self):
        phase, _ = _classify_phase({
            "vix_current": 25,
            "fg_current": 35,
            "vix_velocity_5d": 0.35,
            "vix_acceleration": 0.08,
            "fg_momentum_5d": -15,
            "put_call_spike": True,
        })
        assert phase == "initial_panic"

    def test_peak_fear(self):
        phase, _ = _classify_phase({
            "vix_current": 32,
            "fg_current": 12,
            "vix_velocity_5d": 0.10,
            "vix_acceleration": -0.10,
            "fg_momentum_5d": -5,
            "backwardation_streak": 5,
        })
        assert phase == "peak_fear"

    def test_post_peak(self):
        phase, _ = _classify_phase({
            "vix_current": 25,
            "fg_current": 30,
            "vix_velocity_5d": -0.10,
            "fg_momentum_5d": 8,
        })
        assert phase == "post_peak"

    def test_confidence_range(self):
        for metrics in [
            {"vix_current": 14, "fg_current": 55},
            {"vix_current": 32, "fg_current": 12, "vix_velocity_5d": 0.10, "vix_acceleration": -0.10, "backwardation_streak": 5},
        ]:
            _, conf = _classify_phase(metrics)
            assert 0.3 <= conf <= 1.0

    def test_low_score_defaults_calm(self):
        # Weak signals for non-calm phases should default to calm
        phase, conf = _classify_phase({
            "vix_current": 19,
            "fg_current": 42,
            "vix_velocity_5d": 0.03,
            "fg_momentum_5d": -2,
        })
        assert phase == "calm"


# ── compute_fear_gauge (integration) ──


class TestComputeFearGauge:
    def test_empty_history(self):
        result = compute_fear_gauge([], [])
        assert result["phase"] == "Calm"
        assert result["confidence"] == 0.3
        assert result["date"] is None

    def test_calm_market(self):
        macro = _macro_history([15] * 15)
        sent = _sentiment_history([55] * 15, pcr=0.85)
        result = compute_fear_gauge(macro, sent)
        assert result["phase"] == "Calm"
        assert "action_kr" in result
        assert result["date"] is not None

    def test_panic_market(self):
        # VIX jumps from 15 to 35 over 6 days
        vix = [15, 18, 22, 26, 30, 35]
        macro = _macro_history(vix)
        fg = [60, 50, 40, 30, 25, 20]
        sent = _sentiment_history(fg, pcr=1.5, vts="backwardation")
        result = compute_fear_gauge(macro, sent)
        assert result["phase"] in ("Initial Panic", "Peak Fear")

    def test_metrics_populated(self):
        macro = _macro_history([18, 19, 20, 21, 22, 23])
        sent = _sentiment_history([50, 48, 46, 44, 42, 40], pcr=0.9)
        result = compute_fear_gauge(macro, sent)
        assert "metrics" in result
        assert result["metrics"]["vix_current"] == 23

    def test_phase_label_kr(self):
        result = compute_fear_gauge([], [])
        assert result["phase_kr"] == "안정"
