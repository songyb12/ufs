"""Tests for carry trade and global risk indicators."""

import pytest
from app.indicators.carry_trade import (
    compute_carry_trade_risk,
    compute_forex_map_data,
    compute_global_risk_factors,
    _compute_carry_score,
    _compute_unwind_risk,
    _compute_currency_strength,
    _compute_capital_flows,
    _analyze_dxy_impact,
    CARRY_PAIRS,
    CURRENCY_INFO,
)


class TestComputeCarryScore:
    def test_none_rate_diff(self):
        assert _compute_carry_score(None, 0) == 50

    def test_high_rate_diff(self):
        score = _compute_carry_score(5.0, 0)
        assert score > 70  # High diff + stable FX

    def test_negative_rate_diff(self):
        score = _compute_carry_score(-1.0, 0)
        assert score <= 50  # -20 for negative rate, +20 for stable FX = 50

    def test_volatile_fx(self):
        score = _compute_carry_score(3.0, 8.0)
        assert score < _compute_carry_score(3.0, 0.5)

    def test_none_fx_change(self):
        score = _compute_carry_score(3.0, None)
        assert 0 <= score <= 100

    def test_score_bounds(self):
        for diff in [-5, -2, 0, 2, 5, 10]:
            for fx in [-10, -5, 0, 5, 10]:
                score = _compute_carry_score(diff, fx)
                assert 0 <= score <= 100


class TestComputeUnwindRisk:
    def test_calm_markets(self):
        result = _compute_unwind_risk(0, 0, 0, 15, "JPY")
        assert result["risk_level"] == "LOW"
        assert result["risk_score"] < 15

    def test_jpy_surge(self):
        result = _compute_unwind_risk(-1.5, -3, -6, 32, "JPY")
        assert result["risk_level"] in ("HIGH", "ELEVATED")
        assert result["risk_score"] > 50

    def test_vix_spike(self):
        result = _compute_unwind_risk(0, 0, 0, 35, "CHF")
        assert result["risk_score"] >= 25
        assert any("VIX" in s for s in result["signals"])

    def test_generic_funding_surge(self):
        result = _compute_unwind_risk(-1.5, -2.5, 0, 18, "CHF")
        assert result["risk_score"] > 30

    def test_trend_output(self):
        result = _compute_unwind_risk(-0.5, -1.5, 0, 18, "JPY")
        assert "trend" in result
        assert "trend_kr" in result
        assert result["trend"] in ("WORSENING", "IMPROVING", "STABLE")

    def test_none_vix(self):
        result = _compute_unwind_risk(0, 0, 0, None, "JPY")
        assert result["risk_level"] == "LOW"


class TestComputeCarryTradeRisk:
    def test_basic(self):
        rates = {"JPY": 0.1, "USD": 5.25, "KRW": 3.5, "CHF": 1.5, "EUR": 4.0, "CNY": 3.45, "AUD": 4.35}
        fx = {"USD/JPY": {"current": 150, "change_1d": 0, "change_1w": 0, "change_1m": 0}}
        result = compute_carry_trade_risk(rates, fx, vix=18, dxy=103)
        assert "pairs" in result
        assert "overall_risk" in result
        assert len(result["pairs"]) == len(CARRY_PAIRS)

    def test_empty_rates(self):
        result = compute_carry_trade_risk({}, {}, vix=None, dxy=None)
        assert len(result["pairs"]) == len(CARRY_PAIRS)
        for p in result["pairs"]:
            assert p["rate_differential"] is None

    def test_high_risk_scenario(self):
        rates = {"JPY": 0.5, "USD": 5.0, "KRW": 3.0, "CHF": 1.0, "EUR": 3.5, "CNY": 3.0, "AUD": 4.0}
        fx = {
            "USD/JPY": {"current": 140, "change_1d": -2.0, "change_1w": -4.0, "change_1m": -8.0},
        }
        result = compute_carry_trade_risk(rates, fx, vix=35, dxy=110)
        overall = result["overall_risk"]
        assert overall["score"] > 40  # Should be elevated+
        assert len(overall["advice"]) > 0

    def test_overall_has_scenario(self):
        result = compute_carry_trade_risk({"JPY": 0.1, "USD": 5.0}, {}, vix=18, dxy=103)
        assert "scenario_kr" in result["overall_risk"]


