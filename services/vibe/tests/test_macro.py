"""Tests for macro indicator scoring and classification.

7-factor model: VIX, Yield Curve, DXY, Oil, Copper, USD/KRW, Gold.
Covers every threshold boundary, None/zero/extreme inputs, copper
normalization, aggregate weight math, and return-type contracts.
"""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest

from app.indicators.macro import (
    classify_vix,
    classify_yield_curve,
    classify_usd_krw_trend,
    classify_oil,
    classify_gold,
    classify_dxy,
    classify_copper,
    compute_macro_score,
)


# ── classify_vix ──


class TestClassifyVix:
    """Test VIX classification: complacent / low / elevated / high / extreme."""

    def test_none_returns_unknown(self):
        label, score = classify_vix(None)
        assert label == "unknown"
        assert score == 0.0

    # --- representative values ---

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

    # --- exact boundary values ---

    def test_boundary_12(self):
        """VIX == 12 exits first branch (< 12), enters second (< 20)."""
        label, score = classify_vix(12)
        assert label == "low"
        assert score == 1.0

    def test_boundary_20(self):
        label, score = classify_vix(20)
        assert label == "elevated"
        assert score == 0.0

    def test_boundary_25(self):
        label, score = classify_vix(25)
        assert label == "high"
        assert score == -0.5

    def test_boundary_30(self):
        label, score = classify_vix(30)
        assert label == "extreme"
        assert score == -1.0

    # --- just below boundary ---

    def test_just_below_12(self):
        label, _ = classify_vix(11.99)
        assert label == "complacent"

    def test_just_below_20(self):
        label, _ = classify_vix(19.99)
        assert label == "low"

    def test_just_below_25(self):
        label, _ = classify_vix(24.99)
        assert label == "elevated"

    def test_just_below_30(self):
        label, _ = classify_vix(29.99)
        assert label == "high"

    # --- zero and extremes ---

    def test_zero_vix(self):
        label, score = classify_vix(0)
        assert label == "complacent"
        assert score == 0.5

    def test_very_high_vix(self):
        label, score = classify_vix(80)
        assert label == "extreme"
        assert score == -1.0

    def test_negative_vix(self):
        """Negative VIX is not realistic but should not crash."""
        label, score = classify_vix(-5)
        assert label == "complacent"
        assert score == 0.5

    def test_float_vix(self):
        label, score = classify_vix(14.7)
        assert label == "low"
        assert score == 1.0

    def test_return_types(self):
        label, score = classify_vix(15)
        assert isinstance(label, str)
        assert isinstance(score, float)


# ── classify_yield_curve ──


class TestClassifyYieldCurve:
    """Test yield curve classification: steep / normal / flat / inverted / deeply_inverted."""

    def test_none_returns_unknown(self):
        label, score = classify_yield_curve(None)
        assert label == "unknown"
        assert score == 0.0

    # --- representative values ---

    def test_steep_curve(self):
        label, score = classify_yield_curve(2.5)
        assert label == "steep"
        assert score == 1.0

    def test_normal_curve(self):
        label, score = classify_yield_curve(1.5)
        assert label == "normal"
        assert score == 0.7

    def test_flat_curve(self):
        label, score = classify_yield_curve(0.5)
        assert label == "flat"
        assert score == 0.0

    def test_inverted_curve(self):
        label, score = classify_yield_curve(0.0)
        assert label == "inverted"
        assert score == -0.7

    def test_deeply_inverted(self):
        label, score = classify_yield_curve(-1.0)
        assert label == "deeply_inverted"
        assert score == -1.0

    # --- exact boundary values ---

    def test_boundary_2_0(self):
        """spread == 2.0 does NOT satisfy > 2.0, so falls to next branch."""
        label, score = classify_yield_curve(2.0)
        assert label == "normal"
        assert score == 0.7

    def test_boundary_1_0(self):
        label, score = classify_yield_curve(1.0)
        assert label == "flat"
        assert score == 0.0

    def test_boundary_0_3(self):
        label, score = classify_yield_curve(0.3)
        assert label == "inverted"
        assert score == -0.7

    def test_boundary_neg_0_3(self):
        label, score = classify_yield_curve(-0.3)
        assert label == "deeply_inverted"
        assert score == -1.0

    # --- just above boundary ---

    def test_just_above_2_0(self):
        label, _ = classify_yield_curve(2.01)
        assert label == "steep"

    def test_just_above_1_0(self):
        label, _ = classify_yield_curve(1.01)
        assert label == "normal"

    def test_just_above_0_3(self):
        label, _ = classify_yield_curve(0.31)
        assert label == "flat"

    def test_just_above_neg_0_3(self):
        label, _ = classify_yield_curve(-0.29)
        assert label == "inverted"

    # --- extremes ---

    def test_zero_spread(self):
        label, score = classify_yield_curve(0.0)
        assert label == "inverted"
        assert score == -0.7

    def test_very_steep(self):
        label, score = classify_yield_curve(5.0)
        assert label == "steep"
        assert score == 1.0

    def test_very_deeply_inverted(self):
        label, score = classify_yield_curve(-3.0)
        assert label == "deeply_inverted"
        assert score == -1.0

    def test_return_types(self):
        label, score = classify_yield_curve(1.5)
        assert isinstance(label, str)
        assert isinstance(score, float)


