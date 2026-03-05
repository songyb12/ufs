"""Tests for fundamental indicator scoring."""

import pytest

from app.indicators.fundamental import (
    compute_fundamental_score,
    _compute_value_score,
    _compute_quality_score,
)


class TestComputeValueScore:
    """Test value score (PER + PBR) calculation."""

    def test_low_per_low_pbr_kr(self):
        """Deep value stock in KR market."""
        score = _compute_value_score({"per": 5, "pbr": 0.5}, "KR")
        assert score == 50  # 25 (PER) + 25 (PBR)

    def test_high_per_high_pbr_kr(self):
        """Expensive stock in KR market."""
        score = _compute_value_score({"per": 30, "pbr": 4.0}, "KR")
        assert score < 0

    def test_moderate_per_kr(self):
        score = _compute_value_score({"per": 10, "pbr": 0.9}, "KR")
        assert score > 0  # Should be positive (15 + 15 = 30)

    def test_us_market_higher_per_tolerance(self):
        """US has higher PER thresholds."""
        score_kr = _compute_value_score({"per": 20}, "KR")
        score_us = _compute_value_score({"per": 20}, "US")
        assert score_us > score_kr  # US is more lenient for same PER

    def test_us_market_higher_pbr_tolerance(self):
        score_kr = _compute_value_score({"pbr": 2.0}, "KR")
        score_us = _compute_value_score({"pbr": 2.0}, "US")
        assert score_us > score_kr

    def test_none_per_no_contribution(self):
        score = _compute_value_score({"per": None, "pbr": 0.5}, "KR")
        assert score == 25  # Only PBR contributes

    def test_zero_per_no_contribution(self):
        score = _compute_value_score({"per": 0, "pbr": 0.5}, "KR")
        assert score == 25

    def test_negative_per_no_contribution(self):
        score = _compute_value_score({"per": -5, "pbr": 0.5}, "KR")
        assert score == 25

    def test_empty_data(self):
        score = _compute_value_score({}, "KR")
        assert score == 0.0

    def test_score_clamped_to_range(self):
        score = _compute_value_score({"per": 5, "pbr": 0.5}, "KR")
        assert -50 <= score <= 50


class TestComputeQualityScore:
    """Test quality score (ROE + margin + dividend) calculation."""

    def test_high_quality(self):
        data = {"roe": 25, "operating_margin": 30, "div_yield": 4}
        score = _compute_quality_score(data, "KR")
        assert score > 30  # 20 + 15 + 10 = 45

    def test_low_quality(self):
        data = {"roe": -5, "operating_margin": -5, "div_yield": 0}
        score = _compute_quality_score(data, "KR")
        assert score < 0  # -15 + -15 + -5 = -35

    def test_moderate_quality(self):
        data = {"roe": 12, "operating_margin": 12, "div_yield": 2}
        score = _compute_quality_score(data, "KR")
        assert score > 0

    def test_none_values_no_contribution(self):
        score = _compute_quality_score({}, "KR")
        assert score == 0.0

    def test_roe_only(self):
        score = _compute_quality_score({"roe": 25}, "KR")
        assert score == 20

    def test_high_dividend_bonus(self):
        score = _compute_quality_score({"div_yield": 6}, "KR")
        assert score == 15

    def test_score_clamped(self):
        data = {"roe": 25, "operating_margin": 30, "div_yield": 6}
        score = _compute_quality_score(data, "KR")
        assert -50 <= score <= 50


class TestComputeFundamentalScore:
    """Test overall fundamental score composition."""

    def test_returns_expected_keys(self):
        result = compute_fundamental_score({"per": 10, "pbr": 1.0, "roe": 15}, "KR")
        assert "fundamental_score" in result
        assert "value_score" in result
        assert "quality_score" in result
        assert "components" in result

    def test_score_range(self):
        result = compute_fundamental_score({"per": 10, "pbr": 1.0}, "KR")
        assert -100 <= result["fundamental_score"] <= 100

    def test_deep_value_high_quality(self):
        data = {"per": 5, "pbr": 0.5, "roe": 25, "operating_margin": 30, "div_yield": 4}
        result = compute_fundamental_score(data, "KR")
        assert result["fundamental_score"] > 50

    def test_expensive_low_quality(self):
        data = {"per": 50, "pbr": 5, "roe": -5, "operating_margin": -5, "div_yield": 0}
        result = compute_fundamental_score(data, "KR")
        assert result["fundamental_score"] < -30

    def test_empty_data_returns_zero(self):
        result = compute_fundamental_score({}, "KR")
        assert result["fundamental_score"] == 0.0
        assert result["value_score"] == 0.0
        assert result["quality_score"] == 0.0

    def test_components_preserved(self):
        data = {"per": 10, "pbr": 1.0, "roe": 15, "operating_margin": 20, "div_yield": 3}
        result = compute_fundamental_score(data, "KR")
        assert result["components"]["per"] == 10
        assert result["components"]["pbr"] == 1.0
        assert result["components"]["roe"] == 15

    def test_us_vs_kr_scoring_difference(self):
        """Same data should score differently for KR vs US."""
        data = {"per": 20, "pbr": 3.0}
        kr_result = compute_fundamental_score(data, "KR")
        us_result = compute_fundamental_score(data, "US")
        assert us_result["value_score"] > kr_result["value_score"]
