"""Tests for macro indicator scoring and classification."""

import pytest

from app.indicators.macro import (
    classify_vix,
    classify_yield_curve,
    classify_usd_krw_trend,
    compute_macro_score,
)


class TestClassifyVix:
    """Test VIX classification."""

    def test_none_returns_unknown(self):
        label, score = classify_vix(None)
        assert label == "unknown"
        assert score == 0.0

    def test_complacent_vix(self):
        label, score = classify_vix(10)
        assert label == "complacent"
        assert score == 0.5

    def test_low_vix(self):
        label, score = classify_vix(15)
        assert label == "low"
        assert score == 1.0

    def test_elevated_vix(self):
        label, score = classify_vix(22)
        assert label == "elevated"
        assert score == 0.0

    def test_high_vix(self):
        label, score = classify_vix(28)
        assert label == "high"
        assert score == -0.5

    def test_extreme_vix(self):
        label, score = classify_vix(35)
        assert label == "extreme"
        assert score == -1.0

    def test_boundary_12(self):
        label, _ = classify_vix(12)
        assert label == "low"

    def test_boundary_20(self):
        label, _ = classify_vix(20)
        assert label == "elevated"

    def test_boundary_25(self):
        label, _ = classify_vix(25)
        assert label == "high"

    def test_boundary_30(self):
        label, _ = classify_vix(30)
        assert label == "extreme"


class TestClassifyYieldCurve:
    """Test yield curve classification."""

    def test_none_returns_unknown(self):
        label, score = classify_yield_curve(None)
        assert label == "unknown"
        assert score == 0.0

    def test_steep_curve(self):
        label, score = classify_yield_curve(2.0)
        assert label == "steep"
        assert score == 1.0

    def test_normal_curve(self):
        label, score = classify_yield_curve(0.8)
        assert label == "normal"
        assert score == 0.7

    def test_flat_curve(self):
        label, score = classify_yield_curve(0.3)
        assert label == "flat"
        assert score == 0.0

    def test_inverted_curve(self):
        label, score = classify_yield_curve(-0.3)
        assert label == "inverted"
        assert score == -0.7

    def test_deeply_inverted(self):
        label, score = classify_yield_curve(-1.0)
        assert label == "deeply_inverted"
        assert score == -1.0


class TestClassifyUsdKrw:
    """Test USD/KRW classification."""

    def test_none_returns_unknown(self):
        label, score = classify_usd_krw_trend(None)
        assert label == "unknown"
        assert score == 0.0

    def test_strong_won(self):
        label, score = classify_usd_krw_trend(1150)
        assert label == "strong_won"
        assert score == 0.8

    def test_normal_fx(self):
        label, score = classify_usd_krw_trend(1250)
        assert label == "normal"
        assert score == 0.3

    def test_weak_won(self):
        label, score = classify_usd_krw_trend(1320)
        assert label == "weak_won"
        assert score == -0.3

    def test_very_weak(self):
        label, score = classify_usd_krw_trend(1370)
        assert label == "very_weak"
        assert score == -0.7

    def test_crisis(self):
        label, score = classify_usd_krw_trend(1450)
        assert label == "crisis"
        assert score == -1.0


class TestComputeMacroScore:
    """Test aggregate macro score computation."""

    def test_all_favorable(self):
        data = {"vix": 15, "us_yield_spread": 2.0, "usd_krw": 1150}
        result = compute_macro_score(data)
        assert result["aggregate_score"] > 0.5
        assert result["vix"]["label"] == "low"
        assert result["yield_curve"]["label"] == "steep"
        assert result["fx"]["label"] == "strong_won"

    def test_all_negative(self):
        data = {"vix": 35, "us_yield_spread": -1.0, "usd_krw": 1450}
        result = compute_macro_score(data)
        assert result["aggregate_score"] < -0.5

    def test_mixed_signals(self):
        data = {"vix": 15, "us_yield_spread": -0.3, "usd_krw": 1350}
        result = compute_macro_score(data)
        # VIX favorable, yield inverted, FX weak: mixed
        assert -1.0 <= result["aggregate_score"] <= 1.0

    def test_missing_all_data(self):
        result = compute_macro_score({})
        assert result["aggregate_score"] == 0.0
        assert result["vix"]["label"] == "unknown"
        assert result["yield_curve"]["label"] == "unknown"
        assert result["fx"]["label"] == "unknown"

    def test_partial_data(self):
        data = {"vix": 15}
        result = compute_macro_score(data)
        assert result["vix"]["score"] == 1.0
        assert result["yield_curve"]["score"] == 0.0
        assert result["fx"]["score"] == 0.0

    def test_result_contains_raw_values(self):
        data = {"vix": 22, "us_yield_spread": 0.5, "usd_krw": 1300}
        result = compute_macro_score(data)
        assert result["vix"]["value"] == 22
        assert result["yield_curve"]["value"] == 0.5
        assert result["fx"]["value"] == 1300

    def test_weights_sum_to_one(self):
        """Verify the weighting is consistent."""
        data = {"vix": 15, "us_yield_spread": 2.0, "usd_krw": 1150}
        result = compute_macro_score(data)
        expected = (1.0 * 0.4 + 1.0 * 0.3 + 0.8 * 0.3)
        assert abs(result["aggregate_score"] - expected) < 0.001