# ── classify_usd_krw_trend ──


class TestClassifyUsdKrw:
    """Test USD/KRW classification: strong_won / normal / weak_won / very_weak / crisis."""

    def test_none_returns_unknown(self):
        label, score = classify_usd_krw_trend(None)
        assert label == "unknown"
        assert score == 0.0

    # --- representative values ---

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

    # --- exact boundary values ---

    def test_boundary_1200(self):
        label, score = classify_usd_krw_trend(1200)
        assert label == "normal"
        assert score == 0.3

    def test_boundary_1300(self):
        label, score = classify_usd_krw_trend(1300)
        assert label == "weak_won"
        assert score == -0.3

    def test_boundary_1350(self):
        label, score = classify_usd_krw_trend(1350)
        assert label == "very_weak"
        assert score == -0.7

    def test_boundary_1400(self):
        label, score = classify_usd_krw_trend(1400)
        assert label == "crisis"
        assert score == -1.0

    # --- just below boundary ---

    def test_just_below_1200(self):
        label, _ = classify_usd_krw_trend(1199.99)
        assert label == "strong_won"

    def test_just_below_1300(self):
        label, _ = classify_usd_krw_trend(1299.99)
        assert label == "normal"

    def test_just_below_1350(self):
        label, _ = classify_usd_krw_trend(1349.99)
        assert label == "weak_won"

    def test_just_below_1400(self):
        label, _ = classify_usd_krw_trend(1399.99)
        assert label == "very_weak"

    # --- extremes ---

    def test_zero_usd_krw(self):
        label, score = classify_usd_krw_trend(0)
        assert label == "strong_won"
        assert score == 0.8

    def test_very_high_usd_krw(self):
        label, score = classify_usd_krw_trend(1600)
        assert label == "crisis"
        assert score == -1.0

    def test_return_types(self):
        label, score = classify_usd_krw_trend(1250)
        assert isinstance(label, str)
        assert isinstance(score, float)


# ── classify_oil ──


class TestClassifyOil:
    """Test WTI crude oil classification (U-shaped scoring)."""

    def test_none_returns_unknown(self):
        label, score = classify_oil(None)
        assert label == "unknown"
        assert score == 0.0

    # --- representative values ---

    def test_deflationary(self):
        label, score = classify_oil(30)
        assert label == "deflationary"
        assert score == -0.5

    def test_low(self):
        label, score = classify_oil(50)
        assert label == "low"
        assert score == 0.3

    def test_moderate_sweet_spot(self):
        label, score = classify_oil(65)
        assert label == "moderate"
        assert score == 0.8

    def test_elevated(self):
        label, score = classify_oil(82)
        assert label == "elevated"
        assert score == 0.0

    def test_high(self):
        label, score = classify_oil(100)
        assert label == "high"
        assert score == -0.5

    def test_extreme(self):
        label, score = classify_oil(120)
        assert label == "extreme"
        assert score == -1.0

    # --- exact boundary values ---

    def test_boundary_40(self):
        label, score = classify_oil(40)
        assert label == "low"
        assert score == 0.3

    def test_boundary_55(self):
        label, score = classify_oil(55)
        assert label == "moderate"
        assert score == 0.8

    def test_boundary_75(self):
        label, score = classify_oil(75)
        assert label == "elevated"
        assert score == 0.0

    def test_boundary_90(self):
        label, score = classify_oil(90)
        assert label == "high"
        assert score == -0.5

    def test_boundary_110(self):
        label, score = classify_oil(110)
        assert label == "extreme"
        assert score == -1.0

    # --- just below boundary ---

    def test_just_below_40(self):
        label, _ = classify_oil(39.99)
        assert label == "deflationary"

    def test_just_below_55(self):
        label, _ = classify_oil(54.99)
        assert label == "low"

    def test_just_below_75(self):
        label, _ = classify_oil(74.99)
        assert label == "moderate"

    def test_just_below_90(self):
        label, _ = classify_oil(89.99)
        assert label == "elevated"

    def test_just_below_110(self):
        label, _ = classify_oil(109.99)
        assert label == "high"

    # --- extremes ---

    def test_zero_oil(self):
        label, score = classify_oil(0)
        assert label == "deflationary"
        assert score == -0.5

    def test_negative_oil(self):
        """Negative oil price (happened April 2020) should not crash."""
        label, score = classify_oil(-37)
        assert label == "deflationary"
        assert score == -0.5

    def test_very_high_oil(self):
        label, score = classify_oil(200)
        assert label == "extreme"
        assert score == -1.0

    def test_return_types(self):
        label, score = classify_oil(65)
        assert isinstance(label, str)
        assert isinstance(score, float)


