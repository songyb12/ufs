"""Tests for fear gauge peak fear detection."""

import pytest

from app.indicators.fear_gauge import compute_fear_gauge, _compute_metrics, _classify_phase


def _make_macro(count, vix_values=None):
    vix_vals = vix_values or [18.0] * count
    return [
        {"indicator_date": f"2026-01-{i + 1:02d}", "vix": vix_vals[i % len(vix_vals)]}
        for i in range(count)
    ]


def _make_sentiment(count, fg_values=None, pc_values=None, vts=None):
    fg_vals = fg_values or [50] * count
    pc_vals = pc_values or [0.85] * count
    vts_val = vts or "contango"
    return [
        {
            "indicator_date": f"2026-01-{i + 1:02d}",
            "fear_greed_index": fg_vals[i % len(fg_vals)],
            "put_call_ratio": pc_vals[i % len(pc_vals)],
            "vix_term_structure": vts_val,
        }
        for i in range(count)
    ]


class TestFearGaugeCalm:
    def test_calm_normal_conditions(self):
        macro = _make_macro(30, [16.0] * 30)
        sent = _make_sentiment(30, [55] * 30)
        result = compute_fear_gauge(macro, sent)
        assert result["phase"] == "Calm"

    def test_calm_low_vix_high_fg(self):
        macro = _make_macro(30, [14.0] * 30)
        sent = _make_sentiment(30, [60] * 30)
        result = compute_fear_gauge(macro, sent)
        assert result["phase"] == "Calm"


class TestFearGaugeInitialPanic:
    def test_vix_spike_fg_drop(self):
        """VIX급등(18→32) + F&G급락(50→18) = Initial Panic 또는 Peak Fear"""
        vix = [18.0] * 24 + [22.0, 25.0, 27.0, 29.0, 31.0, 32.0]
        fg = [50] * 24 + [42, 35, 28, 23, 20, 18]
        macro = _make_macro(30, vix)
        sent = _make_sentiment(30, fg)
        result = compute_fear_gauge(macro, sent)
        assert result["phase"] in ("Initial Panic", "Peak Fear")

    def test_rapid_vix_acceleration(self):
        """VIX 가속 상승 시 패닉 감지"""
        vix = [18.0] * 20 + [19, 21, 24, 27, 30, 34, 36, 38, 40, 42]
        fg = [50] * 20 + [45, 40, 35, 30, 25, 22, 20, 18, 16, 14]
        macro = _make_macro(30, vix)
        sent = _make_sentiment(30, fg)
        result = compute_fear_gauge(macro, sent)
        assert result["phase"] in ("Initial Panic", "Peak Fear")


class TestFearGaugePeakFear:
    def test_high_vix_decelerating(self):
        """VIX 고점이지만 속도 감소 + F&G 극단 = Peak Fear"""
        # VIX: rapid rise then plateau
        vix = [18.0] * 10 + [22, 26, 30, 34, 36, 37, 37.5, 37.5, 37.0, 36.5,
                              36, 35.5, 35, 34.5, 34, 33.5, 33, 32.5, 32, 31.5]
        fg = [50] * 10 + [35, 28, 22, 18, 15, 14, 13, 13, 14, 14,
                           14, 15, 15, 15, 16, 16, 16, 17, 17, 17]
        macro = _make_macro(30, vix)
        sent = _make_sentiment(30, fg)
        result = compute_fear_gauge(macro, sent)
        # Should be peak_fear or post_peak (VIX declining from high)
        assert result["phase"] in ("Peak Fear", "Post-Peak")


class TestFearGaugePostPeak:
    def test_vix_declining_fg_recovering(self):
        """VIX 하락 추세 + F&G 반등 시작 = Post-Peak"""
        vix = [35.0] * 15 + [33, 31, 29, 27, 26, 25, 24, 23, 22, 21,
                              20, 19, 18.5, 18, 17.5]
        fg = [15] * 15 + [16, 18, 20, 22, 25, 27, 29, 31, 33, 35,
                           36, 37, 38, 39, 40]
        macro = _make_macro(30, vix)
        sent = _make_sentiment(30, fg)
        result = compute_fear_gauge(macro, sent)
        assert result["phase"] in ("Post-Peak", "Calm")


class TestFearGaugeEdgeCases:
    def test_empty_data(self):
        result = compute_fear_gauge([], [])
        assert result["phase"] == "Calm"
        assert result["confidence"] <= 0.4

    def test_minimal_data(self):
        macro = _make_macro(3)
        sent = _make_sentiment(3)
        result = compute_fear_gauge(macro, sent)
        assert "phase" in result

    def test_metrics_present(self):
        macro = _make_macro(30)
        sent = _make_sentiment(30)
        result = compute_fear_gauge(macro, sent)
        m = result["metrics"]
        assert "vix_current" in m
        assert "vix_velocity_5d" in m
        assert "fg_current" in m
        assert "fg_momentum_5d" in m
        assert "put_call_spike" in m

    def test_action_kr_present(self):
        macro = _make_macro(30)
        sent = _make_sentiment(30)
        result = compute_fear_gauge(macro, sent)
        assert isinstance(result["action_kr"], str)
        assert len(result["action_kr"]) > 0

    def test_confidence_bounded(self):
        macro = _make_macro(30)
        sent = _make_sentiment(30)
        result = compute_fear_gauge(macro, sent)
        assert 0.3 <= result["confidence"] <= 1.0

    def test_backwardation_streak(self):
        macro = _make_macro(30)
        sent = _make_sentiment(30, vts="backwardation")
        result = compute_fear_gauge(macro, sent)
        assert result["metrics"]["backwardation_streak"] == 30

    def test_put_call_spike_detection(self):
        macro = _make_macro(30)
        sent = _make_sentiment(30, pc_values=[1.4] * 30)
        result = compute_fear_gauge(macro, sent)
        assert result["metrics"]["put_call_spike"] is True

    def test_date_from_last_entry(self):
        macro = _make_macro(30)
        sent = _make_sentiment(30)
        result = compute_fear_gauge(macro, sent)
        assert result["date"] == "2026-01-30"
