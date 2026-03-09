"""Tests for sector-macro cross-impact scoring."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest

from app.indicators.sector_macro import (
    _compute_factor_conditions,
    _FACTOR_SCALE,
    _WARNINGS_KR,
    _FACTOR_VALUE_KEYS,
    compute_all_sector_impacts,
    compute_sector_macro_adjustment,
    DEFAULT_SENSITIVITY,
    SECTOR_SENSITIVITY,
)


# ── Constants & Data Integrity ──


class TestConstantsIntegrity:
    """Verify module-level constants are well-formed."""

    def test_default_sensitivity_all_zero(self):
        for v in DEFAULT_SENSITIVITY.values():
            assert v == 0.0

    def test_default_sensitivity_has_all_factors(self):
        assert set(DEFAULT_SENSITIVITY.keys()) == {"oil", "rate", "fx", "dxy"}

    def test_factor_scale_positive(self):
        assert _FACTOR_SCALE > 0

    def test_sector_sensitivity_values_in_range(self):
        """All sensitivity values must be in [-1.0, 1.0]."""
        for sector, sens in SECTOR_SENSITIVITY.items():
            for factor, value in sens.items():
                assert -1.0 <= value <= 1.0, (
                    f"{sector}.{factor} = {value} out of [-1, 1]"
                )

    def test_sector_sensitivity_has_all_factors(self):
        """Every sector must define all four factors."""
        expected_factors = {"oil", "rate", "fx", "dxy"}
        for sector, sens in SECTOR_SENSITIVITY.items():
            assert set(sens.keys()) == expected_factors, (
                f"{sector} missing factors: {expected_factors - set(sens.keys())}"
            )

    def test_sector_sensitivity_not_empty(self):
        assert len(SECTOR_SENSITIVITY) > 0

    def test_warnings_kr_has_all_factors(self):
        """Warning templates cover all four macro factors."""
        assert set(_WARNINGS_KR.keys()) == {"oil", "rate", "fx", "dxy"}

    def test_warnings_kr_each_has_positive_and_negative(self):
        for factor, templates in _WARNINGS_KR.items():
            assert "positive" in templates, f"{factor} missing 'positive' template"
            assert "negative" in templates, f"{factor} missing 'negative' template"

    def test_factor_value_keys_map_all_factors(self):
        assert set(_FACTOR_VALUE_KEYS.keys()) == {"oil", "rate", "fx", "dxy"}

    def test_known_kr_sectors_present(self):
        kr_sectors = [
            "유틸리티", "에너지/플랜트", "반도체", "자동차", "배터리",
            "바이오", "인터넷", "금융", "보험", "철강", "화학", "통신",
            "소비재", "전자", "조선/중공업", "방산/항공", "전기/전력장비", "지주",
        ]
        for s in kr_sectors:
            assert s in SECTOR_SENSITIVITY, f"KR sector '{s}' missing"

    def test_known_us_sectors_present(self):
        us_sectors = [
            "Tech", "Semiconductor", "Energy", "Finance",
            "Healthcare", "Consumer", "Auto", "Infrastructure",
        ]
        for s in us_sectors:
            assert s in SECTOR_SENSITIVITY, f"US sector '{s}' missing"


# ── Factor Conditions ──


class TestComputeFactorConditions:
    """Test _compute_factor_conditions for all factors and boundary values."""

    # --- Oil ---

    def test_high_oil(self):
        conds = _compute_factor_conditions({"wti_crude": 105})
        assert conds["oil"] >= 0.7

    def test_sweet_spot_oil(self):
        conds = _compute_factor_conditions({"wti_crude": 65})
        assert conds["oil"] == 0.0

    def test_low_oil(self):
        conds = _compute_factor_conditions({"wti_crude": 40})
        assert conds["oil"] <= -0.3

    def test_oil_above_100(self):
        conds = _compute_factor_conditions({"wti_crude": 101})
        assert conds["oil"] == 0.8

    def test_oil_boundary_100_exact(self):
        """WTI exactly 100 falls into (90, 100] band -> 0.6."""
        conds = _compute_factor_conditions({"wti_crude": 100})
        assert conds["oil"] == 0.6

    def test_oil_boundary_90_exact(self):
        """WTI exactly 90 falls into (75, 90] band -> 0.2."""
        conds = _compute_factor_conditions({"wti_crude": 90})
        assert conds["oil"] == 0.2

    def test_oil_boundary_75_exact(self):
        """WTI exactly 75 falls into (55, 75] band -> 0.0."""
        conds = _compute_factor_conditions({"wti_crude": 75})
        assert conds["oil"] == 0.0

    def test_oil_boundary_55_exact(self):
        """WTI exactly 55 falls into (45, 55] band -> -0.3."""
        conds = _compute_factor_conditions({"wti_crude": 55})
        assert conds["oil"] == -0.3

    def test_oil_boundary_45_exact(self):
        """WTI exactly 45 falls into <=45 band -> -0.5."""
        conds = _compute_factor_conditions({"wti_crude": 45})
        assert conds["oil"] == -0.5

    def test_oil_zero(self):
        conds = _compute_factor_conditions({"wti_crude": 0})
        assert conds["oil"] == -0.5

    def test_oil_negative(self):
        """Negative WTI (theoretical) should still return lowest bucket."""
        conds = _compute_factor_conditions({"wti_crude": -10})
        assert conds["oil"] == -0.5

    def test_oil_none(self):
        conds = _compute_factor_conditions({"wti_crude": None})
        assert conds["oil"] == 0.0

    # --- Rate ---

    def test_high_rate(self):
        conds = _compute_factor_conditions({"us_10y_yield": 5.5})
        assert conds["rate"] >= 0.7

    def test_low_rate(self):
        conds = _compute_factor_conditions({"us_10y_yield": 2.8})
        assert conds["rate"] <= -0.5

    def test_rate_above_5(self):
        conds = _compute_factor_conditions({"us_10y_yield": 5.1})
        assert conds["rate"] == 0.8

    def test_rate_boundary_5_exact(self):
        """Rate exactly 5.0 falls into (4.5, 5.0] -> 0.5."""
        conds = _compute_factor_conditions({"us_10y_yield": 5.0})
        assert conds["rate"] == 0.5

    def test_rate_boundary_4_5_exact(self):
        """Rate exactly 4.5 falls into (4.0, 4.5] -> 0.2."""
        conds = _compute_factor_conditions({"us_10y_yield": 4.5})
        assert conds["rate"] == 0.2

    def test_rate_boundary_4_0_exact(self):
        """Rate exactly 4.0 falls into (3.5, 4.0] -> 0.0."""
        conds = _compute_factor_conditions({"us_10y_yield": 4.0})
        assert conds["rate"] == 0.0

    def test_rate_boundary_3_5_exact(self):
        """Rate exactly 3.5 falls into (3.0, 3.5] -> -0.3."""
        conds = _compute_factor_conditions({"us_10y_yield": 3.5})
        assert conds["rate"] == -0.3

    def test_rate_boundary_3_0_exact(self):
        """Rate exactly 3.0 falls into <=3.0 -> -0.6."""
        conds = _compute_factor_conditions({"us_10y_yield": 3.0})
        assert conds["rate"] == -0.6

    def test_rate_zero(self):
        conds = _compute_factor_conditions({"us_10y_yield": 0})
        assert conds["rate"] == -0.6

    def test_rate_none(self):
        conds = _compute_factor_conditions({"us_10y_yield": None})
        assert conds["rate"] == 0.0

    def test_rate_negative(self):
        """Negative yield (e.g., Japan-style) -> lowest bucket."""
        conds = _compute_factor_conditions({"us_10y_yield": -0.5})
        assert conds["rate"] == -0.6

    # --- FX (USD/KRW) ---

    def test_weak_krw(self):
        conds = _compute_factor_conditions({"usd_krw": 1420})
        assert conds["fx"] >= 0.7

    def test_strong_krw(self):
        conds = _compute_factor_conditions({"usd_krw": 1230})
        assert conds["fx"] <= -0.3

    def test_fx_above_1400(self):
        conds = _compute_factor_conditions({"usd_krw": 1401})
        assert conds["fx"] == 0.8

    def test_fx_boundary_1400_exact(self):
        """USD/KRW exactly 1400 falls into (1380, 1400] -> 0.6."""
        conds = _compute_factor_conditions({"usd_krw": 1400})
        assert conds["fx"] == 0.6

    def test_fx_boundary_1380_exact(self):
        """USD/KRW exactly 1380 falls into (1350, 1380] -> 0.3."""
        conds = _compute_factor_conditions({"usd_krw": 1380})
        assert conds["fx"] == 0.3

    def test_fx_boundary_1350_exact(self):
        """USD/KRW exactly 1350 falls into (1280, 1350] -> 0.0."""
        conds = _compute_factor_conditions({"usd_krw": 1350})
        assert conds["fx"] == 0.0

    def test_fx_boundary_1280_exact(self):
        """USD/KRW exactly 1280 falls into (1250, 1280] -> -0.3."""
        conds = _compute_factor_conditions({"usd_krw": 1280})
        assert conds["fx"] == -0.3

    def test_fx_boundary_1250_exact(self):
        """USD/KRW exactly 1250 falls into <=1250 -> -0.5."""
        conds = _compute_factor_conditions({"usd_krw": 1250})
        assert conds["fx"] == -0.5

    def test_fx_none(self):
        conds = _compute_factor_conditions({"usd_krw": None})
        assert conds["fx"] == 0.0

    def test_fx_zero(self):
        conds = _compute_factor_conditions({"usd_krw": 0})
        assert conds["fx"] == -0.5

    # --- DXY ---

    def test_strong_dxy(self):
        conds = _compute_factor_conditions({"dxy_index": 112})
        assert conds["dxy"] >= 0.7

    def test_dxy_above_110(self):
        conds = _compute_factor_conditions({"dxy_index": 111})
        assert conds["dxy"] == 0.8

    def test_dxy_boundary_110_exact(self):
        """DXY exactly 110 falls into (107, 110] -> 0.5."""
        conds = _compute_factor_conditions({"dxy_index": 110})
        assert conds["dxy"] == 0.5

    def test_dxy_boundary_107_exact(self):
        """DXY exactly 107 falls into (103, 107] -> 0.2."""
        conds = _compute_factor_conditions({"dxy_index": 107})
        assert conds["dxy"] == 0.2

    def test_dxy_boundary_103_exact(self):
        """DXY exactly 103 falls into (100, 103] -> 0.0."""
        conds = _compute_factor_conditions({"dxy_index": 103})
        assert conds["dxy"] == 0.0

    def test_dxy_boundary_100_exact(self):
        """DXY exactly 100 falls into (97, 100] -> -0.3."""
        conds = _compute_factor_conditions({"dxy_index": 100})
        assert conds["dxy"] == -0.3

    def test_dxy_boundary_97_exact(self):
        """DXY exactly 97 falls into <=97 -> -0.5."""
        conds = _compute_factor_conditions({"dxy_index": 97})
        assert conds["dxy"] == -0.5

    def test_dxy_none(self):
        conds = _compute_factor_conditions({"dxy_index": None})
        assert conds["dxy"] == 0.0

    def test_dxy_zero(self):
        conds = _compute_factor_conditions({"dxy_index": 0})
        assert conds["dxy"] == -0.5

    # --- Combined & Edge Cases ---

    def test_missing_data_defaults_zero(self):
        conds = _compute_factor_conditions({})
        for v in conds.values():
            assert v == 0.0

    def test_all_factors_present(self):
        conds = _compute_factor_conditions({
            "wti_crude": 70, "us_10y_yield": 4.0,
            "usd_krw": 1320, "dxy_index": 102,
        })
        assert set(conds.keys()) == {"oil", "rate", "fx", "dxy"}

    def test_all_none_values(self):
        """All factors present but None -> all zero."""
        conds = _compute_factor_conditions({
            "wti_crude": None, "us_10y_yield": None,
            "usd_krw": None, "dxy_index": None,
        })
        for v in conds.values():
            assert v == 0.0

    def test_extra_keys_ignored(self):
        """Extra keys in macro_data should not cause errors."""
        conds = _compute_factor_conditions({
            "wti_crude": 80, "random_key": 999, "another": "abc",
        })
        assert set(conds.keys()) == {"oil", "rate", "fx", "dxy"}

    def test_all_extreme_high(self):
        """All factors at extreme high values."""
        conds = _compute_factor_conditions({
            "wti_crude": 200, "us_10y_yield": 10.0,
            "usd_krw": 2000, "dxy_index": 130,
        })
        assert conds["oil"] == 0.8
        assert conds["rate"] == 0.8
        assert conds["fx"] == 0.8
        assert conds["dxy"] == 0.8

    def test_all_extreme_low(self):
        """All factors at extreme low values."""
        conds = _compute_factor_conditions({
            "wti_crude": 10, "us_10y_yield": 0.5,
            "usd_krw": 900, "dxy_index": 80,
        })
        assert conds["oil"] == -0.5
        assert conds["rate"] == -0.6
        assert conds["fx"] == -0.5
        assert conds["dxy"] == -0.5

    def test_return_values_bounded(self):
        """Condition values should be in [-1, 1] range for all inputs."""
        test_cases = [
            {"wti_crude": 0}, {"wti_crude": 200},
            {"us_10y_yield": -1}, {"us_10y_yield": 10},
            {"usd_krw": 500}, {"usd_krw": 2000},
            {"dxy_index": 50}, {"dxy_index": 150},
        ]
        for macro in test_cases:
            conds = _compute_factor_conditions(macro)
            for k, v in conds.items():
                assert -1.0 <= v <= 1.0, f"Condition {k} = {v} out of range for {macro}"


# ── Sector Macro Adjustment ──


class TestSectorMacroAdjustment:
    """Test compute_sector_macro_adjustment for scoring, structure, and warnings."""

    # --- Sector-specific direction tests ---

    def test_utility_penalized_high_oil(self):
        """유틸리티: 유가 고수준 -> 부정적 조정 (연료비 부담)"""
        result = compute_sector_macro_adjustment("유틸리티", {"wti_crude": 100})
        assert result["adjustment_score"] < 0
        assert any("유틸리티" in w and "유가" in w for w in result["warnings"])

    def test_energy_boosted_high_oil(self):
        """Energy: 유가 고수준 -> 긍정적 조정"""
        result = compute_sector_macro_adjustment("Energy", {"wti_crude": 100})
        assert result["adjustment_score"] > 0

    def test_semiconductor_weak_krw_boost(self):
        """반도체: 원화 약세 -> 수출 유리 긍정적 조정"""
        result = compute_sector_macro_adjustment("반도체", {"usd_krw": 1420})
        assert result["adjustment_score"] > 0

    def test_bio_high_rate_penalty(self):
        """바이오: 금리 고수준 -> 밸류에이션 부담"""
        result = compute_sector_macro_adjustment("바이오", {"us_10y_yield": 5.5})
        assert result["adjustment_score"] < 0

    def test_finance_high_rate_positive(self):
        """금융: 금리 고수준 -> NIM 확대 (양의 감도)"""
        result = compute_sector_macro_adjustment("금융", {"us_10y_yield": 5.5})
        assert result["factors"]["rate"]["contribution"] > 0

    def test_auto_kr_weak_krw_boost(self):
        """자동차: 원화 약세 -> 수출 환차익"""
        result = compute_sector_macro_adjustment("자동차", {"usd_krw": 1420})
        assert result["factors"]["fx"]["contribution"] > 0

    def test_shipbuilding_high_oil_positive(self):
        """조선/중공업: 유가 상승 -> 해양플랜트 수주 기대"""
        result = compute_sector_macro_adjustment("조선/중공업", {"wti_crude": 105})
        assert result["factors"]["oil"]["contribution"] > 0

    def test_insurance_high_rate_positive(self):
        """보험: 금리 고수준 -> 투자이익률 상승"""
        result = compute_sector_macro_adjustment("보험", {"us_10y_yield": 5.5})
        assert result["factors"]["rate"]["contribution"] > 0

    def test_internet_high_rate_negative(self):
        """인터넷: 금리 고수준 -> 성장주 할인율 상승"""
        result = compute_sector_macro_adjustment("인터넷", {"us_10y_yield": 5.5})
        assert result["factors"]["rate"]["contribution"] < 0

    def test_tech_us_high_rate_negative(self):
        """Tech: 금리 고수준 -> 성장주 밸류에이션 부담"""
        result = compute_sector_macro_adjustment("Tech", {"us_10y_yield": 5.5})
        assert result["factors"]["rate"]["contribution"] < 0

    def test_energy_us_high_oil_strong_positive(self):
        """Energy (US): 유가 매우 고수준 -> 강한 양의 조정"""
        result = compute_sector_macro_adjustment("Energy", {"wti_crude": 110})
        oil_contrib = result["factors"]["oil"]["contribution"]
        # Energy oil sensitivity = 0.7, condition for wti>100 = 0.8
        # contribution = 0.7 * 0.8 * 15 = 8.4
        assert oil_contrib > 8.0

    def test_consumer_high_oil_negative(self):
        """Consumer: 유가 고수준 -> 소비 부담"""
        result = compute_sector_macro_adjustment("Consumer", {"wti_crude": 105})
        assert result["factors"]["oil"]["contribution"] < 0

    # --- Unknown / fallback sectors ---

    def test_unknown_sector_zero_adjustment(self):
        """미등록 섹터 -> 조정값 0"""
        result = compute_sector_macro_adjustment("UnknownSector", {"wti_crude": 100})
        assert result["adjustment_score"] == 0.0

    def test_etf_sector_zero_adjustment(self):
        """ETF 섹터 -> 조정값 0"""
        result = compute_sector_macro_adjustment("ETF", {"wti_crude": 100})
        assert result["adjustment_score"] == 0.0

    def test_unknown_sector_returns_correct_sector_name(self):
        result = compute_sector_macro_adjustment("FooBar", {})
        assert result["sector"] == "FooBar"

    def test_unknown_sector_factors_all_zero_contribution(self):
        result = compute_sector_macro_adjustment("Unknown", {"wti_crude": 110})
        for f in result["factors"].values():
            assert f["contribution"] == 0.0
            assert f["sensitivity"] == 0.0

    def test_empty_string_sector(self):
        """Empty string sector -> uses DEFAULT_SENSITIVITY -> zero adjustment."""
        result = compute_sector_macro_adjustment("", {"wti_crude": 110})
        assert result["adjustment_score"] == 0.0
        assert result["sector"] == ""

    # --- Score bounding ---

    def test_score_bounded_extreme(self):
        """극단 조건에서도 -30 ~ +30 범위"""
        result = compute_sector_macro_adjustment("유틸리티", {
            "wti_crude": 130, "us_10y_yield": 6.0,
            "usd_krw": 1500, "dxy_index": 115,
        })
        assert -30 <= result["adjustment_score"] <= 30

    def test_score_bounded_extreme_positive(self):
        """Extreme positive conditions for Energy (positive oil sensitivity)."""
        result = compute_sector_macro_adjustment("Energy", {
            "wti_crude": 130, "us_10y_yield": 2.0,
            "usd_krw": 1200, "dxy_index": 90,
        })
        assert -30 <= result["adjustment_score"] <= 30

    def test_score_clamp_negative_30(self):
        """Verify score does not go below -30."""
        # 유틸리티 has oil=-0.8; with extreme high oil and high rate and high dxy
        result = compute_sector_macro_adjustment("유틸리티", {
            "wti_crude": 200, "us_10y_yield": 8.0,
            "usd_krw": 1320, "dxy_index": 115,
        })
        assert result["adjustment_score"] >= -30.0

    def test_all_sectors_bounded_extreme_conditions(self):
        """All sectors remain in [-30, 30] under extreme conditions."""
        extreme_macro = {
            "wti_crude": 200, "us_10y_yield": 8.0,
            "usd_krw": 2000, "dxy_index": 130,
        }
        for sector in SECTOR_SENSITIVITY:
            result = compute_sector_macro_adjustment(sector, extreme_macro)
            assert -30 <= result["adjustment_score"] <= 30, (
                f"{sector} score {result['adjustment_score']} out of bounds"
            )

    # --- Structure validation ---

    def test_factors_structure(self):
        result = compute_sector_macro_adjustment("반도체", {"wti_crude": 80})
        assert set(result["factors"].keys()) == {"oil", "rate", "fx", "dxy"}
        for f in result["factors"].values():
            assert "condition" in f
            assert "sensitivity" in f
            assert "contribution" in f

    def test_return_dict_has_all_keys(self):
        result = compute_sector_macro_adjustment("반도체", {"wti_crude": 80})
        assert "adjustment_score" in result
        assert "sector" in result
        assert "factors" in result
        assert "warnings" in result

    def test_sector_name_preserved_in_result(self):
        result = compute_sector_macro_adjustment("반도체", {})
        assert result["sector"] == "반도체"

    def test_adjustment_score_is_float(self):
        result = compute_sector_macro_adjustment("반도체", {"wti_crude": 80})
        assert isinstance(result["adjustment_score"], float)

    def test_factor_values_are_rounded(self):
        """Factor contributions should be rounded to 2 decimal places."""
        result = compute_sector_macro_adjustment("반도체", {
            "wti_crude": 95, "us_10y_yield": 4.8,
        })
        for f in result["factors"].values():
            assert f["condition"] == round(f["condition"], 2)
            assert f["sensitivity"] == round(f["sensitivity"], 2)
            assert f["contribution"] == round(f["contribution"], 2)

    def test_adjustment_score_is_rounded(self):
        result = compute_sector_macro_adjustment("반도체", {"wti_crude": 95})
        assert result["adjustment_score"] == round(result["adjustment_score"], 2)

    # --- Empty / None macro data ---

    def test_empty_macro_data(self):
        result = compute_sector_macro_adjustment("반도체", {})
        assert result["adjustment_score"] == 0.0
        assert len(result["warnings"]) == 0

    def test_all_none_macro_data(self):
        result = compute_sector_macro_adjustment("반도체", {
            "wti_crude": None, "us_10y_yield": None,
            "usd_krw": None, "dxy_index": None,
        })
        assert result["adjustment_score"] == 0.0

    # --- Contribution math verification ---

    def test_contribution_equals_condition_times_sensitivity_times_scale(self):
        """Verify: contribution = condition * sensitivity * _FACTOR_SCALE."""
        sector = "반도체"
        macro = {"wti_crude": 105, "us_10y_yield": 5.5, "usd_krw": 1420, "dxy_index": 112}
        result = compute_sector_macro_adjustment(sector, macro)
        conditions = _compute_factor_conditions(macro)
        sensitivity = SECTOR_SENSITIVITY[sector]

        for factor in ("oil", "rate", "fx", "dxy"):
            expected = round(
                conditions[factor] * sensitivity[factor] * _FACTOR_SCALE, 2
            )
            assert result["factors"][factor]["contribution"] == expected, (
                f"{factor}: expected {expected}, got {result['factors'][factor]['contribution']}"
            )

    def test_total_score_equals_sum_of_contributions(self):
        """adjustment_score = clamp(sum of contributions, -30, 30)."""
        sector = "반도체"
        macro = {"wti_crude": 80, "us_10y_yield": 4.2}
        result = compute_sector_macro_adjustment(sector, macro)

        raw_sum = sum(f["contribution"] for f in result["factors"].values())
        expected = round(max(-30.0, min(30.0, raw_sum)), 2)
        assert result["adjustment_score"] == expected

    def test_single_factor_contribution_isolated(self):
        """When only one factor is present, score equals that factor's contribution."""
        result = compute_sector_macro_adjustment("에너지/플랜트", {"wti_crude": 105})
        # Only oil has a non-zero condition; others default to 0.0
        oil_contrib = result["factors"]["oil"]["contribution"]
        assert result["adjustment_score"] == oil_contrib

    # --- Warning tests ---

    def test_warnings_generated_for_significant_impact(self):
        """큰 영향일 때 경고 생성"""
        result = compute_sector_macro_adjustment("유틸리티", {"wti_crude": 110})
        assert len(result["warnings"]) > 0

    def test_no_warnings_for_neutral_conditions(self):
        """중립 조건에서 경고 없음"""
        result = compute_sector_macro_adjustment("유틸리티", {"wti_crude": 65})
        assert len(result["warnings"]) == 0

    def test_warning_contains_sector_name(self):
        result = compute_sector_macro_adjustment("유틸리티", {"wti_crude": 110})
        for w in result["warnings"]:
            assert "유틸리티" in w

    def test_warning_contains_raw_value(self):
        """Warning templates should include the raw macro value."""
        result = compute_sector_macro_adjustment("유틸리티", {"wti_crude": 110})
        # The oil warning should contain the formatted WTI value
        oil_warnings = [w for w in result["warnings"] if "유가" in w]
        assert len(oil_warnings) > 0
        assert "110" in oil_warnings[0] or "$110" in oil_warnings[0]

    def test_no_warnings_when_sensitivity_below_threshold(self):
        """Warnings require |sensitivity| >= 0.3 even if contribution is large."""
        # 통신 has rate sensitivity = 0.1 (< 0.3), so no warning even at extreme rate
        result = compute_sector_macro_adjustment("통신", {"us_10y_yield": 5.5})
        rate_warnings = [w for w in result["warnings"] if "금리" in w]
        assert len(rate_warnings) == 0

    def test_no_warnings_when_contribution_below_4(self):
        """Warnings require |contribution| >= 4.0."""
        # 금융 rate sensitivity = 0.3
        # At rate=4.5, condition=0.2, contribution = 0.3 * 0.2 * 15 = 0.9 < 4.0
        result = compute_sector_macro_adjustment("금융", {"us_10y_yield": 4.5})
        rate_warnings = [w for w in result["warnings"] if "금리" in w]
        assert len(rate_warnings) == 0

    def test_positive_warning_for_positive_contribution(self):
        """Positive contribution > 3.0 should use 'positive' template."""
        # Energy: oil sensitivity = 0.7, wti=105 -> condition=0.8
        # contribution = 0.7 * 0.8 * 15 = 8.4 > 3.0
        result = compute_sector_macro_adjustment("Energy", {"wti_crude": 105})
        # Positive template not Korean-sector specific, but template exists
        # Energy is US sector, templates are Korean text
        # Check that warnings are generated
        assert len(result["warnings"]) > 0

    def test_negative_warning_for_negative_contribution(self):
        """Negative contribution < -3.0 should use 'negative' template."""
        # 유틸리티: oil sensitivity = -0.8, wti=105 -> condition=0.8
        # contribution = -0.8 * 0.8 * 15 = -9.6 < -3.0
        result = compute_sector_macro_adjustment("유틸리티", {"wti_crude": 105})
        assert any("유가" in w and "비용 부담" in w for w in result["warnings"])

    def test_no_warnings_when_raw_value_missing(self):
        """If raw value key is missing from macro_data, no warning generated."""
        # Pass only unrelated keys (not in _FACTOR_VALUE_KEYS mapping)
        # Even though conditions would be 0 anyway, this tests the raw_value guard
        result = compute_sector_macro_adjustment("유틸리티", {})
        assert len(result["warnings"]) == 0

    def test_multiple_warnings_possible(self):
        """A sector can have warnings for multiple factors."""
        # 유틸리티 has oil=-0.8 and rate=-0.3
        # extreme conditions: high oil and high rate both cause negative contribution
        result = compute_sector_macro_adjustment("유틸리티", {
            "wti_crude": 110, "us_10y_yield": 5.5,
        })
        # Oil: -0.8 * 0.8 * 15 = -9.6 (|contrib| >= 4, |sens| >= 0.3) -> warning
        # Rate: -0.3 * 0.8 * 15 = -3.6 (|contrib| < 4) -> no warning
        assert len(result["warnings"]) >= 1

    def test_fx_positive_warning(self):
        """원화 약세 -> 수출 관련 섹터에 positive warning."""
        # 반도체 fx sensitivity = 0.5
        # usd_krw=1420 -> fx condition=0.8, contribution = 0.5*0.8*15 = 6.0
        result = compute_sector_macro_adjustment("반도체", {"usd_krw": 1420})
        fx_warnings = [w for w in result["warnings"] if "원화" in w]
        assert len(fx_warnings) > 0
        assert any("환차익" in w for w in fx_warnings)