# ── classify_gold ──


class TestClassifyGold:
    """Test gold safe-haven classification."""

    def test_none_returns_unknown(self):
        label, score = classify_gold(None)
        assert label == "unknown"
        assert score == 0.0

    # --- representative values ---

    def test_low_demand(self):
        label, score = classify_gold(1800)
        assert label == "low_demand"
        assert score == 0.6

    def test_normal(self):
        label, score = classify_gold(2000)
        assert label == "normal"
        assert score == 0.2

    def test_elevated(self):
        label, score = classify_gold(2300)
        assert label == "elevated"
        assert score == -0.2

    def test_high_demand(self):
        label, score = classify_gold(2600)
        assert label == "high_demand"
        assert score == -0.5

    def test_extreme(self):
        label, score = classify_gold(3000)
        assert label == "extreme"
        assert score == -0.8

    # --- exact boundary values ---

    def test_boundary_1900(self):
        label, score = classify_gold(1900)
        assert label == "normal"
        assert score == 0.2

    def test_boundary_2200(self):
        label, score = classify_gold(2200)
        assert label == "elevated"
        assert score == -0.2

    def test_boundary_2500(self):
        label, score = classify_gold(2500)
        assert label == "high_demand"
        assert score == -0.5

    def test_boundary_2800(self):
        label, score = classify_gold(2800)
        assert label == "extreme"
        assert score == -0.8

    # --- just below boundary ---

    def test_just_below_1900(self):
        label, _ = classify_gold(1899.99)
        assert label == "low_demand"

    def test_just_below_2200(self):
        label, _ = classify_gold(2199.99)
        assert label == "normal"

    def test_just_below_2500(self):
        label, _ = classify_gold(2499.99)
        assert label == "elevated"

    def test_just_below_2800(self):
        label, _ = classify_gold(2799.99)
        assert label == "high_demand"

    # --- extremes ---

    def test_zero_gold(self):
        label, score = classify_gold(0)
        assert label == "low_demand"
        assert score == 0.6

    def test_very_high_gold(self):
        label, score = classify_gold(5000)
        assert label == "extreme"
        assert score == -0.8

    def test_return_types(self):
        label, score = classify_gold(2100)
        assert isinstance(label, str)
        assert isinstance(score, float)


# ── classify_dxy ──


