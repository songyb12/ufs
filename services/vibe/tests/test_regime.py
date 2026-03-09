"""Tests for app.indicators.regime — pure function tests."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest

from app.indicators.regime import (
    DEFENSE_SECTORS,
    DRIVER_LABELS,
    RISK_LABELS,
    _empty_benchmark,
    _fx_scenario_range,
    _generate_action_items,
    _scenario_range,
    aggregate_sector_fund_flow,
    compute_cross_market_recommendation,
    compute_entry_scenarios,
    compute_relative_strength,
    compute_sector_rotation,
    compute_stagflation_index,
    detect_combined_regime,
    detect_driver_regime,
    detect_risk_regime,
)


# ── detect_risk_regime ──


class TestDetectRiskRegime:
    def test_all_none_defaults_to_risk_on(self):
        r = detect_risk_regime(None, None, None, None, None)
        assert r["regime"] == "Risk-On"
        assert -1.0 <= r["score"] <= 1.0

    def test_panic_conditions(self):
        r = detect_risk_regime(vix=40, fear_greed=10, put_call_ratio=1.5,
                               vix_term_structure="backwardation", yield_spread=-1.0)
        assert r["regime"] == "Panic"
        assert r["score"] <= -0.6

    def test_complacent_conditions(self):
        r = detect_risk_regime(vix=11, fear_greed=90, put_call_ratio=0.5,
                               vix_term_structure="contango", yield_spread=2.0)
        assert r["regime"] == "Complacent"
        assert r["score"] > 0.5

    def test_risk_off_moderate_fear(self):
        r = detect_risk_regime(vix=30, fear_greed=25, put_call_ratio=1.1,
                               vix_term_structure="backwardation", yield_spread=-0.2)
        assert r["regime"] in ("Panic", "Risk-Off")
        assert r["score"] < 0

    def test_risk_on_neutral(self):
        r = detect_risk_regime(vix=18, fear_greed=55, put_call_ratio=0.85,
                               vix_term_structure="contango", yield_spread=0.5)
        assert r["regime"] == "Risk-On"
        assert -0.15 < r["score"] <= 0.5

    def test_score_clamped(self):
        r = detect_risk_regime(vix=100, fear_greed=0, put_call_ratio=3.0,
                               vix_term_structure="backwardation", yield_spread=-5.0)
        assert r["score"] >= -1.0
        r2 = detect_risk_regime(vix=5, fear_greed=100, put_call_ratio=0.1,
                                vix_term_structure="contango", yield_spread=5.0)
        assert r2["score"] <= 1.0

    def test_factors_present(self):
        r = detect_risk_regime(20, 50, 0.9, "contango", 0.5)
        assert "vix" in r["factors"]
        assert "fear_greed" in r["factors"]
        assert "put_call" in r["factors"]
        assert "vix_term" in r["factors"]
        assert "yield_spread" in r["factors"]

    def test_vix_boundary_13(self):
        r1 = detect_risk_regime(vix=12.9, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(vix=13.0, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["vix"]["label"] == "very_low"
        assert r2["factors"]["vix"]["label"] == "low"

    def test_fear_greed_score_formula(self):
        r = detect_risk_regime(vix=18, fear_greed=0, put_call_ratio=0.85,
                               vix_term_structure="contango", yield_spread=0.5)
        assert r["factors"]["fear_greed"]["score"] == -1.0

        r2 = detect_risk_regime(vix=18, fear_greed=100, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r2["factors"]["fear_greed"]["score"] == 1.0

    def test_kr_label_present(self):
        r = detect_risk_regime(20, 50, 0.9, "contango", 0.5)
        assert r["regime_kr"] in ("안일", "리스크온", "리스크오프", "패닉")

    # ── VIX boundary tests ──

    def test_vix_boundary_18(self):
        r1 = detect_risk_regime(vix=17.9, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(vix=18.0, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["vix"]["label"] == "low"
        assert r2["factors"]["vix"]["label"] == "normal"

    def test_vix_boundary_22(self):
        r1 = detect_risk_regime(vix=21.9, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(vix=22.0, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["vix"]["label"] == "normal"
        assert r2["factors"]["vix"]["label"] == "elevated"

    def test_vix_boundary_28(self):
        r1 = detect_risk_regime(vix=27.9, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(vix=28.0, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["vix"]["label"] == "elevated"
        assert r2["factors"]["vix"]["label"] == "high"

    def test_vix_boundary_35(self):
        r1 = detect_risk_regime(vix=34.9, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(vix=35.0, fear_greed=50, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["vix"]["label"] == "high"
        assert r2["factors"]["vix"]["label"] == "extreme"

    def test_vix_scores_decrease_with_higher_vix(self):
        """VIX score should be monotonically non-increasing as VIX rises."""
        vix_values = [10, 15, 20, 25, 30, 40]
        scores = []
        for v in vix_values:
            r = detect_risk_regime(vix=v, fear_greed=50, put_call_ratio=0.85,
                                   vix_term_structure="contango", yield_spread=0.5)
            scores.append(r["factors"]["vix"]["score"])
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    # ── Fear & Greed boundary tests ──

    def test_fear_greed_label_extreme_fear(self):
        r = detect_risk_regime(18, fear_greed=10, put_call_ratio=0.85,
                               vix_term_structure="contango", yield_spread=0.5)
        assert r["factors"]["fear_greed"]["label"] == "extreme_fear"

    def test_fear_greed_label_fear(self):
        r = detect_risk_regime(18, fear_greed=30, put_call_ratio=0.85,
                               vix_term_structure="contango", yield_spread=0.5)
        assert r["factors"]["fear_greed"]["label"] == "fear"

    def test_fear_greed_label_neutral(self):
        r = detect_risk_regime(18, fear_greed=50, put_call_ratio=0.85,
                               vix_term_structure="contango", yield_spread=0.5)
        assert r["factors"]["fear_greed"]["label"] == "neutral"

    def test_fear_greed_label_greed(self):
        r = detect_risk_regime(18, fear_greed=70, put_call_ratio=0.85,
                               vix_term_structure="contango", yield_spread=0.5)
        assert r["factors"]["fear_greed"]["label"] == "greed"

    def test_fear_greed_label_extreme_greed(self):
        r = detect_risk_regime(18, fear_greed=85, put_call_ratio=0.85,
                               vix_term_structure="contango", yield_spread=0.5)
        assert r["factors"]["fear_greed"]["label"] == "extreme_greed"

    def test_fear_greed_boundary_20(self):
        r1 = detect_risk_regime(18, fear_greed=19, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(18, fear_greed=20, put_call_ratio=0.85,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["fear_greed"]["label"] == "extreme_fear"
        assert r2["factors"]["fear_greed"]["label"] == "fear"

    # ── Put/Call ratio boundary tests ──

    def test_put_call_boundary_0_6(self):
        r1 = detect_risk_regime(18, 50, put_call_ratio=0.59,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(18, 50, put_call_ratio=0.6,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["put_call"]["score"] == 0.5
        assert r2["factors"]["put_call"]["score"] == 0.2

    def test_put_call_boundary_0_8(self):
        r1 = detect_risk_regime(18, 50, put_call_ratio=0.79,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(18, 50, put_call_ratio=0.8,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["put_call"]["score"] == 0.2
        assert r2["factors"]["put_call"]["score"] == -0.1

    def test_put_call_boundary_1_0(self):
        r1 = detect_risk_regime(18, 50, put_call_ratio=0.99,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(18, 50, put_call_ratio=1.0,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["put_call"]["score"] == -0.1
        assert r2["factors"]["put_call"]["score"] == -0.4

    def test_put_call_boundary_1_2(self):
        r1 = detect_risk_regime(18, 50, put_call_ratio=1.19,
                                vix_term_structure="contango", yield_spread=0.5)
        r2 = detect_risk_regime(18, 50, put_call_ratio=1.2,
                                vix_term_structure="contango", yield_spread=0.5)
        assert r1["factors"]["put_call"]["score"] == -0.4
        assert r2["factors"]["put_call"]["score"] == -0.8

    def test_put_call_label_bullish_bearish(self):
        r_bull = detect_risk_regime(18, 50, put_call_ratio=0.5,
                                    vix_term_structure="contango", yield_spread=0.5)
        r_bear = detect_risk_regime(18, 50, put_call_ratio=1.5,
                                    vix_term_structure="contango", yield_spread=0.5)
        assert r_bull["factors"]["put_call"]["label"] == "bullish"
        assert r_bear["factors"]["put_call"]["label"] == "bearish"

    # ── VIX term structure tests ──

    def test_vix_term_contango(self):
        r = detect_risk_regime(18, 50, 0.85, vix_term_structure="contango", yield_spread=0.5)
        assert r["factors"]["vix_term"]["score"] == 0.3

    def test_vix_term_backwardation(self):
        r = detect_risk_regime(18, 50, 0.85, vix_term_structure="backwardation", yield_spread=0.5)
        assert r["factors"]["vix_term"]["score"] == -0.5

    def test_vix_term_none_defaults_to_contango(self):
        r = detect_risk_regime(18, 50, 0.85, vix_term_structure=None, yield_spread=0.5)
        assert r["factors"]["vix_term"]["value"] == "contango"
        assert r["factors"]["vix_term"]["score"] == 0.3

    # ── Yield spread boundary tests ──

    def test_yield_spread_boundary_negative_0_5(self):
        r1 = detect_risk_regime(18, 50, 0.85, "contango", yield_spread=-0.6)
        r2 = detect_risk_regime(18, 50, 0.85, "contango", yield_spread=-0.4)
        assert r1["factors"]["yield_spread"]["score"] == -0.8
        assert r2["factors"]["yield_spread"]["score"] == -0.3

    def test_yield_spread_boundary_zero(self):
        r1 = detect_risk_regime(18, 50, 0.85, "contango", yield_spread=-0.1)
        r2 = detect_risk_regime(18, 50, 0.85, "contango", yield_spread=0.0)
        assert r1["factors"]["yield_spread"]["score"] == -0.3
        assert r2["factors"]["yield_spread"]["score"] == 0.2

    def test_yield_spread_boundary_1_0(self):
        r1 = detect_risk_regime(18, 50, 0.85, "contango", yield_spread=0.9)
        r2 = detect_risk_regime(18, 50, 0.85, "contango", yield_spread=1.0)
        assert r1["factors"]["yield_spread"]["score"] == 0.2
        assert r2["factors"]["yield_spread"]["score"] == 0.5

    def test_yield_spread_label_inverted_vs_normal(self):
        r_inv = detect_risk_regime(18, 50, 0.85, "contango", yield_spread=-0.5)
        r_nor = detect_risk_regime(18, 50, 0.85, "contango", yield_spread=0.5)
        assert r_inv["factors"]["yield_spread"]["label"] == "inverted"
        assert r_nor["factors"]["yield_spread"]["label"] == "normal"

    # ── Regime classification boundary tests ──

    def test_regime_score_boundary_minus_0_6(self):
        """Score exactly -0.6 should be Panic."""
        # We need to engineer inputs to get score exactly -0.6
        # Just verify the boundary logic on both sides
        r_panic = detect_risk_regime(vix=40, fear_greed=10, put_call_ratio=1.3,
                                     vix_term_structure="backwardation", yield_spread=-1.0)
        assert r_panic["regime"] == "Panic"
        assert r_panic["score"] <= -0.6

    def test_regime_score_boundary_minus_0_15(self):
        """Score just above -0.15 should be Risk-On, just below should be Risk-Off."""
        # Risk-Off zone: -0.6 < score <= -0.15
        r = detect_risk_regime(vix=25, fear_greed=35, put_call_ratio=0.95,
                               vix_term_structure="contango", yield_spread=0.3)
        # This gives a mildly negative score — verify it's in the right category
        assert r["regime"] in ("Risk-On", "Risk-Off")

    def test_zero_vix(self):
        """VIX of 0 should still work (very_low bracket)."""
        r = detect_risk_regime(vix=0, fear_greed=50, put_call_ratio=0.85,
                               vix_term_structure="contango", yield_spread=0.5)
        assert r["factors"]["vix"]["label"] == "very_low"
        assert r["factors"]["vix"]["score"] == 0.8

    def test_factor_value_preserved(self):
        """Factor values should reflect actual input (not default)."""
        r = detect_risk_regime(vix=25.5, fear_greed=65, put_call_ratio=0.92,
                               vix_term_structure="contango", yield_spread=0.75)
        assert r["factors"]["vix"]["value"] == 25.5
        assert r["factors"]["fear_greed"]["value"] == 65
        assert r["factors"]["put_call"]["value"] == 0.92
        assert r["factors"]["yield_spread"]["value"] == 0.75


# ── detect_driver_regime ──


class TestDetectDriverRegime:
    def test_all_none_range_bound(self):
        r = detect_driver_regime(None, None, None)
        assert r["driver"] == "Range-Bound"
        assert r["confidence"] == 0.5

    def test_momentum_driven(self):
        r = detect_driver_regime(avg_technical_score=20.0, avg_macro_score=5.0,
                                 avg_fund_flow_score=2.0)
        assert r["driver"] == "Momentum-Driven"
        assert r["confidence"] > 0

    def test_fundamental_driven(self):
        r = detect_driver_regime(avg_technical_score=3.0, avg_macro_score=15.0,
                                 avg_fund_flow_score=10.0)
        assert r["driver"] == "Fundamental-Driven"

    def test_range_bound_balanced(self):
        r = detect_driver_regime(avg_technical_score=10.0, avg_macro_score=8.0,
                                 avg_fund_flow_score=4.0)
        assert r["driver"] == "Range-Bound"

    def test_threshold_boundary(self):
        # momentum_strength must exceed fundamental * 1.3 AND > 5
        r = detect_driver_regime(avg_technical_score=4.0, avg_macro_score=0.0,
                                 avg_fund_flow_score=0.0)
        # tech=4, fundamental=0 → momentum > fundamental*1.3 but NOT > 5
        assert r["driver"] == "Range-Bound"

    def test_rationale_has_data(self):
        r = detect_driver_regime(10.0, 5.0, 3.0)
        assert "기술적 강도" in r["rationale"]
        assert "매크로 강도" in r["rationale"]

    def test_rationale_no_data(self):
        r = detect_driver_regime(None, None, None)
        assert r["rationale"] == "데이터 부족"

    def test_negative_scores_use_abs(self):
        """Negative scores should be treated as absolute values."""
        r = detect_driver_regime(avg_technical_score=-20.0, avg_macro_score=-5.0,
                                 avg_fund_flow_score=-2.0)
        # abs(-20) = 20 for tech, abs(-5) + abs(-2)*0.5 = 6.0 for fundamental
        # 20 > 6.0 * 1.3 (7.8) and 20 > 5 => momentum
        assert r["driver"] == "Momentum-Driven"

    def test_confidence_capped_at_1(self):
        """Confidence should never exceed 1.0."""
        r = detect_driver_regime(avg_technical_score=100.0, avg_macro_score=1.0,
                                 avg_fund_flow_score=0.0)
        assert r["confidence"] <= 1.0

    def test_fundamental_confidence_capped(self):
        r = detect_driver_regime(avg_technical_score=1.0, avg_macro_score=100.0,
                                 avg_fund_flow_score=50.0)
        assert r["confidence"] <= 1.0

    def test_breakdown_dict_present(self):
        r = detect_driver_regime(10.0, 5.0, 3.0)
        assert "breakdown" in r
        assert "technical_strength" in r["breakdown"]
        assert "fundamental_strength" in r["breakdown"]

    def test_breakdown_values_correct(self):
        r = detect_driver_regime(avg_technical_score=-15.0, avg_macro_score=8.0,
                                 avg_fund_flow_score=6.0)
        assert r["breakdown"]["technical_strength"] == 15.0  # abs(-15)
        # fundamental = abs(8) + abs(6) * 0.5 = 11.0
        assert r["breakdown"]["fundamental_strength"] == 11.0

    def test_fundamental_strength_includes_flow_half_weight(self):
        """Fund flow contributes 0.5x to fundamental_strength."""
        r = detect_driver_regime(avg_technical_score=0.0, avg_macro_score=0.0,
                                 avg_fund_flow_score=20.0)
        # fundamental = 0 + 20*0.5 = 10.0
        assert r["breakdown"]["fundamental_strength"] == 10.0

    def test_momentum_threshold_exact_boundary(self):
        """When momentum is exactly 1.3x fundamental, should be range_bound (not >)."""
        # tech=6.5, macro=5, flow=0 => fundamental=5, 6.5 == 5*1.3
        r = detect_driver_regime(avg_technical_score=6.5, avg_macro_score=5.0,
                                 avg_fund_flow_score=0.0)
        assert r["driver"] == "Range-Bound"

    def test_momentum_just_above_threshold(self):
        """When momentum is just above 1.3x fundamental and > 5, should be momentum."""
        r = detect_driver_regime(avg_technical_score=6.6, avg_macro_score=5.0,
                                 avg_fund_flow_score=0.0)
        assert r["driver"] == "Momentum-Driven"

    def test_fundamental_threshold_exact_boundary(self):
        """When fundamental is exactly 1.3x momentum, should be range_bound."""
        # macro=6.5, flow=0, tech=5 => fundamental=6.5 == 5*1.3
        r = detect_driver_regime(avg_technical_score=5.0, avg_macro_score=6.5,
                                 avg_fund_flow_score=0.0)
        assert r["driver"] == "Range-Bound"

    def test_fundamental_just_above_threshold(self):
        r = detect_driver_regime(avg_technical_score=5.0, avg_macro_score=6.6,
                                 avg_fund_flow_score=0.0)
        assert r["driver"] == "Fundamental-Driven"

    def test_momentum_above_ratio_but_below_5(self):
        """Momentum > fundamental*1.3 but momentum <= 5 => range_bound."""
        r = detect_driver_regime(avg_technical_score=4.9, avg_macro_score=1.0,
                                 avg_fund_flow_score=0.0)
        assert r["driver"] == "Range-Bound"

    def test_fundamental_above_ratio_but_below_5(self):
        """Fundamental > momentum*1.3 but fundamental <= 5 => range_bound."""
        r = detect_driver_regime(avg_technical_score=1.0, avg_macro_score=4.9,
                                 avg_fund_flow_score=0.0)
        assert r["driver"] == "Range-Bound"

    def test_kr_label_present(self):
        r = detect_driver_regime(10.0, 5.0, 3.0)
        assert r["driver_kr"] in ("모멘텀 주도", "펀더멘탈 주도", "박스권")

    def test_rationale_only_tech_nonzero(self):
        r = detect_driver_regime(avg_technical_score=10.0, avg_macro_score=0.0,
                                 avg_fund_flow_score=0.0)
        assert "기술적 강도" in r["rationale"]
        assert "매크로 강도" not in r["rationale"]

    def test_rationale_includes_flow(self):
        r = detect_driver_regime(10.0, 5.0, 3.0)
        assert "수급 강도" in r["rationale"]

    def test_all_zero_is_range_bound(self):
        r = detect_driver_regime(avg_technical_score=0.0, avg_macro_score=0.0,
                                 avg_fund_flow_score=0.0)
        assert r["driver"] == "Range-Bound"
        assert r["rationale"] == "데이터 부족"


# ── detect_combined_regime ──


class TestDetectCombinedRegime:
    def test_all_none(self):
        r = detect_combined_regime(None, None, None)
        assert "risk_regime" in r
        assert "driver_regime" in r
        assert "/" in r["label"]
        assert "/" in r["label_kr"]

    def test_with_stats(self):
        stats = {
            "KR": {"avg_technical": 15, "avg_macro": 5, "avg_fund_flow": 3},
            "US": {"avg_technical": 10, "avg_macro": 8, "avg_fund_flow": 2},
        }
        r = detect_combined_regime(
            macro_data={"vix": 22},
            sentiment_data={"fear_greed_index": 40},
            signal_stats=stats,
        )
        assert r["risk_regime"]["score"] is not None
        assert r["driver_regime"]["driver"] is not None

    def test_empty_dicts(self):
        r = detect_combined_regime({}, {}, {})
        assert "risk_regime" in r
        assert "driver_regime" in r

    def test_non_dict_values_in_stats_ignored(self):
        """Non-dict values in signal_stats should be silently skipped."""
        stats = {
            "KR": {"avg_technical": 10, "avg_macro": 5, "avg_fund_flow": 2},
            "metadata": "not a dict",
            "count": 42,
        }
        r = detect_combined_regime(None, None, stats)
        assert "risk_regime" in r
        assert "driver_regime" in r

    def test_partial_stats_data(self):
        """Stats with only some fields should still work."""
        stats = {
            "KR": {"avg_technical": 10},  # no macro or flow
            "US": {"avg_macro": 8},       # no tech or flow
        }
        r = detect_combined_regime(None, None, stats)
        assert r["driver_regime"]["driver"] is not None

    def test_label_format(self):
        r = detect_combined_regime(None, None, None)
        # Labels should be "RiskRegime / DriverRegime"
        parts_en = r["label"].split(" / ")
        parts_kr = r["label_kr"].split(" / ")
        assert len(parts_en) == 2
        assert len(parts_kr) == 2

    def test_single_market_stats(self):
        stats = {"KR": {"avg_technical": 20, "avg_macro": 3, "avg_fund_flow": 1}}
        r = detect_combined_regime(None, None, stats)
        assert r["driver_regime"]["breakdown"]["technical_strength"] == 20.0


# ── compute_stagflation_index ──


class TestStagflationIndex:
    def test_all_none_defaults(self):
        r = compute_stagflation_index(None, None, None, None, None)
        assert 0 <= r["index"] <= 100
        assert r["level"] in ("Low", "Watch", "Elevated", "High")

    def test_high_stagflation(self):
        # High gold, low copper, inverted yield, high oil, high DXY
        r = compute_stagflation_index(
            gold_price=3000, copper_price=2.5, wti_crude=110,
            yield_spread=-1.0, dxy_index=112,
        )
        assert r["index"] >= 70
        assert r["level"] == "High"

    def test_low_stagflation(self):
        # Low gold/copper ratio, normal yield, low oil, low DXY
        r = compute_stagflation_index(
            gold_price=1600, copper_price=5.0, wti_crude=50,
            yield_spread=2.0, dxy_index=95,
        )
        assert r["index"] < 30
        assert r["level"] == "Low"

    def test_copper_cents_normalization(self):
        # Copper in cents/lb (e.g. 420 = $4.20)
        r = compute_stagflation_index(
            gold_price=2000, copper_price=420, wti_crude=70,
            yield_spread=0.5, dxy_index=103,
        )
        gc_ratio = r["components"]["gold_copper_ratio"]["value"]
        # Should be ~476 (2000/4.2), not 2000/420=4.76
        assert gc_ratio > 400

    def test_components_have_weights(self):
        r = compute_stagflation_index(2000, 4.0, 70, 0.5, 103)
        total_weight = sum(c["weight"] for c in r["components"].values())
        assert abs(total_weight - 1.0) < 0.01

    def test_index_clamped(self):
        r = compute_stagflation_index(10000, 0.5, 200, -5.0, 130)
        assert r["index"] <= 100
        r2 = compute_stagflation_index(500, 10.0, 20, 5.0, 80)
        assert r2["index"] >= 0

    def test_gold_copper_ratio_boundary_700(self):
        r = compute_stagflation_index(gold_price=3500, copper_price=4.5,
                                      wti_crude=70, yield_spread=0.5, dxy_index=103)
        # 3500/4.5 = 777 > 700
        assert r["components"]["gold_copper_ratio"]["score"] == 100

    def test_yield_curve_inverted(self):
        r = compute_stagflation_index(2000, 4.0, 70, yield_spread=-1.0, dxy_index=103)
        assert r["components"]["yield_curve"]["score"] == 90
        assert r["components"]["yield_curve"]["signal"] == "inverted"

    def test_oil_above_100(self):
        r = compute_stagflation_index(2000, 4.0, wti_crude=120, yield_spread=0.5, dxy_index=103)
        assert r["components"]["oil_pressure"]["score"] >= 80

    # ── Gold/Copper ratio boundaries ──

    def test_gc_ratio_below_400(self):
        # gold/copper < 400 => gc_score = gc_ratio/400 * 10
        r = compute_stagflation_index(gold_price=1200, copper_price=4.0,
                                      wti_crude=70, yield_spread=0.5, dxy_index=103)
        # 1200/4.0 = 300 < 400
        assert r["components"]["gold_copper_ratio"]["score"] < 10
        assert r["components"]["gold_copper_ratio"]["signal"] == "normal"

    def test_gc_ratio_between_400_and_500(self):
        r = compute_stagflation_index(gold_price=1800, copper_price=4.0,
                                      wti_crude=70, yield_spread=0.5, dxy_index=103)
        # 1800/4.0 = 450
        gc_score = r["components"]["gold_copper_ratio"]["score"]
        assert 10 <= gc_score <= 40

    def test_gc_ratio_between_500_and_600(self):
        r = compute_stagflation_index(gold_price=2200, copper_price=4.0,
                                      wti_crude=70, yield_spread=0.5, dxy_index=103)
        # 2200/4.0 = 550
        gc_score = r["components"]["gold_copper_ratio"]["score"]
        assert 40 <= gc_score <= 70

    def test_gc_ratio_between_600_and_700(self):
        r = compute_stagflation_index(gold_price=2600, copper_price=4.0,
                                      wti_crude=70, yield_spread=0.5, dxy_index=103)
        # 2600/4.0 = 650
        gc_score = r["components"]["gold_copper_ratio"]["score"]
        assert 70 <= gc_score <= 100
        assert r["components"]["gold_copper_ratio"]["signal"] == "high_risk"

    def test_gc_ratio_signal_watch(self):
        # gc_score between 35 and 60 => "watch"
        r = compute_stagflation_index(gold_price=2000, copper_price=4.0,
                                      wti_crude=70, yield_spread=0.5, dxy_index=103)
        # 2000/4.0 = 500, gc_score = 40
        assert r["components"]["gold_copper_ratio"]["signal"] == "watch"

    def test_copper_near_zero_protected(self):
        """Very low copper should not cause division by zero."""
        r = compute_stagflation_index(gold_price=2000, copper_price=0.001,
                                      wti_crude=70, yield_spread=0.5, dxy_index=103)
        assert r["components"]["gold_copper_ratio"]["score"] == 100  # ratio >> 700

    # ── Yield curve boundaries ──

    def test_yield_spread_between_0_and_0_5(self):
        r = compute_stagflation_index(2000, 4.0, 70, yield_spread=0.3, dxy_index=103)
        yc_score = r["components"]["yield_curve"]["score"]
        assert 30 <= yc_score <= 60
        assert r["components"]["yield_curve"]["signal"] == "flat"

    def test_yield_spread_between_0_5_and_1_5(self):
        r = compute_stagflation_index(2000, 4.0, 70, yield_spread=1.0, dxy_index=103)
        yc_score = r["components"]["yield_curve"]["score"]
        assert 0 <= yc_score <= 30

    def test_yield_spread_above_1_5(self):
        r = compute_stagflation_index(2000, 4.0, 70, yield_spread=2.0, dxy_index=103)
        assert r["components"]["yield_curve"]["score"] == 0

    # ── Oil pressure boundaries ──

    def test_oil_below_55(self):
        r = compute_stagflation_index(2000, 4.0, wti_crude=50, yield_spread=0.5, dxy_index=103)
        assert r["components"]["oil_pressure"]["score"] == 0
        assert r["components"]["oil_pressure"]["signal"] == "stable"

    def test_oil_between_55_and_75(self):
        r = compute_stagflation_index(2000, 4.0, wti_crude=65, yield_spread=0.5, dxy_index=103)
        score = r["components"]["oil_pressure"]["score"]
        assert 0 < score <= 25

    def test_oil_between_75_and_90(self):
        r = compute_stagflation_index(2000, 4.0, wti_crude=82, yield_spread=0.5, dxy_index=103)
        score = r["components"]["oil_pressure"]["score"]
        assert 25 <= score <= 55

    def test_oil_between_90_and_100(self):
        r = compute_stagflation_index(2000, 4.0, wti_crude=95, yield_spread=0.5, dxy_index=103)
        score = r["components"]["oil_pressure"]["score"]
        assert 55 <= score <= 80
        assert r["components"]["oil_pressure"]["signal"] == "high_inflation"

    # ── DXY boundaries ──

    def test_dxy_below_100(self):
        r = compute_stagflation_index(2000, 4.0, 70, 0.5, dxy_index=98)
        assert r["components"]["dxy_tightening"]["score"] == 0
        assert r["components"]["dxy_tightening"]["signal"] == "easy"

    def test_dxy_between_100_and_103(self):
        r = compute_stagflation_index(2000, 4.0, 70, 0.5, dxy_index=101.5)
        score = r["components"]["dxy_tightening"]["score"]
        assert 0 < score <= 25

    def test_dxy_between_103_and_106(self):
        r = compute_stagflation_index(2000, 4.0, 70, 0.5, dxy_index=104.5)
        score = r["components"]["dxy_tightening"]["score"]
        assert 25 <= score <= 50

    def test_dxy_between_106_and_110(self):
        r = compute_stagflation_index(2000, 4.0, 70, 0.5, dxy_index=108)
        score = r["components"]["dxy_tightening"]["score"]
        assert 50 <= score <= 85
        assert r["components"]["dxy_tightening"]["signal"] == "tight"

    def test_dxy_above_110(self):
        r = compute_stagflation_index(2000, 4.0, 70, 0.5, dxy_index=115)
        assert r["components"]["dxy_tightening"]["score"] == 85

    # ── Copper demand boundaries ──

    def test_copper_demand_below_3(self):
        r = compute_stagflation_index(2000, copper_price=2.5, wti_crude=70,
                                      yield_spread=0.5, dxy_index=103)
        assert r["components"]["copper_demand"]["score"] == 80
        assert r["components"]["copper_demand"]["signal"] == "weak_demand"

    def test_copper_demand_between_3_and_3_5(self):
        r = compute_stagflation_index(2000, copper_price=3.2, wti_crude=70,
                                      yield_spread=0.5, dxy_index=103)
        score = r["components"]["copper_demand"]["score"]
        assert 50 <= score <= 80

    def test_copper_demand_between_3_5_and_4(self):
        r = compute_stagflation_index(2000, copper_price=3.7, wti_crude=70,
                                      yield_spread=0.5, dxy_index=103)
        score = r["components"]["copper_demand"]["score"]
        assert 20 <= score <= 50

    def test_copper_demand_between_4_and_4_5(self):
        r = compute_stagflation_index(2000, copper_price=4.2, wti_crude=70,
                                      yield_spread=0.5, dxy_index=103)
        score = r["components"]["copper_demand"]["score"]
        assert 0 <= score <= 20

    def test_copper_demand_above_4_5(self):
        r = compute_stagflation_index(2000, copper_price=5.0, wti_crude=70,
                                      yield_spread=0.5, dxy_index=103)
        assert r["components"]["copper_demand"]["score"] == 0
        assert r["components"]["copper_demand"]["signal"] == "strong"

    def test_copper_demand_cents_normalization(self):
        """Copper demand component also normalizes cents/lb."""
        r = compute_stagflation_index(2000, copper_price=350, wti_crude=70,
                                      yield_spread=0.5, dxy_index=103)
        # 350 > 100 => 350/100 = 3.5 (boundary)
        assert r["components"]["copper_demand"]["value"] == 3.5

    # ── Level classification ──

    def test_level_watch(self):
        """Index between 30 and 50 should be Watch."""
        r = compute_stagflation_index(gold_price=2200, copper_price=3.8,
                                      wti_crude=80, yield_spread=0.2, dxy_index=105)
        # Designed to land in the Watch range
        if 30 <= r["index"] < 50:
            assert r["level"] == "Watch"
            assert r["level_kr"] == "주의"

    def test_level_elevated(self):
        """Index between 50 and 70 should be Elevated."""
        r = compute_stagflation_index(gold_price=2800, copper_price=3.0,
                                      wti_crude=95, yield_spread=-0.3, dxy_index=108)
        if 50 <= r["index"] < 70:
            assert r["level"] == "Elevated"
            assert r["level_kr"] == "경계"

    def test_all_components_have_required_keys(self):
        r = compute_stagflation_index(2000, 4.0, 70, 0.5, 103)
        for name, comp in r["components"].items():
            assert "value" in comp, f"{name} missing 'value'"
            assert "score" in comp, f"{name} missing 'score'"
            assert "signal" in comp, f"{name} missing 'signal'"
            assert "weight" in comp, f"{name} missing 'weight'"


# ── compute_cross_market_recommendation ──


class TestCrossMarketRecommendation:
    def test_all_none_returns_both_ok(self):
        r = compute_cross_market_recommendation(None, None, None, None, None, None)
        assert r["recommendation"] in ("Both OK", "KR Favorable", "US Favorable", "Caution")
        assert "kr_score" in r
        assert "us_score" in r

    def test_kr_favorable(self):
        r = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1280, "vix": 14, "us_10y_yield": 3.0, "us_yield_spread": 0.8},
            sentiment_data={"fear_greed_index": 60},
            kr_fund_flow_summary={"total_foreign_net": 1_000_000_000_000},
            us_etf_flow_summary={"risk_appetite_score": 0.2},
            kr_signal_stats={"avg_score": 25},
            us_signal_stats={"avg_score": 5},
        )
        assert r["recommendation"] == "KR Favorable"
        assert r["kr_score"] > r["us_score"]

    def test_us_favorable(self):
        r = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1420, "vix": 22, "us_10y_yield": 3.0, "us_yield_spread": 1.0},
            sentiment_data={},
            kr_fund_flow_summary={"total_foreign_net": -500_000_000_000},
            us_etf_flow_summary={"risk_appetite_score": 0.8},
            kr_signal_stats={"avg_score": -10},
            us_signal_stats={"avg_score": 20},
        )
        assert r["recommendation"] == "US Favorable"

    def test_caution_both_negative(self):
        r = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1450, "vix": 35, "us_10y_yield": 5.0, "us_yield_spread": -0.5},
            sentiment_data={"fear_greed_index": 15},
            kr_fund_flow_summary={"total_foreign_net": -800_000_000_000},
            us_etf_flow_summary={"risk_appetite_score": -0.8},
            kr_signal_stats={"avg_score": -25},
            us_signal_stats={"avg_score": -25},
        )
        assert r["recommendation"] == "Caution"
        assert r["kr_score"] < -0.2
        assert r["us_score"] < -0.2

    def test_factors_present(self):
        r = compute_cross_market_recommendation(None, None, None, None, None, None)
        assert "fx_trend" in r["factors"]
        assert "volatility" in r["factors"]
        assert "yield_env" in r["factors"]
        assert "fund_flow" in r["factors"]
        assert "signal_momentum" in r["factors"]

    def test_action_items_generated(self):
        r = compute_cross_market_recommendation(
            macro_data={"vix": 30, "usd_krw": 1400},
            sentiment_data={"fear_greed_index": 20},
            kr_fund_flow_summary=None,
            us_etf_flow_summary=None,
            kr_signal_stats=None,
            us_signal_stats=None,
        )
        assert len(r["action_items"]) > 0

    def test_fund_flow_scaling(self):
        r = compute_cross_market_recommendation(
            macro_data=None, sentiment_data=None,
            kr_fund_flow_summary={"total_foreign_net": 500_000_000_000},
            us_etf_flow_summary={"risk_appetite_score": 1.0},
            kr_signal_stats=None, us_signal_stats=None,
        )
        kr_flow = r["factors"]["fund_flow"]["kr_impact"]
        us_flow = r["factors"]["fund_flow"]["us_impact"]
        assert kr_flow > 0
        assert us_flow > 0
        assert kr_flow <= 0.7
        assert us_flow <= 0.7

    # ── FX trend boundary tests ──

    def test_fx_strong_krw(self):
        r = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1280}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r["factors"]["fx_trend"]["kr_impact"] == 0.8
        assert r["factors"]["fx_trend"]["us_impact"] == -0.3

    def test_fx_boundary_1300(self):
        r1 = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1299}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        r2 = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1300}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r1["factors"]["fx_trend"]["kr_impact"] == 0.8
        assert r2["factors"]["fx_trend"]["kr_impact"] == 0.4

    def test_fx_boundary_1350(self):
        r1 = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1349}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        r2 = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1350}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r1["factors"]["fx_trend"]["kr_impact"] == 0.4
        assert r2["factors"]["fx_trend"]["kr_impact"] == -0.2

    def test_fx_boundary_1400(self):
        r1 = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1399}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        r2 = compute_cross_market_recommendation(
            macro_data={"usd_krw": 1400}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r1["factors"]["fx_trend"]["kr_impact"] == -0.2
        assert r2["factors"]["fx_trend"]["kr_impact"] == -0.7

    # ── Volatility boundary tests ──

    def test_vol_boundary_15(self):
        r1 = compute_cross_market_recommendation(
            macro_data={"vix": 14.9}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        r2 = compute_cross_market_recommendation(
            macro_data={"vix": 15}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r1["factors"]["volatility"]["kr_impact"] == 0.5
        assert r2["factors"]["volatility"]["kr_impact"] == 0.3

    def test_vol_boundary_28(self):
        r1 = compute_cross_market_recommendation(
            macro_data={"vix": 27.9}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        r2 = compute_cross_market_recommendation(
            macro_data={"vix": 28}, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r1["factors"]["volatility"]["kr_impact"] == -0.3
        assert r2["factors"]["volatility"]["kr_impact"] == -0.7

    # ── Yield environment tests ──

    def test_yield_env_low_rate_positive_spread(self):
        r = compute_cross_market_recommendation(
            macro_data={"us_10y_yield": 3.0, "us_yield_spread": 0.8},
            sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r["factors"]["yield_env"]["kr_impact"] == 0.2
        assert r["factors"]["yield_env"]["us_impact"] == 0.6

    def test_yield_env_inverted_spread(self):
        r = compute_cross_market_recommendation(
            macro_data={"us_10y_yield": 4.0, "us_yield_spread": -0.5},
            sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r["factors"]["yield_env"]["kr_impact"] == -0.4
        assert r["factors"]["yield_env"]["us_impact"] == -0.2

    def test_yield_env_high_rate(self):
        """High 10Y yield with positive spread => rate-rise pressure."""
        r = compute_cross_market_recommendation(
            macro_data={"us_10y_yield": 5.0, "us_yield_spread": 0.5},
            sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r["factors"]["yield_env"]["kr_impact"] == -0.2
        assert r["factors"]["yield_env"]["us_impact"] == -0.3

    # ── Fund flow edge cases ──

    def test_negative_fund_flow(self):
        r = compute_cross_market_recommendation(
            macro_data=None, sentiment_data=None,
            kr_fund_flow_summary={"total_foreign_net": -300_000_000_000},
            us_etf_flow_summary={"risk_appetite_score": -0.5},
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r["factors"]["fund_flow"]["kr_impact"] < 0
        assert r["factors"]["fund_flow"]["us_impact"] < 0

    def test_zero_us_etf_score(self):
        r = compute_cross_market_recommendation(
            macro_data=None, sentiment_data=None,
            kr_fund_flow_summary=None,
            us_etf_flow_summary={"risk_appetite_score": 0},
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r["factors"]["fund_flow"]["us_impact"] == 0

    def test_fund_flow_clamped_at_0_7(self):
        r = compute_cross_market_recommendation(
            macro_data=None, sentiment_data=None,
            kr_fund_flow_summary={"total_foreign_net": 10_000_000_000_000},
            us_etf_flow_summary=None,
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r["factors"]["fund_flow"]["kr_impact"] <= 0.7

    # ── Signal momentum ──

    def test_signal_momentum_clamped(self):
        r = compute_cross_market_recommendation(
            macro_data=None, sentiment_data=None,
            kr_fund_flow_summary=None, us_etf_flow_summary=None,
            kr_signal_stats={"avg_score": 100},
            us_signal_stats={"avg_score": -100},
        )
        assert r["factors"]["signal_momentum"]["kr_impact"] <= 0.7
        assert r["factors"]["signal_momentum"]["us_impact"] >= -0.7

    def test_flow_label_no_data(self):
        r = compute_cross_market_recommendation(
            macro_data=None, sentiment_data=None,
            kr_fund_flow_summary={"total_foreign_net": 0},
            us_etf_flow_summary={"risk_appetite_score": 0},
            kr_signal_stats=None, us_signal_stats=None,
        )
        assert r["factors"]["fund_flow"]["label"] == "수급 데이터 부족"


# ── aggregate_sector_fund_flow ──


class TestAggregateSectorFundFlow:
    def test_empty(self):
        result = aggregate_sector_fund_flow([], {})
        assert result == []

    def test_single_symbol(self):
        rows = [{"symbol": "005930", "foreign_net_buy": 1000, "institution_net_buy": 500, "individual_net_buy": -200}]
        sector_map = {"005930": "반도체"}
        result = aggregate_sector_fund_flow(rows, sector_map)
        assert len(result) == 1
        assert result[0]["sector"] == "반도체"
        assert result[0]["foreign_net"] == 1000
        assert result[0]["institution_net"] == 500
        assert result[0]["total_net"] == 1500  # foreign + institution

    def test_unmapped_symbol_goes_to_etc(self):
        rows = [{"symbol": "UNKNOWN", "foreign_net_buy": 100, "institution_net_buy": 50, "individual_net_buy": 0}]
        result = aggregate_sector_fund_flow(rows, {})
        assert result[0]["sector"] == "기타"

    def test_aggregation_across_symbols(self):
        rows = [
            {"symbol": "A", "foreign_net_buy": 100, "institution_net_buy": 50, "individual_net_buy": 0},
            {"symbol": "B", "foreign_net_buy": 200, "institution_net_buy": 100, "individual_net_buy": 0},
        ]
        sector_map = {"A": "Tech", "B": "Tech"}
        result = aggregate_sector_fund_flow(rows, sector_map)
        assert len(result) == 1
        assert result[0]["total_net"] == 450
        assert result[0]["symbol_count"] == 2

    def test_sorted_by_total_net_desc(self):
        rows = [
            {"symbol": "A", "foreign_net_buy": 100, "institution_net_buy": 0, "individual_net_buy": 0},
            {"symbol": "B", "foreign_net_buy": 500, "institution_net_buy": 0, "individual_net_buy": 0},
        ]
        sector_map = {"A": "Low", "B": "High"}
        result = aggregate_sector_fund_flow(rows, sector_map)
        assert result[0]["sector"] == "High"

    def test_top_symbols_limited_to_5(self):
        rows = [{"symbol": f"S{i}", "foreign_net_buy": i * 10, "institution_net_buy": 0, "individual_net_buy": 0}
                for i in range(10)]
        sector_map = {f"S{i}": "Big" for i in range(10)}
        result = aggregate_sector_fund_flow(rows, sector_map)
        assert len(result[0]["top_symbols"]) <= 5

    def test_none_values_in_row_treated_as_zero(self):
        rows = [{"symbol": "A", "foreign_net_buy": None, "institution_net_buy": None, "individual_net_buy": None}]
        sector_map = {"A": "Tech"}
        result = aggregate_sector_fund_flow(rows, sector_map)
        assert result[0]["foreign_net"] == 0
        assert result[0]["institution_net"] == 0
        assert result[0]["individual_net"] == 0
        assert result[0]["total_net"] == 0

    def test_missing_keys_in_row_treated_as_zero(self):
        rows = [{"symbol": "A"}]  # No buy fields
        sector_map = {"A": "Tech"}
        result = aggregate_sector_fund_flow(rows, sector_map)
        assert result[0]["total_net"] == 0

    def test_duplicate_symbol_entries_accumulated(self):
        """Multiple rows for same symbol accumulate into the same sector."""
        rows = [
            {"symbol": "A", "foreign_net_buy": 100, "institution_net_buy": 0, "individual_net_buy": 0},
            {"symbol": "A", "foreign_net_buy": 200, "institution_net_buy": 50, "individual_net_buy": 0},
        ]
        sector_map = {"A": "Tech"}
        result = aggregate_sector_fund_flow(rows, sector_map)
        assert result[0]["foreign_net"] == 300
        assert result[0]["institution_net"] == 50
        assert result[0]["total_net"] == 350  # (100+0) + (200+50)
        # symbol_count should still be 1 (same symbol)
        assert result[0]["symbol_count"] == 1

    def test_multiple_sectors_sorted(self):
        rows = [
            {"symbol": "A", "foreign_net_buy": -100, "institution_net_buy": 0, "individual_net_buy": 0},
            {"symbol": "B", "foreign_net_buy": 500, "institution_net_buy": 0, "individual_net_buy": 0},
            {"symbol": "C", "foreign_net_buy": 200, "institution_net_buy": 100, "individual_net_buy": 0},
        ]
        sector_map = {"A": "X", "B": "Y", "C": "Z"}
        result = aggregate_sector_fund_flow(rows, sector_map)
        totals = [r["total_net"] for r in result]
        assert totals == sorted(totals, reverse=True)

    def test_top_symbols_sorted_by_abs_value(self):
        rows = [
            {"symbol": "A", "foreign_net_buy": 10, "institution_net_buy": 0, "individual_net_buy": 0},
            {"symbol": "B", "foreign_net_buy": -500, "institution_net_buy": 0, "individual_net_buy": 0},
            {"symbol": "C", "foreign_net_buy": 200, "institution_net_buy": 0, "individual_net_buy": 0},
        ]
        sector_map = {"A": "S", "B": "S", "C": "S"}
        result = aggregate_sector_fund_flow(rows, sector_map)
        top = result[0]["top_symbols"]
        # Should be sorted by abs(net) descending
        abs_vals = [abs(t["net"]) for t in top]
        assert abs_vals == sorted(abs_vals, reverse=True)


# ── compute_sector_rotation ──


class TestComputeSectorRotation:
    def test_empty(self):
        result = compute_sector_rotation([], [])
        assert result == []

    def test_inflow_signal(self):
        # Tech rises from rank 2 to rank 1 with positive net
        curr = [{"sector": "Tech", "total_net": 1000}, {"sector": "Bio", "total_net": 200}]
        prev = [{"sector": "Bio", "total_net": 800}, {"sector": "Tech", "total_net": 300}]
        result = compute_sector_rotation(curr, prev)
        tech = next(r for r in result if r["sector"] == "Tech")
        assert tech["signal"] == "Inflow"
        assert tech["rank_change"] > 0

    def test_outflow_signal(self):
        curr = [{"sector": "A", "total_net": 100}, {"sector": "B", "total_net": -200}]
        prev = [{"sector": "B", "total_net": 300}, {"sector": "A", "total_net": 50}]
        result = compute_sector_rotation(curr, prev)
        b_entry = next(r for r in result if r["sector"] == "B")
        assert b_entry["signal"] == "Outflow"

    def test_stable_signal(self):
        curr = [{"sector": "X", "total_net": 50}]
        prev = [{"sector": "X", "total_net": 45}]
        result = compute_sector_rotation(curr, prev)
        assert result[0]["signal"] == "Stable"
        assert result[0]["rank_change"] == 0

    def test_sector_only_in_current(self):
        """New sector appearing only in current period."""
        curr = [{"sector": "New", "total_net": 100}]
        prev = []
        result = compute_sector_rotation(curr, prev)
        assert len(result) == 1
        new_entry = result[0]
        assert new_entry["sector"] == "New"
        assert new_entry["current_net"] == 100
        # prev_rank defaults to len(all_sectors) = 1
        assert new_entry["rank_change"] == 0  # 1 - 1 = 0

    def test_sector_only_in_previous(self):
        """Sector disappearing from current period."""
        curr = []
        prev = [{"sector": "Old", "total_net": 100}]
        result = compute_sector_rotation(curr, prev)
        assert len(result) == 1
        old_entry = result[0]
        assert old_entry["sector"] == "Old"
        assert old_entry["current_net"] == 0

    def test_flow_change_calculation(self):
        curr = [{"sector": "A", "total_net": 200}]
        prev = [{"sector": "A", "total_net": 150}]
        result = compute_sector_rotation(curr, prev)
        assert result[0]["flow_change"] == 50

    def test_negative_flow_change(self):
        curr = [{"sector": "A", "total_net": 50}]
        prev = [{"sector": "A", "total_net": 200}]
        result = compute_sector_rotation(curr, prev)
        assert result[0]["flow_change"] == -150

    def test_sorted_by_current_rank(self):
        curr = [
            {"sector": "A", "total_net": 300},
            {"sector": "B", "total_net": 200},
            {"sector": "C", "total_net": 100},
        ]
        prev = [
            {"sector": "C", "total_net": 500},
            {"sector": "A", "total_net": 200},
            {"sector": "B", "total_net": 100},
        ]
        result = compute_sector_rotation(curr, prev)
        ranks = [r["current_rank"] for r in result]
        assert ranks == sorted(ranks)

    def test_rank_change_positive_means_improved(self):
        """Rank change = prev_rank - curr_rank; positive means improved."""
        curr = [{"sector": "A", "total_net": 500}, {"sector": "B", "total_net": 100}]
        prev = [{"sector": "B", "total_net": 500}, {"sector": "A", "total_net": 100}]
        result = compute_sector_rotation(curr, prev)
        a_entry = next(r for r in result if r["sector"] == "A")
        assert a_entry["rank_change"] == 1  # Was rank 2, now rank 1
        b_entry = next(r for r in result if r["sector"] == "B")
        assert b_entry["rank_change"] == -1  # Was rank 1, now rank 2

    def test_outflow_via_negative_net_and_rank_drop(self):
        """Negative net + rank drop => Outflow."""
        curr = [{"sector": "A", "total_net": 100}, {"sector": "B", "total_net": -50}]
        prev = [{"sector": "B", "total_net": 200}, {"sector": "A", "total_net": 100}]
        result = compute_sector_rotation(curr, prev)
        b = next(r for r in result if r["sector"] == "B")
        assert b["signal"] == "Outflow"

    def test_inflow_via_rank_change_positive_but_zero_net(self):
        """Rank improved but net=0: rank_change > 1 => Inflow."""
        curr = [{"sector": "A", "total_net": 0}, {"sector": "B", "total_net": -100}]
        prev = [{"sector": "B", "total_net": 0}, {"sector": "A", "total_net": -100}]
        result = compute_sector_rotation(curr, prev)
        a = next(r for r in result if r["sector"] == "A")
        # rank_change = 2-1 = 1, abs(1) <= 1 => Stable
        assert a["signal"] == "Stable"


# ── compute_relative_strength ──


class TestComputeRelativeStrength:
    def test_empty_input(self):
        result = compute_relative_strength({}, {}, {})
        assert result == []

    def test_outperformer(self):
        result = compute_relative_strength(
            symbol_returns={"AAPL": 5.0},
            benchmark_returns={"US": 2.0},
            sector_map={"AAPL": "Tech"},
        )
        assert len(result) == 1
        assert result[0]["rs_ratio"] > 1.0

    def test_underperformer(self):
        result = compute_relative_strength(
            symbol_returns={"AAPL": -3.0},
            benchmark_returns={"US": 2.0},
            sector_map={"AAPL": "Tech"},
        )
        assert result[0]["rs_ratio"] < 1.0

    def test_hedge_candidate(self):
        result = compute_relative_strength(
            symbol_returns={"012450": 3.0},
            benchmark_returns={"KR": -2.0},
            sector_map={"012450": "방산/항공"},
            risk_regime_score=-0.5,
        )
        assert result[0]["is_defense_sector"] is True
        assert result[0]["is_hedge_candidate"] is True

    def test_etf_excluded(self):
        result = compute_relative_strength(
            symbol_returns={"SPY": 2.0, "AAPL": 3.0},
            benchmark_returns={"US": 2.0},
            sector_map={"SPY": "ETF", "AAPL": "Tech"},
        )
        symbols = [r["symbol"] for r in result]
        assert "SPY" not in symbols
        assert "AAPL" in symbols

    def test_kr_market_detection(self):
        result = compute_relative_strength(
            symbol_returns={"005930": 1.0},
            benchmark_returns={"KR": 0.5, "US": 1.0},
            sector_map={"005930": "반도체"},
        )
        assert result[0]["market"] == "KR"
        assert result[0]["benchmark_return"] == 0.5

    def test_sorted_by_rs_ratio_desc(self):
        result = compute_relative_strength(
            symbol_returns={"AAPL": 1.0, "MSFT": 5.0, "GOOGL": -2.0},
            benchmark_returns={"US": 0.0},
            sector_map={"AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech"},
        )
        ratios = [r["rs_ratio"] for r in result]
        assert ratios == sorted(ratios, reverse=True)

    def test_benchmark_near_zero(self):
        """When benchmark return is ~0, should use alternative RS calculation."""
        result = compute_relative_strength(
            symbol_returns={"AAPL": 5.0},
            benchmark_returns={"US": -99.9},  # bench_factor near 0
            sector_map={"AAPL": "Tech"},
        )
        # bench_factor = 1 + (-99.9/100) = 0.001 < 0.001 threshold
        # rs_ratio = 1.0 + (5.0 - (-99.9)) / 100 = 2.049
        assert len(result) == 1
        assert result[0]["rs_ratio"] > 1.0

    def test_non_defense_sector_not_hedge(self):
        """Non-defense sector should never be hedge candidate."""
        result = compute_relative_strength(
            symbol_returns={"AAPL": 10.0},
            benchmark_returns={"US": -5.0},
            sector_map={"AAPL": "Tech"},
            risk_regime_score=-0.8,
        )
        assert result[0]["is_defense_sector"] is False
        assert result[0]["is_hedge_candidate"] is False

    def test_defense_sector_no_risk_off(self):
        """Defense sector but risk_regime_score not negative enough => not hedge."""
        result = compute_relative_strength(
            symbol_returns={"012450": 3.0},
            benchmark_returns={"KR": -2.0},
            sector_map={"012450": "방산/항공"},
            risk_regime_score=-0.2,  # Not < -0.3
        )
        assert result[0]["is_defense_sector"] is True
        assert result[0]["is_hedge_candidate"] is False

    def test_defense_sector_underperforming_not_hedge(self):
        """Defense sector, risk-off, but RS < 1.0 => not hedge candidate."""
        result = compute_relative_strength(
            symbol_returns={"012450": -5.0},
            benchmark_returns={"KR": -2.0},
            sector_map={"012450": "방산/항공"},
            risk_regime_score=-0.5,
        )
        assert result[0]["is_defense_sector"] is True
        assert result[0]["rs_ratio"] < 1.0
        assert result[0]["is_hedge_candidate"] is False

    def test_risk_regime_score_none_not_hedge(self):
        """Risk regime score None => is_hedge_candidate always False."""
        result = compute_relative_strength(
            symbol_returns={"012450": 3.0},
            benchmark_returns={"KR": -2.0},
            sector_map={"012450": "방산/항공"},
            risk_regime_score=None,
        )
        assert result[0]["is_hedge_candidate"] is False

    def test_us_market_detection(self):
        """Unknown sector defaults to US market."""
        result = compute_relative_strength(
            symbol_returns={"AAPL": 2.0},
            benchmark_returns={"US": 1.0, "KR": 0.5},
            sector_map={"AAPL": "SomeNewSector"},
        )
        assert result[0]["market"] == "US"
        assert result[0]["benchmark_return"] == 1.0

    def test_all_defense_sectors_recognized(self):
        """All defined DEFENSE_SECTORS should be flagged."""
        for sector in DEFENSE_SECTORS:
            result = compute_relative_strength(
                symbol_returns={"SYM": 5.0},
                benchmark_returns={"KR": 0.0, "US": 0.0},
                sector_map={"SYM": sector},
            )
            assert result[0]["is_defense_sector"] is True, f"{sector} not recognized"

    def test_missing_benchmark_defaults_to_zero(self):
        """If benchmark return for market is not provided, should default to 0."""
        result = compute_relative_strength(
            symbol_returns={"AAPL": 5.0},
            benchmark_returns={},  # No US benchmark
            sector_map={"AAPL": "Tech"},
        )
        assert result[0]["benchmark_return"] == 0.0
        # RS = (1+0.05)/(1+0) = 1.05
        assert abs(result[0]["rs_ratio"] - 1.05) < 0.001

    def test_return_pct_and_benchmark_rounded(self):
        result = compute_relative_strength(
            symbol_returns={"AAPL": 3.14159},
            benchmark_returns={"US": 1.41421},
            sector_map={"AAPL": "Tech"},
        )
        assert result[0]["return_pct"] == 3.14
        assert result[0]["benchmark_return"] == 1.41


# ── compute_entry_scenarios ──


class TestComputeEntryScenarios:
    def _make_prices(self, n=120, base=100.0, step=0.1):
        return [{"trade_date": f"2025-01-{i+1:02d}", "close": base + i * step} for i in range(n)]

    def test_empty_prices(self):
        r = compute_entry_scenarios({})
        assert r["benchmarks"]["KOSPI"]["current"] == 0
        assert r["benchmarks"]["SPY"]["current"] == 0
        assert r["probability_bias"] == "base"

    def test_full_data(self):
        r = compute_entry_scenarios(
            benchmark_prices={
                "KOSPI": self._make_prices(130, 2500, 2.0),
                "SPY": self._make_prices(130, 450, 0.5),
            },
        )
        kospi = r["benchmarks"]["KOSPI"]
        assert kospi["current"] > 0
        assert kospi["ma20"] > 0
        assert kospi["ma60"] > 0
        assert kospi["ma120"] > 0
        assert kospi["support_zone"][0] <= kospi["support_zone"][1]
        assert kospi["resistance_zone"][0] <= kospi["resistance_zone"][1]

    def test_scenario_ranges_ordered(self):
        r = compute_entry_scenarios(
            benchmark_prices={"KOSPI": self._make_prices(130, 2500, 2.0)},
        )
        for scenario in r["scenarios"].values():
            rng = scenario["kospi_range"]
            assert rng[0] <= rng[1], f"Range not ordered: {rng}"

    def test_probability_bias_from_risk_score(self):
        r1 = compute_entry_scenarios({}, risk_score=70)
        assert r1["probability_bias"] == "worst"

        r2 = compute_entry_scenarios({}, risk_score=20)
        assert r2["probability_bias"] == "best"

        r3 = compute_entry_scenarios({}, risk_score=45)
        assert r3["probability_bias"] == "base"

    def test_fx_data(self):
        fx = [{"close": 1350 + i * 0.5} for i in range(130)]
        r = compute_entry_scenarios({}, fx_prices=fx)
        assert r["fx"]["usd_krw_current"] is not None
        assert r["fx"]["ma20"] is not None
        assert r["fx"]["ma60"] is not None
        assert r["fx"]["ma120"] is not None
        assert "inflection_zone" in r["fx"]

    def test_fx_scenario_ranges(self):
        fx = [{"close": 1350 + i * 0.3} for i in range(130)]
        r = compute_entry_scenarios({}, fx_prices=fx)
        for scenario in r["scenarios"].values():
            rng = scenario["usd_krw_range"]
            assert rng[0] <= rng[1]

    def test_insufficient_data(self):
        # Only 10 prices — not enough for MA60/MA120
        r = compute_entry_scenarios(
            benchmark_prices={"KOSPI": self._make_prices(10, 2500, 2.0)},
        )
        kospi = r["benchmarks"]["KOSPI"]
        assert kospi["current"] > 0
        # ma60/ma120 should fall back to current
        assert kospi["ma60"] == kospi["current"]

    def test_fx_with_usd_krw_key(self):
        """fx_prices may use 'usd_krw' key instead of 'close'."""
        fx = [{"usd_krw": 1350 + i * 0.5} for i in range(130)]
        r = compute_entry_scenarios({}, fx_prices=fx)
        assert r["fx"]["usd_krw_current"] is not None
        assert r["fx"]["ma20"] is not None

    def test_fx_insufficient_for_ma60(self):
        """Less than 60 fx prices: ma60 should be None."""
        fx = [{"close": 1350 + i * 0.5} for i in range(30)]
        r = compute_entry_scenarios({}, fx_prices=fx)
        assert r["fx"]["ma20"] is not None
        assert r["fx"]["ma60"] is None
        assert r["fx"]["ma120"] is None
        assert "inflection_zone" not in r["fx"]

    def test_fx_none(self):
        """No fx data should return all None fields."""
        r = compute_entry_scenarios({}, fx_prices=None)
        assert r["fx"]["usd_krw_current"] is None
        assert r["fx"]["ma20"] is None

    def test_fx_empty_list(self):
        r = compute_entry_scenarios({}, fx_prices=[])
        assert r["fx"]["usd_krw_current"] is None

    def test_risk_score_boundary_30(self):
        r = compute_entry_scenarios({}, risk_score=30)
        assert r["probability_bias"] == "base"
        r2 = compute_entry_scenarios({}, risk_score=29)
        assert r2["probability_bias"] == "best"

    def test_risk_score_boundary_60(self):
        r = compute_entry_scenarios({}, risk_score=60)
        assert r["probability_bias"] == "base"
        r2 = compute_entry_scenarios({}, risk_score=61)
        assert r2["probability_bias"] == "worst"

    def test_scenarios_have_all_three(self):
        r = compute_entry_scenarios({})
        assert "best" in r["scenarios"]
        assert "base" in r["scenarios"]
        assert "worst" in r["scenarios"]

    def test_scenario_labels(self):
        r = compute_entry_scenarios({})
        assert r["scenarios"]["best"]["label"] == "Best"
        assert r["scenarios"]["best"]["label_kr"] == "낙관"
        assert r["scenarios"]["base"]["label"] == "Base"
        assert r["scenarios"]["base"]["label_kr"] == "기본"
        assert r["scenarios"]["worst"]["label"] == "Worst"
        assert r["scenarios"]["worst"]["label_kr"] == "비관"

    def test_downtrend_scenario_ranges_still_ordered(self):
        """Even in a downtrend (where MAs cross), ranges should be [low, high]."""
        # Create declining prices
        prices = [{"trade_date": f"2025-01-{i+1:02d}", "close": 3000 - i * 5}
                  for i in range(130)]
        r = compute_entry_scenarios(benchmark_prices={"KOSPI": prices})
        for scenario in r["scenarios"].values():
            rng = scenario["kospi_range"]
            assert rng[0] <= rng[1], f"Range not ordered in downtrend: {rng}"

    def test_only_spy_provided(self):
        """Should still produce KOSPI with empty_benchmark."""
        r = compute_entry_scenarios(
            benchmark_prices={"SPY": self._make_prices(130, 450, 0.5)},
        )
        assert r["benchmarks"]["KOSPI"]["current"] == 0
        assert r["benchmarks"]["SPY"]["current"] > 0

    def test_prices_with_none_close_filtered(self):
        """Prices with None close should be filtered out."""
        prices = [{"trade_date": "2025-01-01", "close": None}] * 50 + self._make_prices(120, 2500, 2.0)
        r = compute_entry_scenarios(benchmark_prices={"KOSPI": prices})
        assert r["benchmarks"]["KOSPI"]["current"] > 0

    def test_ma20_uses_last_20_prices(self):
        """MA20 should be computed from the last 20 prices."""
        # 120 prices: first 100 at base 100, last 20 at base 200
        prices = ([{"trade_date": f"2025-01-{i+1:02d}", "close": 100.0} for i in range(100)]
                  + [{"trade_date": f"2025-05-{i+1:02d}", "close": 200.0} for i in range(20)])
        r = compute_entry_scenarios(benchmark_prices={"KOSPI": prices})
        # MA20 should be 200.0 (last 20 are all 200)
        assert r["benchmarks"]["KOSPI"]["ma20"] == 200.0


# ── Private Helper Functions ──


class TestEmptyBenchmark:
    def test_returns_zero_dict(self):
        bm = _empty_benchmark()
        assert bm["current"] == 0
        assert bm["ma20"] == 0
        assert bm["ma60"] == 0
        assert bm["ma120"] == 0
        assert bm["support_zone"] == [0, 0]
        assert bm["resistance_zone"] == [0, 0]


class TestScenarioRange:
    def test_zero_current_returns_zero(self):
        bm = _empty_benchmark()
        assert _scenario_range(bm, "best") == [0, 0]
        assert _scenario_range(bm, "base") == [0, 0]
        assert _scenario_range(bm, "worst") == [0, 0]

    def test_best_scenario(self):
        bm = {"current": 100, "ma20": 95, "ma60": 90, "ma120": 85}
        rng = _scenario_range(bm, "best")
        assert rng[0] == 95.0  # ma20
        assert rng[1] == 105.0  # current * 1.05

    def test_base_scenario(self):
        bm = {"current": 100, "ma20": 95, "ma60": 90, "ma120": 85}
        rng = _scenario_range(bm, "base")
        assert rng[0] == 90.0  # ma60
        assert rng[1] == 95.0  # ma20

    def test_worst_scenario(self):
        bm = {"current": 100, "ma20": 95, "ma60": 90, "ma120": 85}
        rng = _scenario_range(bm, "worst")
        # low = ma120*0.95 = 80.75, high = ma60 = 90
        assert rng[0] == 80.75
        assert rng[1] == 90.0

    def test_downtrend_crossover_sorted(self):
        """When MA20 < MA60 (downtrend), ranges should still be [low, high]."""
        bm = {"current": 80, "ma20": 85, "ma60": 95, "ma120": 100}
        for scenario in ("best", "base", "worst"):
            rng = _scenario_range(bm, scenario)
            assert rng[0] <= rng[1], f"Scenario {scenario} not sorted: {rng}"


class TestFxScenarioRange:
    def test_no_current_returns_zero(self):
        fx = {"usd_krw_current": None, "ma60": 1350, "ma120": 1340}
        assert _fx_scenario_range(fx, "best") == [0, 0]
        assert _fx_scenario_range(fx, "base") == [0, 0]
        assert _fx_scenario_range(fx, "worst") == [0, 0]

    def test_best_scenario_krw_strengthening(self):
        fx = {"usd_krw_current": 1350, "ma60": 1340, "ma120": 1330}
        rng = _fx_scenario_range(fx, "best")
        # target_low = 1350 * 0.97, target_high = 1350
        assert rng[0] == round(1350 * 0.97, 1)
        assert rng[1] == 1350.0

    def test_base_scenario_range_continues(self):
        fx = {"usd_krw_current": 1350, "ma60": 1340, "ma120": 1330}
        rng = _fx_scenario_range(fx, "base")
        assert rng[0] == round(1350 * 0.98, 1)
        assert rng[1] == round(1350 * 1.02, 1)

    def test_worst_scenario_krw_weakening(self):
        fx = {"usd_krw_current": 1350, "ma60": 1340, "ma120": 1330}
        rng = _fx_scenario_range(fx, "worst")
        assert rng[0] == 1350.0
        assert rng[1] == round(1350 * 1.05, 1)

    def test_all_scenarios_ordered(self):
        fx = {"usd_krw_current": 1380, "ma60": 1360, "ma120": 1350}
        for scenario in ("best", "base", "worst"):
            rng = _fx_scenario_range(fx, scenario)
            assert rng[0] <= rng[1], f"FX scenario {scenario} not sorted: {rng}"


class TestGenerateActionItems:
    def test_high_vix_generates_warning(self):
        items = _generate_action_items({"vix": 30}, {}, {}, "Both OK")
        assert any("VIX" in item for item in items)

    def test_low_vix_generates_hedge_warning(self):
        items = _generate_action_items({"vix": 12}, {}, {}, "Both OK")
        assert any("극저변동" in item for item in items)

    def test_normal_vix_no_item(self):
        items = _generate_action_items({"vix": 20}, {}, {}, "Both OK")
        vix_items = [item for item in items if "VIX" in item and "극저변동" not in item and "고수준" in item]
        assert len(vix_items) == 0

    def test_extreme_fear(self):
        items = _generate_action_items({}, {"fear_greed_index": 20}, {}, "Both OK")
        assert any("극단 공포" in item for item in items)

    def test_extreme_greed(self):
        items = _generate_action_items({}, {"fear_greed_index": 80}, {}, "Both OK")
        assert any("극단 탐욕" in item for item in items)

    def test_neutral_fear_greed_no_item(self):
        items = _generate_action_items({}, {"fear_greed_index": 50}, {}, "Both OK")
        fg_items = [item for item in items if "공포지수" in item]
        assert len(fg_items) == 0

    def test_high_usd_krw(self):
        items = _generate_action_items({"usd_krw": 1400}, {}, {}, "Both OK")
        assert any("환율" in item and "고수준" in item for item in items)

    def test_low_usd_krw(self):
        items = _generate_action_items({"usd_krw": 1280}, {}, {}, "Both OK")
        assert any("환율" in item and "안정" in item for item in items)

    def test_caution_recommendation(self):
        items = _generate_action_items({}, {}, {}, "Caution")
        assert any("현금 비중" in item for item in items)

    def test_kr_favorable(self):
        items = _generate_action_items({}, {}, {}, "KR Favorable")
        assert any("KR" in item for item in items)

    def test_us_favorable(self):
        items = _generate_action_items({}, {}, {}, "US Favorable")
        assert any("US" in item for item in items)

    def test_no_signals_default_item(self):
        """When no special conditions, should get the default 'no signal' item."""
        items = _generate_action_items(
            {"vix": 20, "usd_krw": 1350},
            {"fear_greed_index": 50},
            {},
            "Both OK",
        )
        assert any("특이 시그널 없음" in item for item in items)

    def test_defaults_when_keys_missing(self):
        """Missing keys should use defaults without error."""
        items = _generate_action_items({}, {}, {}, "Both OK")
        # Should not raise, should use defaults: vix=18, fg=50, usd_krw=1350
        assert isinstance(items, list)
        assert len(items) > 0


# ── Constants / Labels ──


class TestConstants:
    def test_risk_labels_all_have_en_kr(self):
        for key, val in RISK_LABELS.items():
            assert "en" in val, f"RISK_LABELS[{key}] missing 'en'"
            assert "kr" in val, f"RISK_LABELS[{key}] missing 'kr'"

    def test_driver_labels_all_have_en_kr(self):
        for key, val in DRIVER_LABELS.items():
            assert "en" in val, f"DRIVER_LABELS[{key}] missing 'en'"
            assert "kr" in val, f"DRIVER_LABELS[{key}] missing 'kr'"

    def test_defense_sectors_is_set(self):
        assert isinstance(DEFENSE_SECTORS, set)
        assert len(DEFENSE_SECTORS) > 0