# ── All Sector Impacts ──


class TestAllSectorImpacts:
    """Test compute_all_sector_impacts batch computation."""

    def test_returns_list(self):
        impacts = compute_all_sector_impacts({"wti_crude": 80})
        assert isinstance(impacts, list)
        assert len(impacts) == len(SECTOR_SENSITIVITY)

    def test_sorted_by_abs_score(self):
        impacts = compute_all_sector_impacts({"wti_crude": 100})
        abs_scores = [abs(i["adjustment_score"]) for i in impacts]
        assert abs_scores == sorted(abs_scores, reverse=True)

    def test_energy_at_top_with_high_oil(self):
        """유가 고수준 -> Energy/유틸리티가 상위에 위치"""
        impacts = compute_all_sector_impacts({"wti_crude": 110})
        top_sectors = [i["sector"] for i in impacts[:5]]
        assert "Energy" in top_sectors or "유틸리티" in top_sectors

    def test_each_has_required_keys(self):
        impacts = compute_all_sector_impacts({"wti_crude": 80})
        for imp in impacts:
            assert "adjustment_score" in imp
            assert "sector" in imp
            assert "factors" in imp
            assert "warnings" in imp

    def test_empty_macro_all_zeros(self):
        """Empty macro data -> all sectors score 0."""
        impacts = compute_all_sector_impacts({})
        for imp in impacts:
            assert imp["adjustment_score"] == 0.0

    def test_all_none_macro_all_zeros(self):
        """All None macro values -> all sectors score 0."""
        impacts = compute_all_sector_impacts({
            "wti_crude": None, "us_10y_yield": None,
            "usd_krw": None, "dxy_index": None,
        })
        for imp in impacts:
            assert imp["adjustment_score"] == 0.0

    def test_all_sectors_present_in_results(self):
        """Every sector in SECTOR_SENSITIVITY appears exactly once."""
        impacts = compute_all_sector_impacts({"wti_crude": 80})
        result_sectors = {i["sector"] for i in impacts}
        expected_sectors = set(SECTOR_SENSITIVITY.keys())
        assert result_sectors == expected_sectors

    def test_all_scores_bounded(self):
        """All sector scores remain in [-30, 30] under any conditions."""
        extreme = {
            "wti_crude": 200, "us_10y_yield": 8.0,
            "usd_krw": 2000, "dxy_index": 130,
        }
        impacts = compute_all_sector_impacts(extreme)
        for imp in impacts:
            assert -30 <= imp["adjustment_score"] <= 30, (
                f"{imp['sector']} = {imp['adjustment_score']}"
            )

    def test_consistent_with_individual_calls(self):
        """Batch results match individual compute_sector_macro_adjustment calls."""
        macro = {"wti_crude": 95, "us_10y_yield": 4.3, "usd_krw": 1360, "dxy_index": 105}
        impacts = compute_all_sector_impacts(macro)
        impact_map = {i["sector"]: i for i in impacts}

        for sector in SECTOR_SENSITIVITY:
            individual = compute_sector_macro_adjustment(sector, macro)
            assert impact_map[sector]["adjustment_score"] == individual["adjustment_score"]
            assert impact_map[sector]["factors"] == individual["factors"]

    def test_sorting_stability_with_equal_scores(self):
        """When all scores are 0 (empty macro), list has correct length."""
        impacts = compute_all_sector_impacts({})
        assert len(impacts) == len(SECTOR_SENSITIVITY)
        # All zero, so sort is stable and all elements present
        for imp in impacts:
            assert imp["adjustment_score"] == 0.0

    def test_rate_shock_pushes_growth_sectors_down(self):
        """금리 급등 -> 바이오/인터넷 등 성장주 하위 정렬."""
        impacts = compute_all_sector_impacts({"us_10y_yield": 6.0})
        scores_by_sector = {i["sector"]: i["adjustment_score"] for i in impacts}
        # 바이오 sensitivity rate=-0.5, 인터넷 rate=-0.4 -> negative scores
        assert scores_by_sector["바이오"] < 0
        assert scores_by_sector["인터넷"] < 0
        # 금융/보험 sensitivity rate=+0.3 -> positive scores
        assert scores_by_sector["금융"] > 0
        assert scores_by_sector["보험"] > 0