class TestClassifyDxy:
    """Test USD Dollar Index classification."""

    def test_none_returns_unknown(self):
        label, score = classify_dxy(None)
        assert label == "unknown"
        assert score == 0.0

    # --- representative values ---

    def test_weak_dollar(self):
        label, score = classify_dxy(93)
        assert label == "weak"
        assert score == 0.5

    def test_normal(self):
        label, score = classify_dxy(98)
        assert label == "normal"
        assert score == 0.3

    def test_firm(self):
        label, score = classify_dxy(101)
        assert label == "firm"
        assert score == 0.0

    def test_strong(self):
        label, score = classify_dxy(105)
        assert label == "strong"
        assert score == -0.4

    def test_very_strong(self):
        label, score = classify_dxy(110)
        assert label == "very_strong"
        assert score == -0.8

    # --- exact boundary values ---

    def test_boundary_95(self):
        label, score = classify_dxy(95)
        assert label == "normal"
        assert score == 0.3

    def test_boundary_100(self):
        label, score = classify_dxy(100)
        assert label == "firm"
        assert score == 0.0

    def test_boundary_103(self):
        label, score = classify_dxy(103)
        assert label == "strong"
        assert score == -0.4

    def test_boundary_107(self):
        label, score = classify_dxy(107)
        assert label == "very_strong"
        assert score == -0.8

    # --- just below boundary ---

    def test_just_below_95(self):
        label, _ = classify_dxy(94.99)
        assert label == "weak"

    def test_just_below_100(self):
        label, _ = classify_dxy(99.99)
        assert label == "normal"

    def test_just_below_103(self):
        label, _ = classify_dxy(102.99)
        assert label == "firm"

    def test_just_below_107(self):
        label, _ = classify_dxy(106.99)
        assert label == "strong"

    # --- extremes ---

    def test_zero_dxy(self):
        label, score = classify_dxy(0)
        assert label == "weak"
        assert score == 0.5

    def test_very_high_dxy(self):
        label, score = classify_dxy(120)
        assert label == "very_strong"
        assert score == -0.8

    def test_return_types(self):
        label, score = classify_dxy(100)
        assert isinstance(label, str)
        assert isinstance(score, float)


# ── classify_copper ──


class TestClassifyCopper:
    """Test copper (Dr. Copper) economic indicator classification.

    Includes normalization from cents/lb to $/lb.
    """

    def test_none_returns_unknown(self):
        label, score = classify_copper(None)
        assert label == "unknown"
        assert score == 0.0

    # --- representative values in $/lb ---

    def test_contraction(self):
        label, score = classify_copper(2.5)
        assert label == "contraction"
        assert score == -0.8

    def test_weak(self):
        label, score = classify_copper(3.2)
        assert label == "weak"
        assert score == -0.3

    def test_normal(self):
        label, score = classify_copper(3.8)
        assert label == "normal"
        assert score == 0.3

    def test_strong(self):
        label, score = classify_copper(4.3)
        assert label == "strong"
        assert score == 0.7

    def test_boom(self):
        label, score = classify_copper(5.0)
        assert label == "boom"
        assert score == 0.5

    # --- exact boundary values ---

    def test_boundary_3_0(self):
        label, score = classify_copper(3.0)
        assert label == "weak"
        assert score == -0.3

    def test_boundary_3_5(self):
        label, score = classify_copper(3.5)
        assert label == "normal"
        assert score == 0.3

    def test_boundary_4_0(self):
        label, score = classify_copper(4.0)
        assert label == "strong"
        assert score == 0.7

    def test_boundary_4_5(self):
        label, score = classify_copper(4.5)
        assert label == "boom"
        assert score == 0.5

    # --- just below boundary ---

    def test_just_below_3_0(self):
        label, _ = classify_copper(2.99)
        assert label == "contraction"

    def test_just_below_3_5(self):
        label, _ = classify_copper(3.49)
        assert label == "weak"

    def test_just_below_4_0(self):
        label, _ = classify_copper(3.99)
        assert label == "normal"

    def test_just_below_4_5(self):
        label, _ = classify_copper(4.49)
        assert label == "strong"

    # --- cents/lb normalization (HG=F COMEX format) ---

    def test_cents_normalization_250(self):
        """250 cents/lb -> $2.50/lb -> contraction."""
        label, score = classify_copper(250)
        assert label == "contraction"
        assert score == -0.8

    def test_cents_normalization_320(self):
        """320 cents/lb -> $3.20/lb -> weak."""
        label, score = classify_copper(320)
        assert label == "weak"
        assert score == -0.3

    def test_cents_normalization_380(self):
        """380 cents/lb -> $3.80/lb -> normal."""
        label, score = classify_copper(380)
        assert label == "normal"
        assert score == 0.3

    def test_cents_normalization_430(self):
        """430 cents/lb -> $4.30/lb -> strong."""
        label, score = classify_copper(430)
        assert label == "strong"
        assert score == 0.7

    def test_cents_normalization_500(self):
        """500 cents/lb -> $5.00/lb -> boom."""
        label, score = classify_copper(500)
        assert label == "boom"
        assert score == 0.5

    def test_cents_normalization_boundary_100_not_triggered(self):
        """100 exactly does NOT trigger normalization (> 100, not >= 100).
        100 treated as $100/lb -> boom."""
        label, score = classify_copper(100)
        assert label == "boom"
        assert score == 0.5

    def test_cents_normalization_boundary_101(self):
        """101 cents/lb -> $1.01/lb -> contraction."""
        label, score = classify_copper(101)
        assert label == "contraction"
        assert score == -0.8

    def test_no_normalization_below_100(self):
        """Values <= 100 should NOT be normalized (treated as $/lb)."""
        # 99.99 $/lb is already in $/lb range but unrealistically high
        # The normalization threshold is > 100
        label, score = classify_copper(99.99)
        assert label == "boom"
        assert score == 0.5

    # --- extremes ---

    def test_zero_copper(self):
        label, score = classify_copper(0)
        assert label == "contraction"
        assert score == -0.8

    def test_very_high_copper_dollars(self):
        label, score = classify_copper(10.0)
        assert label == "boom"
        assert score == 0.5

    def test_very_high_copper_cents(self):
        """1000 cents/lb -> $10.00/lb -> boom."""
        label, score = classify_copper(1000)
        assert label == "boom"
        assert score == 0.5

    def test_return_types(self):
        label, score = classify_copper(4.0)
        assert isinstance(label, str)
        assert isinstance(score, float)