class TestCurrencyStrength:
    def test_usd_base(self):
        result = _compute_currency_strength("USD", {})
        assert result["label"] == "기준통화"

    def test_strong_currency(self):
        result = _compute_currency_strength("JPY", {"change_1d": -2, "change_1w": -3, "change_1m": -5})
        assert result["score"] > 0  # Negative changes → strong

    def test_weak_currency(self):
        result = _compute_currency_strength("BRL", {"change_1d": 3, "change_1w": 4, "change_1m": 6})
        assert result["score"] < 0

    def test_no_data(self):
        result = _compute_currency_strength("KRW", {})
        assert result["score"] == 0


class TestCapitalFlows:
    def test_basic_flows(self):
        countries = [
            {"currency": "JPY", "country": "일본", "lat": 35, "lon": 139, "flag": "🇯🇵", "interest_rate": 0.1},
            {"currency": "USD", "country": "미국", "lat": 38, "lon": -77, "flag": "🇺🇸", "interest_rate": 5.25},
            {"currency": "EUR", "country": "유럽연합", "lat": 50, "lon": 4, "flag": "🇪🇺", "interest_rate": 4.0},
        ]
        flows = _compute_capital_flows(countries)
        assert len(flows) > 0
        assert all("rate_diff" in f for f in flows)
        assert all(f["rate_diff"] > 1.0 for f in flows)

    def test_no_rates(self):
        countries = [
            {"currency": "JPY", "country": "일본", "lat": 35, "lon": 139, "flag": "🇯🇵", "interest_rate": None},
        ]
        flows = _compute_capital_flows(countries)
        assert flows == []

    def test_small_diff_filtered(self):
        countries = [
            {"currency": "EUR", "country": "EU", "lat": 50, "lon": 4, "flag": "🇪🇺", "interest_rate": 4.0},
            {"currency": "GBP", "country": "UK", "lat": 51, "lon": 0, "flag": "🇬🇧", "interest_rate": 4.5},
        ]
        flows = _compute_capital_flows(countries)
        assert len(flows) == 0  # 0.5% diff < 1.0 threshold


class TestDxyImpact:
    def test_strong_dollar(self):
        result = _analyze_dxy_impact(110)
        assert result["level"] == "Very Strong"
        assert result["color"] == "#ef4444"

    def test_weak_dollar(self):
        result = _analyze_dxy_impact(95)
        assert result["level"] == "Very Weak"
        assert result["color"] == "#16a34a"

    def test_neutral_dollar(self):
        result = _analyze_dxy_impact(102)
        assert result["level"] == "Neutral"

    def test_none_default(self):
        result = _analyze_dxy_impact(None)
        assert result["value"] == 103


class TestForexMapData:
    def test_basic(self):
        fx = {"USD/JPY": {"current": 150, "change_1d": 0.5, "change_1w": 1.0, "change_1m": 2.0}}
        rates = {"USD": 5.25, "JPY": 0.1}
        result = compute_forex_map_data(fx, rates, dxy=103, vix=18)
        assert "countries" in result
        assert "flows" in result
        assert "dxy_analysis" in result
        assert len(result["countries"]) == len(CURRENCY_INFO)

    def test_empty(self):
        result = compute_forex_map_data({}, {}, dxy=None, vix=None)
        assert len(result["countries"]) == len(CURRENCY_INFO)


class TestGlobalRiskFactors:
    def test_stable_market(self):
        macro = {"vix": 15, "dxy_index": 100, "us_yield_spread": 0.5, "wti_crude": 70}
        factors = compute_global_risk_factors(macro, {}, {"USD": 5.25, "KRW": 3.5})
        # Low VIX, normal DXY, positive spread, moderate oil → no factors
        assert isinstance(factors, list)

    def test_high_risk_market(self):
        macro = {"vix": 35, "dxy_index": 110, "us_yield_spread": -0.8, "wti_crude": 105, "usd_krw": 1450, "gold": 2900, "copper": 2.8}
        carry_risk = {"overall_risk": {"score": 70, "level": "HIGH", "level_kr": "위험"}}
        factors = compute_global_risk_factors(macro, {}, {"USD": 5.25, "KRW": 3.5}, carry_risk)
        assert len(factors) >= 5
        assert factors[0]["score"] >= factors[-1]["score"]  # Sorted by score

    def test_rate_differential(self):
        macro = {}
        factors = compute_global_risk_factors(macro, {}, {"USD": 5.25, "KRW": 3.0})
        rate_diff = [f for f in factors if f["factor"] == "rate_differential"]
        assert len(rate_diff) == 1
        assert rate_diff[0]["severity"] in ("ELEVATED", "WATCH")

    def test_none_macro(self):
        factors = compute_global_risk_factors(None, None, None)
        assert isinstance(factors, list)