# ── compute_macro_score ──


class TestComputeMacroScore:
    """Test aggregate macro score computation with 7 factors."""

    # --- full data scenarios ---

    def test_all_favorable(self):
        data = {
            "vix": 15, "us_yield_spread": 2.5, "usd_krw": 1150,
            "wti_crude": 65, "gold_price": 1800, "dxy_index": 93,
            "copper_price": 4.3,
        }
        result = compute_macro_score(data)
        assert result["aggregate_score"] > 0.5
        assert result["vix"]["label"] == "low"
        assert result["yield_curve"]["label"] == "steep"
        assert result["fx"]["label"] == "strong_won"
        assert result["oil"]["label"] == "moderate"
        assert result["gold"]["label"] == "low_demand"
        assert result["dxy"]["label"] == "weak"
        assert result["copper"]["label"] == "strong"

    def test_all_negative(self):
        data = {
            "vix": 35, "us_yield_spread": -1.0, "usd_krw": 1450,
            "wti_crude": 120, "gold_price": 3000, "dxy_index": 110,
            "copper_price": 2.5,
        }
        result = compute_macro_score(data)
        assert result["aggregate_score"] < -0.5

    def test_mixed_signals(self):
        data = {
            "vix": 15, "us_yield_spread": -0.3, "usd_krw": 1350,
            "wti_crude": 65, "gold_price": 2600, "dxy_index": 105,
            "copper_price": 3.8,
        }
        result = compute_macro_score(data)
        assert -1.0 <= result["aggregate_score"] <= 1.0

    # --- missing / partial data ---

    def test_missing_all_data(self):
        result = compute_macro_score({})
        assert result["aggregate_score"] == 0.0
        assert result["vix"]["label"] == "unknown"
        assert result["yield_curve"]["label"] == "unknown"
        assert result["fx"]["label"] == "unknown"
        assert result["oil"]["label"] == "unknown"
        assert result["gold"]["label"] == "unknown"
        assert result["dxy"]["label"] == "unknown"
        assert result["copper"]["label"] == "unknown"

    def test_partial_data_only_vix(self):
        data = {"vix": 15}
        result = compute_macro_score(data)
        assert result["vix"]["score"] == 1.0
        # All others default to 0.0
        assert result["yield_curve"]["score"] == 0.0
        assert result["fx"]["score"] == 0.0
        assert result["oil"]["score"] == 0.0
        assert result["gold"]["score"] == 0.0
        assert result["dxy"]["score"] == 0.0
        assert result["copper"]["score"] == 0.0
        # aggregate = 1.0 * 0.20 = 0.20
        assert result["aggregate_score"] == 0.2

    def test_partial_data_oil_and_copper(self):
        data = {"wti_crude": 65, "copper_price": 4.3}
        result = compute_macro_score(data)
        assert result["oil"]["score"] == 0.8
        assert result["copper"]["score"] == 0.7

    def test_all_none_explicit(self):
        """All keys present but with None values."""
        data = {
            "vix": None, "us_yield_spread": None, "usd_krw": None,
            "wti_crude": None, "gold_price": None, "dxy_index": None,
            "copper_price": None,
        }
        result = compute_macro_score(data)
        assert result["aggregate_score"] == 0.0
        for key in ["vix", "yield_curve", "fx", "oil", "gold", "dxy", "copper"]:
            assert result[key]["label"] == "unknown"
            assert result[key]["score"] == 0.0

    # --- raw value pass-through ---

    def test_result_contains_raw_values(self):
        data = {
            "vix": 22, "us_yield_spread": 0.5, "usd_krw": 1300,
            "wti_crude": 70, "gold_price": 2100, "dxy_index": 102,
            "copper_price": 4.0,
        }
        result = compute_macro_score(data)
        assert result["vix"]["value"] == 22
        assert result["yield_curve"]["value"] == 0.5
        assert result["fx"]["value"] == 1300
        assert result["oil"]["value"] == 70
        assert result["gold"]["value"] == 2100
        assert result["dxy"]["value"] == 102
        assert result["copper"]["value"] == 4.0

    def test_missing_values_are_none(self):
        result = compute_macro_score({})
        assert result["vix"]["value"] is None
        assert result["yield_curve"]["value"] is None
        assert result["fx"]["value"] is None
        assert result["oil"]["value"] is None
        assert result["gold"]["value"] is None
        assert result["dxy"]["value"] is None
        assert result["copper"]["value"] is None

    # --- weight verification ---

    def test_weights_sum_to_one(self):
        """Verify the 7-factor weighting sums to 1.0."""
        data = {
            "vix": 15, "us_yield_spread": 2.5, "usd_krw": 1150,
            "wti_crude": 65, "gold_price": 1800, "dxy_index": 93,
            "copper_price": 4.3,
        }
        result = compute_macro_score(data)
        expected = (
            1.0 * 0.20   # VIX low
            + 1.0 * 0.15  # Yield steep
            + 0.5 * 0.15  # DXY weak
            + 0.8 * 0.15  # Oil moderate
            + 0.7 * 0.15  # Copper strong
            + 0.8 * 0.10  # USD/KRW strong won
            + 0.6 * 0.10  # Gold low demand
        )
        assert abs(result["aggregate_score"] - round(expected, 4)) < 0.0001

    def test_all_negative_exact_score(self):
        """Verify exact aggregate for all-negative scenario."""
        data = {
            "vix": 35, "us_yield_spread": -1.0, "usd_krw": 1450,
            "wti_crude": 120, "gold_price": 3000, "dxy_index": 110,
            "copper_price": 2.5,
        }
        result = compute_macro_score(data)
        expected = (
            -1.0 * 0.20   # VIX extreme
            + -1.0 * 0.15  # Yield deeply inverted
            + -0.8 * 0.15  # DXY very strong
            + -1.0 * 0.15  # Oil extreme
            + -0.8 * 0.15  # Copper contraction
            + -1.0 * 0.10  # USD/KRW crisis
            + -0.8 * 0.10  # Gold extreme
        )
        assert abs(result["aggregate_score"] - round(expected, 4)) < 0.0001

    def test_single_factor_contribution_vix(self):
        """Only VIX provided: aggregate = score * 0.20."""
        data = {"vix": 15}
        result = compute_macro_score(data)
        assert result["aggregate_score"] == round(1.0 * 0.20, 4)

    def test_single_factor_contribution_yield(self):
        """Only yield spread provided: aggregate = score * 0.15."""
        data = {"us_yield_spread": 2.5}
        result = compute_macro_score(data)
        assert result["aggregate_score"] == round(1.0 * 0.15, 4)

    def test_single_factor_contribution_dxy(self):
        """Only DXY provided: aggregate = score * 0.15."""
        data = {"dxy_index": 93}
        result = compute_macro_score(data)
        assert result["aggregate_score"] == round(0.5 * 0.15, 4)

    def test_single_factor_contribution_oil(self):
        """Only oil provided: aggregate = score * 0.15."""
        data = {"wti_crude": 65}
        result = compute_macro_score(data)
        assert result["aggregate_score"] == round(0.8 * 0.15, 4)

    def test_single_factor_contribution_copper(self):
        """Only copper provided: aggregate = score * 0.15."""
        data = {"copper_price": 4.3}
        result = compute_macro_score(data)
        assert result["aggregate_score"] == round(0.7 * 0.15, 4)

    def test_single_factor_contribution_fx(self):
        """Only USD/KRW provided: aggregate = score * 0.10."""
        data = {"usd_krw": 1150}
        result = compute_macro_score(data)
        assert result["aggregate_score"] == round(0.8 * 0.10, 4)

    def test_single_factor_contribution_gold(self):
        """Only gold provided: aggregate = score * 0.10."""
        data = {"gold_price": 1800}
        result = compute_macro_score(data)
        assert result["aggregate_score"] == round(0.6 * 0.10, 4)

    # --- aggregate is bounded ---

    def test_aggregate_bounded_upper(self):
        """Maximum possible aggregate when all scores are at their highest."""
        data = {
            "vix": 15,           # 1.0
            "us_yield_spread": 3.0,  # 1.0
            "usd_krw": 1100,    # 0.8
            "wti_crude": 65,    # 0.8
            "gold_price": 1800, # 0.6
            "dxy_index": 90,    # 0.5
            "copper_price": 4.3, # 0.7
        }
        result = compute_macro_score(data)
        assert result["aggregate_score"] <= 1.0

    def test_aggregate_bounded_lower(self):
        """Minimum possible aggregate when all scores are at their lowest."""
        data = {
            "vix": 40,           # -1.0
            "us_yield_spread": -2.0,  # -1.0
            "usd_krw": 1500,    # -1.0
            "wti_crude": 150,   # -1.0
            "gold_price": 3500, # -0.8
            "dxy_index": 115,   # -0.8
            "copper_price": 2.0, # -0.8
        }
        result = compute_macro_score(data)
        assert result["aggregate_score"] >= -1.0

    # --- structure / keys ---

    def test_result_keys(self):
        """All 7 factors plus aggregate must be in result."""
        result = compute_macro_score({})
        expected_keys = {"vix", "yield_curve", "fx", "oil", "gold", "dxy", "copper", "aggregate_score"}
        assert set(result.keys()) == expected_keys

    def test_factor_subdict_keys(self):
        """Each factor dict must contain label, score, value."""
        result = compute_macro_score({"vix": 20})
        for key in ["vix", "yield_curve", "fx", "oil", "gold", "dxy", "copper"]:
            assert "label" in result[key]
            assert "score" in result[key]
            assert "value" in result[key]

    def test_aggregate_is_rounded(self):
        """aggregate_score should be rounded to 4 decimal places."""
        data = {
            "vix": 15, "us_yield_spread": 1.5, "usd_krw": 1250,
            "wti_crude": 65, "gold_price": 2000, "dxy_index": 98,
            "copper_price": 3.8,
        }
        result = compute_macro_score(data)
        assert result["aggregate_score"] == round(result["aggregate_score"], 4)

    def test_return_type_is_dict(self):
        result = compute_macro_score({})
        assert isinstance(result, dict)

    def test_aggregate_score_is_float(self):
        result = compute_macro_score({})
        assert isinstance(result["aggregate_score"], float)

    # --- copper cents normalization pass-through in aggregate ---

    def test_aggregate_with_copper_in_cents(self):
        """Copper in cents/lb should be normalized before scoring."""
        data_cents = {"copper_price": 430}  # 430 cents = $4.30
        data_dollars = {"copper_price": 4.3}  # $4.30
        result_cents = compute_macro_score(data_cents)
        result_dollars = compute_macro_score(data_dollars)
        assert result_cents["copper"]["score"] == result_dollars["copper"]["score"]
        assert result_cents["aggregate_score"] == result_dollars["aggregate_score"]

    # --- extra / unknown keys are harmless ---

    def test_extra_keys_ignored(self):
        """Extra keys in macro_data should not affect result."""
        data = {
            "vix": 15, "us_yield_spread": 2.5, "usd_krw": 1150,
            "wti_crude": 65, "gold_price": 1800, "dxy_index": 93,
            "copper_price": 4.3,
            "foo": "bar", "extra_indicator": 999,
        }
        result = compute_macro_score(data)
        assert result["aggregate_score"] > 0.5
        assert "foo" not in result
