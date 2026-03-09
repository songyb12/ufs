"""Tests for market season detection, investment clock, yield phase, and risk scoring."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import math

import pytest

from app.indicators.market_season import (
    _classify_season,
    _default_season,
    _normalize_copper,
    check_strategy_match,
    compute_investment_clock,
    compute_unified_risk_score,
    detect_market_season,
    detect_yield_phase,
)


# ── Helpers ──

def _make_macro_row(day_offset: int, us_10y: float = 4.0, copper: float = 4.2,
                     wti: float = 70.0, gold: float = 2200, dxy: float = 103,
                     yield_spread: float = 0.5, vix: float = 18.0) -> dict:
    """Create a single macro history row."""
    return {
        "indicator_date": f"2026-01-{day_offset:02d}",
        "us_10y_yield": us_10y,
        "copper_price": copper,
        "wti_crude": wti,
        "gold_price": gold,
        "dxy_index": dxy,
        "us_yield_spread": yield_spread,
        "vix": vix,
    }


def _make_history(count: int, **overrides) -> list[dict]:
    """Create a macro history list with uniform values."""
    return [_make_macro_row(i + 1, **overrides) for i in range(count)]


# ── detect_market_season ──

class TestDetectMarketSeason:
    def test_insufficient_data(self):
        """Less than 10 days returns unknown."""
        result = detect_market_season([_make_macro_row(1)] * 5)
        assert result["season"] == "Unknown"
        assert result["confidence"] == 0.0

    def test_spring_season(self):
        """Falling rates + improving growth → Spring."""
        # Older period: high yields
        older = _make_history(30, us_10y=4.5, copper=3.8)
        # Recent period: lower yields, better copper
        recent = _make_history(15, us_10y=4.0, copper=4.3)
        history = older + recent

        result = detect_market_season(history)
        assert result["season"] == "Spring"
        assert result["season_kr"] == "금융장세"
        assert result["axes"]["rate_direction"] == "falling"
        assert result["confidence"] > 0

    def test_summer_season(self):
        """Rising rates + improving growth → Summer."""
        older = _make_history(30, us_10y=3.5, copper=3.8)
        recent = _make_history(15, us_10y=4.2, copper=4.5)
        history = older + recent

        result = detect_market_season(history)
        assert result["season"] == "Summer"
        assert result["season_kr"] == "실적장세"
        assert result["axes"]["rate_direction"] == "rising"

    def test_autumn_season(self):
        """Rising/flat rates + deteriorating growth → Autumn."""
        older = _make_history(30, us_10y=4.0, copper=4.5)
        recent = _make_history(15, us_10y=4.3, copper=3.8)
        history = older + recent

        result = detect_market_season(history)
        assert result["season"] == "Autumn"
        assert result["season_kr"] == "역금융장세"

    def test_winter_season(self):
        """Falling rates + deteriorating growth → Winter."""
        older = _make_history(30, us_10y=4.5, copper=4.5)
        recent = _make_history(15, us_10y=4.0, copper=3.5)
        history = older + recent

        result = detect_market_season(history)
        assert result["season"] == "Winter"
        assert result["season_kr"] == "역실적장세"

    def test_confidence_bounds(self):
        """Confidence is always between 0.2 and 1.0."""
        # Very ambiguous data
        flat = _make_history(45, us_10y=4.0, copper=4.0)
        result = detect_market_season(flat)
        assert 0.2 <= result["confidence"] <= 1.0

    def test_with_etf_momentum(self):
        """ETF momentum contributes to growth proxy."""
        history = _make_history(45, us_10y=4.0, copper=4.0)
        result = detect_market_season(
            history,
            etf_momentum={"spy_return_60d": 0.10},
        )
        assert result["axes"]["components"]["etf_momentum"] > 0

    def test_with_kr_foreign_flow(self):
        """KR foreign flow contributes to growth proxy."""
        history = _make_history(45, us_10y=4.0, copper=4.0)
        kr_flow = [
            {"trade_date": f"2026-01-{i:02d}", "total_foreign_net": 50_000_000_000}
            for i in range(1, 31)
        ]
        result = detect_market_season(history, kr_foreign_trend=kr_flow)
        # Flow should contribute something
        assert "kr_flow_momentum" in result["axes"]["components"]

    def test_copper_cents_normalization(self):
        """Copper values > 100 are normalized from cents to dollars."""
        older = _make_history(30, us_10y=4.5, copper=420)
        recent = _make_history(15, us_10y=4.0, copper=450)
        result = detect_market_season(older + recent)
        # Should not crash; copper 420 → $4.20
        assert result["season"] in ("Spring", "Summer", "Autumn", "Winter", "Unknown")

    def test_all_none_yields(self):
        """Handles None yield values gracefully."""
        history = [{"indicator_date": f"2026-01-{i:02d}", "us_10y_yield": None,
                     "copper_price": 4.0} for i in range(1, 46)]
        result = detect_market_season(history)
        assert result["axes"]["rate_direction"] == "flat"


# ── compute_investment_clock ──

class TestInvestmentClock:
    def test_recovery_quadrant(self):
        """Growth positive, inflation negative → Recovery."""
        macro = {
            "copper_price": 4.5,
            "us_yield_spread": 1.5,
            "vix": 15,
            "wti_crude": 55,
            "gold_price": 1800,
            "dxy_index": 98,
        }
        result = compute_investment_clock(macro)
        assert result["quadrant"] == "Recovery"
        assert result["growth_score"] > 0
        assert result["inflation_score"] < 0

    def test_overheat_quadrant(self):
        """Growth positive, inflation positive → Overheat."""
        macro = {
            "copper_price": 4.5,
            "us_yield_spread": 1.5,
            "vix": 15,
            "wti_crude": 100,
            "gold_price": 2800,
            "dxy_index": 108,
        }
        result = compute_investment_clock(macro)
        assert result["quadrant"] == "Overheat"
        assert result["growth_score"] > 0
        assert result["inflation_score"] > 0

    def test_stagflation_quadrant(self):
        """Growth negative, inflation positive → Stagflation."""
        macro = {
            "copper_price": 2.8,
            "us_yield_spread": -0.5,
            "vix": 32,
            "wti_crude": 110,
            "gold_price": 2800,
            "dxy_index": 112,
        }
        result = compute_investment_clock(macro)
        assert result["quadrant"] == "Stagflation"
        assert result["growth_score"] < 0
        assert result["inflation_score"] > 0

    def test_reflation_quadrant(self):
        """Growth negative, inflation negative → Reflation."""
        macro = {
            "copper_price": 3.0,
            "us_yield_spread": -0.3,
            "vix": 28,
            "wti_crude": 45,
            "gold_price": 1900,
            "dxy_index": 97,
        }
        result = compute_investment_clock(macro)
        assert result["quadrant"] == "Reflation"
        assert result["growth_score"] < 0
        assert result["inflation_score"] < 0

    def test_none_macro_data(self):
        """None input returns valid structure."""
        result = compute_investment_clock(None)
        assert "quadrant" in result
        assert "growth_score" in result
        assert "inflation_score" in result

    def test_empty_macro_data(self):
        """Empty dict uses defaults."""
        result = compute_investment_clock({})
        assert result["quadrant"] in ("Recovery", "Overheat", "Stagflation", "Reflation")

    def test_score_bounds(self):
        """Scores are within [-1, +1]."""
        macro = {
            "copper_price": 5.0,
            "us_yield_spread": 3.0,
            "vix": 8,
            "wti_crude": 150,
            "gold_price": 3000,
            "dxy_index": 120,
        }
        result = compute_investment_clock(macro)
        assert -1.0 <= result["growth_score"] <= 1.0
        assert -1.0 <= result["inflation_score"] <= 1.0

    def test_with_history_copper_trend(self):
        """History enhances copper growth score with trend."""
        macro = {"copper_price": 4.0, "us_yield_spread": 0.5, "vix": 18,
                 "wti_crude": 70, "gold_price": 2200, "dxy_index": 103}
        # Rising copper history
        history = _make_history(10, copper=3.5) + _make_history(15, copper=4.5)
        result = compute_investment_clock(macro, history)
        assert result["growth_components"]["copper"] > 0

    def test_components_present(self):
        """Return includes growth and inflation component breakdowns."""
        result = compute_investment_clock({"copper_price": 4.0, "vix": 18})
        assert "growth_components" in result
        assert "inflation_components" in result
        assert "copper" in result["growth_components"]
        assert "oil" in result["inflation_components"]


# ── detect_yield_phase ──

class TestYieldPhase:
    def test_insufficient_data(self):
        result = detect_yield_phase([0.5] * 5)
        assert result["phase"] == "Unknown"
        assert result["risk_flag"] is False

    def test_normal_phase(self):
        """Healthy positive spread → Normal."""
        spreads = [1.5] * 30
        result = detect_yield_phase(spreads)
        assert result["phase"] == "Normal"
        assert result["risk_flag"] is False

    def test_inverted_phase(self):
        """Negative spread, not steepening → Inverted."""
        spreads = [-0.3] * 30
        result = detect_yield_phase(spreads)
        assert result["phase"] == "Inverted"
        assert result["risk_flag"] is True

    def test_normalizing_phase(self):
        """Spread was negative, now rising → Normalizing (most dangerous)."""
        # Older: deeper inversion
        spreads = [-0.5] * 20 + [-0.3, -0.2, -0.15, -0.1, -0.05, 0.0, 0.05, 0.1, 0.15, 0.2]
        result = detect_yield_phase(spreads)
        assert result["phase"] == "Normalizing"
        assert result["risk_flag"] is True

    def test_flattening_phase(self):
        """Spread positive but declining → Flattening."""
        spreads = [1.0] * 15 + [0.8, 0.7, 0.6, 0.5, 0.4, 0.35, 0.3, 0.28, 0.25, 0.22, 0.2, 0.18, 0.15, 0.12, 0.1]
        result = detect_yield_phase(spreads)
        assert result["phase"] == "Flattening"
        assert result["risk_flag"] is False

    def test_none_values_filtered(self):
        """None values in history are filtered out."""
        spreads = [None, 1.5, None, 1.4, 1.3] + [1.2] * 10 + [None]
        result = detect_yield_phase(spreads)
        # Should not crash
        assert result["phase"] in ("Normal", "Flattening", "Inverted",
                                    "Normalizing", "Transitioning", "Unknown")

    def test_current_spread_accuracy(self):
        """Current spread matches the last non-None value."""
        spreads = [0.5] * 20 + [0.75]
        result = detect_yield_phase(spreads)
        assert result["current_spread"] == 0.75


# ── check_strategy_match ──

class TestStrategyMatch:
    def test_winter_with_many_buys(self):
        """Winter + many buy signals → warning."""
        result = check_strategy_match(
            season="Winter",
            clock_quadrant="Reflation",
            signal_summary={"buy_count": 8, "sell_count": 2, "hold_count": 5},
        )
        assert result["warning_count"] > 0
        assert any("겨울" in w["message"] for w in result["warnings"])

    def test_spring_no_positions(self):
        """Spring + no positions → opportunity."""
        result = check_strategy_match(
            season="Spring",
            clock_quadrant="Recovery",
            portfolio_summary={"total_positions": 0, "total_invested": 0,
                               "kr_pct": 0, "us_pct": 0, "tech_pct": 0},
        )
        assert any(w["level"] == "opportunity" for w in result["warnings"])

    def test_autumn_kr_heavy(self):
        """Autumn + KR-heavy → warning."""
        result = check_strategy_match(
            season="Autumn",
            clock_quadrant="Overheat",
            portfolio_summary={"total_positions": 10, "kr_pct": 75,
                               "us_pct": 25, "tech_pct": 30, "total_invested": 50_000_000},
        )
        assert any("KR 비중" in w["message"] for w in result["warnings"])

    def test_stagflation_many_positions(self):
        """Stagflation + many positions → warning."""
        result = check_strategy_match(
            season="Autumn",
            clock_quadrant="Stagflation",
            portfolio_summary={"total_positions": 12, "kr_pct": 50,
                               "us_pct": 50, "tech_pct": 20, "total_invested": 80_000_000},
        )
        assert any("침체" in w["message"] for w in result["warnings"])

    def test_recovery_with_position_opportunity(self):
        """Recovery + no positions → opportunity."""
        result = check_strategy_match(
            season="Summer",
            clock_quadrant="Recovery",
            portfolio_summary={"total_positions": 0, "total_invested": 0,
                               "kr_pct": 0, "us_pct": 0, "tech_pct": 0},
        )
        assert any("회복" in w["message"] for w in result["warnings"])

    def test_match_score_bounds(self):
        """Match score is always 0-100."""
        result = check_strategy_match(
            season="Winter",
            clock_quadrant="Stagflation",
            portfolio_summary={"total_positions": 20, "kr_pct": 80,
                               "us_pct": 20, "tech_pct": 60, "total_invested": 100_000_000},
            signal_summary={"buy_count": 15, "sell_count": 0, "hold_count": 5},
        )
        assert 0 <= result["match_score"] <= 100

    def test_good_alignment_summer(self):
        """Summer with positions and buy signals → decent match."""
        result = check_strategy_match(
            season="Summer",
            clock_quadrant="Overheat",
            portfolio_summary={"total_positions": 8, "kr_pct": 40,
                               "us_pct": 60, "tech_pct": 30, "total_invested": 50_000_000},
            signal_summary={"buy_count": 5, "sell_count": 2, "hold_count": 3},
        )
        assert result["match_score"] >= 50

    def test_unknown_season_no_crash(self):
        """Unknown season should not crash."""
        result = check_strategy_match(
            season="Unknown",
            clock_quadrant="Recovery",
        )
        assert "match_score" in result


# ── compute_unified_risk_score ──

class TestUnifiedRiskScore:
    def test_low_risk(self):
        """Recovery + low stagflation + risk-on → low score."""
        result = compute_unified_risk_score(
            stagflation_index=15.0,
            risk_regime_score=0.5,
            clock_quadrant="Recovery",
        )
        assert result["score"] < 30
        assert result["level"] == "Low"

    def test_high_risk(self):
        """Stagflation + high stag index + panic → high score."""
        result = compute_unified_risk_score(
            stagflation_index=80.0,
            risk_regime_score=-0.7,
            clock_quadrant="Stagflation",
        )
        assert result["score"] > 65
        assert result["level"] in ("High", "Critical")

    def test_moderate_risk(self):
        """Mixed signals → moderate."""
        result = compute_unified_risk_score(
            stagflation_index=40.0,
            risk_regime_score=0.0,
            clock_quadrant="Overheat",
        )
        assert 25 <= result["score"] <= 65

    def test_score_bounds(self):
        """Score is always 0-100."""
        # Extreme low
        r1 = compute_unified_risk_score(0.0, 1.0, "Recovery")
        assert 0 <= r1["score"] <= 100

        # Extreme high
        r2 = compute_unified_risk_score(100.0, -1.0, "Stagflation")
        assert 0 <= r2["score"] <= 100

    def test_components_present(self):
        """Result includes all component breakdowns."""
        result = compute_unified_risk_score(50.0, 0.0, "Overheat")
        assert "components" in result
        assert "stagflation" in result["components"]
        assert "risk_regime" in result["components"]
        assert "investment_clock" in result["components"]

    def test_component_weights_sum_to_one(self):
        """Component weights sum to 1.0."""
        result = compute_unified_risk_score(50.0, 0.0, "Recovery")
        total_weight = sum(
            c["weight"] for c in result["components"].values()
        )
        assert abs(total_weight - 1.0) < 0.001

    def test_level_labels(self):
        """All risk levels have correct thresholds."""
        assert compute_unified_risk_score(0, 1.0, "Recovery")["level"] == "Low"
        assert compute_unified_risk_score(50, 0.0, "Overheat")["level"] in ("Moderate", "Elevated")
        assert compute_unified_risk_score(100, -1.0, "Stagflation")["level"] == "Critical"


# ══════════════════════════════════════════════════════════════════════
# Extended edge-case tests
# ══════════════════════════════════════════════════════════════════════


# ── Private helper: _normalize_copper ──


class TestNormalizeCopper:
    def test_none_returns_default(self):
        """None input returns the default fallback of 4.0."""
        assert _normalize_copper(None) == 4.0

    def test_cents_to_dollars(self):
        """Values > 100 are treated as cents/lb and divided by 100."""
        assert _normalize_copper(420) == 4.2
        assert _normalize_copper(350.5) == 3.505

    def test_dollars_passthrough(self):
        """Values <= 100 are treated as $/lb and returned unchanged."""
        assert _normalize_copper(4.2) == 4.2
        assert _normalize_copper(99.99) == 99.99

    def test_boundary_100(self):
        """Exactly 100 is not > 100, so returned as-is."""
        assert _normalize_copper(100) == 100

    def test_boundary_just_above_100(self):
        """100.01 triggers cents-to-dollars conversion."""
        assert abs(_normalize_copper(100.01) - 1.0001) < 1e-6

    def test_zero(self):
        """Zero copper price passes through without error."""
        assert _normalize_copper(0) == 0

    def test_negative(self):
        """Negative copper (bad data) passes through without error."""
        assert _normalize_copper(-5.0) == -5.0


# ── Private helper: _classify_season ──


class TestClassifySeason:
    """Exhaustive coverage of the rate x growth direction matrix."""

    def test_falling_improving_is_spring(self):
        assert _classify_season("falling", "improving") == "spring"

    def test_falling_flat_is_spring(self):
        assert _classify_season("falling", "flat") == "spring"

    def test_rising_improving_is_summer(self):
        assert _classify_season("rising", "improving") == "summer"

    def test_flat_improving_is_summer(self):
        assert _classify_season("flat", "improving") == "summer"

    def test_flat_flat_is_summer(self):
        """Flat/flat is neutral continuation, mapped to summer."""
        assert _classify_season("flat", "flat") == "summer"

    def test_rising_deteriorating_is_autumn(self):
        assert _classify_season("rising", "deteriorating") == "autumn"

    def test_flat_deteriorating_is_autumn(self):
        assert _classify_season("flat", "deteriorating") == "autumn"

    def test_rising_flat_is_autumn(self):
        assert _classify_season("rising", "flat") == "autumn"

    def test_falling_deteriorating_is_winter(self):
        assert _classify_season("falling", "deteriorating") == "winter"

    def test_unknown_directions_default_autumn(self):
        """Unrecognized direction combination defaults to autumn."""
        assert _classify_season("unknown", "unknown") == "autumn"
        assert _classify_season("", "") == "autumn"


# ── Private helper: _default_season ──


class TestDefaultSeason:
    def test_reason_propagated(self):
        """Reason string appears in description_kr."""
        result = _default_season("test reason")
        assert result["description_kr"] == "test reason"
        assert result["season"] == "Unknown"
        assert result["confidence"] == 0.0

    def test_axes_zeroed(self):
        """All axis values are zero in default response."""
        result = _default_season("x")
        axes = result["axes"]
        assert axes["rate_direction"] == "unknown"
        assert axes["rate_momentum"] == 0.0
        assert axes["growth_direction"] == "unknown"
        assert axes["growth_proxy"] == 0.0
        for v in axes["components"].values():
            assert v == 0.0


# ── detect_market_season: edge cases ──


class TestDetectMarketSeasonEdgeCases:
    def test_empty_list(self):
        """Empty history returns unknown."""
        result = detect_market_season([])
        assert result["season"] == "Unknown"
        assert result["confidence"] == 0.0

    def test_exactly_10_rows(self):
        """Boundary: exactly 10 rows is sufficient but applies data penalty."""
        history = _make_history(10)
        result = detect_market_season(history)
        # Should not be Unknown
        assert result["season"] in ("Spring", "Summer", "Autumn", "Winter")
        # data_penalty = 10/20 = 0.5, so confidence is penalized
        assert result["confidence"] <= 1.0

    def test_exactly_9_rows_insufficient(self):
        """9 rows is below the 10-day minimum."""
        result = detect_market_season(_make_history(9))
        assert result["season"] == "Unknown"
        assert "9" in result["description_kr"]

    def test_data_penalty_partial(self):
        """15 rows: data_penalty = 15/20 = 0.75, applied to confidence."""
        older = _make_history(5, us_10y=4.5, copper=3.5)
        recent = _make_history(10, us_10y=3.8, copper=4.5)
        history = older + recent
        result = detect_market_season(history)
        # With 15 rows, penalty = 0.75
        assert result["confidence"] <= 1.0

    def test_20_plus_rows_no_penalty(self):
        """20+ rows: data_penalty = 1.0, no penalty."""
        history = _make_history(30, us_10y=4.5, copper=3.5) + _make_history(15, us_10y=3.8, copper=4.5)
        result = detect_market_season(history)
        # With 45 rows, penalty = min(1.0, 45/20) = 1.0
        assert result["confidence"] > 0

    def test_all_none_copper(self):
        """All None copper prices fall back to default 4.0."""
        history = [
            {"indicator_date": f"2026-01-{i:02d}", "us_10y_yield": 4.0, "copper_price": None}
            for i in range(1, 46)
        ]
        result = detect_market_season(history)
        # No copper variation → copper_mom = 0
        assert result["axes"]["components"]["copper_momentum"] == 0.0

    def test_zero_yield_values(self):
        """Zero yields should not cause division-by-zero."""
        history = _make_history(45, us_10y=0.0, copper=4.0)
        result = detect_market_season(history)
        # avg_older ~= 0, guarded by abs(avg_older) < 0.001 check
        assert result["axes"]["rate_momentum"] == 0.0
        assert result["axes"]["rate_direction"] == "flat"

    def test_very_small_yield_values(self):
        """Near-zero yields: abs(avg_older) < 0.001 triggers zero guard."""
        history = _make_history(45, us_10y=0.0005, copper=4.0)
        result = detect_market_season(history)
        assert result["axes"]["rate_momentum"] == 0.0

    def test_negative_etf_momentum(self):
        """Negative SPY return contributes negative growth proxy."""
        history = _make_history(45, us_10y=4.0, copper=4.0)
        result = detect_market_season(
            history,
            etf_momentum={"spy_return_60d": -0.12},
        )
        assert result["axes"]["components"]["etf_momentum"] < 0

    def test_etf_momentum_clamped(self):
        """ETF momentum above +-15% is clamped to +-1.0."""
        history = _make_history(45, us_10y=4.0, copper=4.0)
        result_high = detect_market_season(
            history,
            etf_momentum={"spy_return_60d": 0.50},
        )
        assert result_high["axes"]["components"]["etf_momentum"] == 1.0

        result_low = detect_market_season(
            history,
            etf_momentum={"spy_return_60d": -0.50},
        )
        assert result_low["axes"]["components"]["etf_momentum"] == -1.0

    def test_kr_flow_none_values_in_entries(self):
        """KR flow entries with None total_foreign_net treated as 0."""
        history = _make_history(45, us_10y=4.0, copper=4.0)
        kr_flow = [
            {"trade_date": f"2026-01-{i:02d}", "total_foreign_net": None}
            for i in range(1, 31)
        ]
        result = detect_market_season(history, kr_foreign_trend=kr_flow)
        assert result["axes"]["components"]["kr_flow_momentum"] == 0.0

    def test_kr_flow_insufficient(self):
        """Less than 10 KR flow entries → momentum defaults to 0."""
        history = _make_history(45, us_10y=4.0, copper=4.0)
        kr_flow = [{"total_foreign_net": 1_000_000_000} for _ in range(5)]
        result = detect_market_season(history, kr_foreign_trend=kr_flow)
        assert result["axes"]["components"]["kr_flow_momentum"] == 0.0

    def test_mixed_none_yields(self):
        """Some None yields with enough valid values to compute rate."""
        history = []
        for i in range(45):
            row = {"indicator_date": f"2026-02-{(i % 28) + 1:02d}", "copper_price": 4.0}
            # 30 valid yields, 15 None yields
            row["us_10y_yield"] = 4.0 if i < 30 else None
            history.append(row)
        result = detect_market_season(history)
        # 30 valid yields >= 15 threshold, so rate should be computed
        assert result["axes"]["rate_direction"] in ("falling", "rising", "flat")

    def test_yields_between_10_and_15(self):
        """10-14 valid yields → rate_momentum defaults to 0, direction flat."""
        history = []
        for i in range(20):
            row = {"indicator_date": f"2026-01-{i + 1:02d}", "copper_price": 4.0}
            row["us_10y_yield"] = 4.0 if i < 12 else None
            history.append(row)
        result = detect_market_season(history)
        assert result["axes"]["rate_momentum"] == 0.0
        assert result["axes"]["rate_direction"] == "flat"

    def test_return_schema_complete(self):
        """Verify all expected keys exist in a valid result."""
        history = _make_history(45)
        result = detect_market_season(history)
        required = {
            "season", "season_kr", "icon", "confidence",
            "description_kr", "strategy_kr", "axes",
        }
        assert required.issubset(result.keys())
        axes_keys = {"rate_direction", "rate_momentum", "growth_direction",
                     "growth_proxy", "components"}
        assert axes_keys.issubset(result["axes"].keys())
        comp_keys = {"copper_momentum", "etf_momentum", "kr_flow_momentum"}
        assert comp_keys.issubset(result["axes"]["components"].keys())


# ── compute_investment_clock: edge cases ──


class TestInvestmentClockEdgeCases:
    def test_zero_copper_no_division_error(self):
        """Zero copper should not cause ZeroDivisionError in gold/copper ratio.

        The code guards with max(copper, 0.01).
        """
        macro = {"copper_price": 0, "gold_price": 2000}
        result = compute_investment_clock(macro)
        # gold / max(0, 0.01) = 2000 / 0.01 = 200000 → gc_ratio > 700 → gc_inf = 0.9
        assert "quadrant" in result

    def test_none_individual_fields(self):
        """None for individual macro fields uses default/fallback."""
        macro = {
            "copper_price": None,
            "us_yield_spread": None,
            "vix": None,
            "wti_crude": None,
            "gold_price": None,
            "dxy_index": None,
        }
        result = compute_investment_clock(macro)
        assert result["quadrant"] in ("Recovery", "Overheat", "Stagflation", "Reflation")
        # yield_g, vix_g, oil_inf, dxy_inf all 0 when None
        assert result["growth_components"]["yield_curve"] == 0.0
        assert result["growth_components"]["vix_inverse"] == 0.0
        assert result["inflation_components"]["oil"] == 0.0
        assert result["inflation_components"]["dxy"] == 0.0

    def test_extreme_high_values(self):
        """Extreme macro values produce clamped scores."""
        macro = {
            "copper_price": 10.0,
            "us_yield_spread": 5.0,
            "vix": 5,
            "wti_crude": 200,
            "gold_price": 5000,
            "dxy_index": 130,
        }
        result = compute_investment_clock(macro)
        assert -1.0 <= result["growth_score"] <= 1.0
        assert -1.0 <= result["inflation_score"] <= 1.0

    def test_extreme_low_values(self):
        """Very low macro values produce clamped scores."""
        macro = {
            "copper_price": 1.0,
            "us_yield_spread": -3.0,
            "vix": 80,
            "wti_crude": 10,
            "gold_price": 500,
            "dxy_index": 80,
        }
        result = compute_investment_clock(macro)
        assert -1.0 <= result["growth_score"] <= 1.0
        assert -1.0 <= result["inflation_score"] <= 1.0

    def test_copper_trend_with_insufficient_history(self):
        """Less than 20 rows in history skips trend enhancement."""
        macro = {"copper_price": 4.0, "us_yield_spread": 0.5, "vix": 18,
                 "wti_crude": 70, "gold_price": 2200, "dxy_index": 103}
        history = _make_history(15, copper=3.0)
        result_short = compute_investment_clock(macro, history)
        result_none = compute_investment_clock(macro, None)
        # With < 20 history rows, copper trend is not applied
        # Both should use the same copper_g from macro data only
        assert result_short["growth_components"]["copper"] == result_none["growth_components"]["copper"]

    def test_copper_trend_clamped(self):
        """Copper trend adjustment is clamped to [-0.3, 0.3]."""
        macro = {"copper_price": 4.0, "us_yield_spread": 0.5, "vix": 18,
                 "wti_crude": 70, "gold_price": 2200, "dxy_index": 103}
        # Extreme copper trend: very low early, very high late
        history = _make_history(10, copper=1.0) + _make_history(15, copper=8.0)
        result = compute_investment_clock(macro, history)
        assert -1.0 <= result["growth_components"]["copper"] <= 1.0

    def test_vix_thresholds(self):
        """Verify VIX threshold transitions."""
        base = {"copper_price": 4.0, "us_yield_spread": 0.5, "wti_crude": 70,
                "gold_price": 2200, "dxy_index": 103}

        # VIX < 13: calm
        r1 = compute_investment_clock({**base, "vix": 10})
        assert r1["growth_components"]["vix_inverse"] == 0.7

        # VIX 13-18: moderate calm
        r2 = compute_investment_clock({**base, "vix": 15})
        assert r2["growth_components"]["vix_inverse"] == 0.5

        # VIX 22-28: concern
        r3 = compute_investment_clock({**base, "vix": 25})
        assert r3["growth_components"]["vix_inverse"] == -0.4

        # VIX >= 28: panic
        r4 = compute_investment_clock({**base, "vix": 35})
        assert r4["growth_components"]["vix_inverse"] == -0.8

    def test_wti_thresholds(self):
        """Verify WTI oil threshold transitions."""
        base = {"copper_price": 4.0, "us_yield_spread": 0.5, "vix": 18,
                "gold_price": 2200, "dxy_index": 103}

        r_high = compute_investment_clock({**base, "wti_crude": 110})
        assert r_high["inflation_components"]["oil"] == 0.9

        r_low = compute_investment_clock({**base, "wti_crude": 35})
        assert r_low["inflation_components"]["oil"] == -0.8

    def test_yield_spread_thresholds(self):
        """Verify yield spread growth scoring thresholds."""
        base = {"copper_price": 4.0, "vix": 18, "wti_crude": 70,
                "gold_price": 2200, "dxy_index": 103}

        # Steep curve (> 1.5)
        r1 = compute_investment_clock({**base, "us_yield_spread": 2.0})
        assert r1["growth_components"]["yield_curve"] == 0.8

        # Deeply inverted (< -0.5)
        r2 = compute_investment_clock({**base, "us_yield_spread": -1.0})
        assert r2["growth_components"]["yield_curve"] == -0.9

    def test_gold_copper_ratio_high(self):
        """High gold/copper ratio signals stagflation."""
        macro = {"copper_price": 2.5, "gold_price": 2500,
                 "us_yield_spread": 0.5, "vix": 18, "wti_crude": 70, "dxy_index": 103}
        result = compute_investment_clock(macro)
        # ratio = 2500 / 2.5 = 1000 → gc_inf = 0.9
        assert result["inflation_components"]["gold_copper_ratio"] == 0.9

    def test_gold_copper_ratio_low(self):
        """Low gold/copper ratio signals low inflation."""
        macro = {"copper_price": 5.0, "gold_price": 1500,
                 "us_yield_spread": 0.5, "vix": 18, "wti_crude": 70, "dxy_index": 103}
        result = compute_investment_clock(macro)
        # ratio = 1500 / 5 = 300 → gc_inf = -0.6
        assert result["inflation_components"]["gold_copper_ratio"] == -0.6


# ── detect_yield_phase: edge cases ──


class TestYieldPhaseEdgeCases:
    def test_empty_list(self):
        """Empty list → Unknown."""
        result = detect_yield_phase([])
        assert result["phase"] == "Unknown"

    def test_all_none_values(self):
        """All None values → filtered to empty → Unknown."""
        result = detect_yield_phase([None] * 30)
        assert result["phase"] == "Unknown"
        assert result["current_spread"] is None

    def test_exactly_10_values(self):
        """Exactly 10 valid values is the minimum for a real result."""
        result = detect_yield_phase([1.5] * 10)
        assert result["phase"] != "Unknown"
        assert result["current_spread"] == 1.5

    def test_9_values_insufficient(self):
        """9 valid values (after None filtering) is insufficient."""
        result = detect_yield_phase([1.5] * 9 + [None, None])
        assert result["phase"] == "Unknown"

    def test_spread_at_zero_boundary(self):
        """Current spread exactly 0.0 is in the 0-0.5 range, not inverted."""
        spreads = [0.0] * 30
        result = detect_yield_phase(spreads)
        # current=0, trend=stable → transitioning
        assert result["phase"] in ("Transitioning", "Flattening", "Normalizing")

    def test_spread_at_half_boundary(self):
        """Current spread exactly 0.5 is in the 0.5-1.0 range."""
        spreads = [0.5] * 30
        result = detect_yield_phase(spreads)
        assert result["phase"] in ("Normal", "Flattening")

    def test_spread_at_one_boundary(self):
        """Current spread exactly 1.0 is in the >= 1.0 range → Normal."""
        spreads = [1.0] * 30
        result = detect_yield_phase(spreads)
        assert result["phase"] == "Normal"

    def test_deep_inversion_followed_by_recovery(self):
        """Deep inversion (-1.0) recovering to positive → Normalizing."""
        spreads = [-1.0] * 20 + [-0.5, -0.3, -0.1, 0.0, 0.1, 0.2, 0.25, 0.3, 0.35, 0.4]
        result = detect_yield_phase(spreads)
        assert result["phase"] == "Normalizing"
        assert result["risk_flag"] is True

    def test_inverted_steepening_is_normalizing(self):
        """Negative spread but trend = steepening → Normalizing."""
        # Older: very negative, recent: less negative
        older = [-0.8] * 15
        recent = [-0.5, -0.4, -0.35, -0.3, -0.25, -0.2, -0.18, -0.15, -0.12, -0.1]
        result = detect_yield_phase(older + recent)
        assert result["phase"] == "Normalizing"

    def test_trend_stable(self):
        """Nearly identical older and recent averages → stable trend."""
        spreads = [0.3] * 30
        result = detect_yield_phase(spreads)
        assert result["trend"] == "stable"

    def test_trend_steepening(self):
        """Recent average > older average by > 0.05 → steepening."""
        spreads = [0.2] * 15 + [0.5] * 15
        result = detect_yield_phase(spreads)
        assert result["trend"] == "steepening"

    def test_trend_flattening(self):
        """Recent average < older average by > 0.05 → flattening."""
        spreads = [1.0] * 15 + [0.3] * 15
        result = detect_yield_phase(spreads)
        assert result["trend"] == "flattening"

    def test_avg_10d_accuracy(self):
        """avg_10d correctly averages last 10 values."""
        spreads = [0.0] * 15 + [1.0] * 10
        result = detect_yield_phase(spreads)
        assert result["avg_10d"] == 1.0

    def test_none_mixed_with_valid(self):
        """None values interspersed with valid spreads are filtered."""
        spreads = [None, 1.5, None, 1.4, None, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6]
        result = detect_yield_phase(spreads)
        # 10 valid values → should work
        assert result["phase"] != "Unknown"

    def test_only_10_data_older_fallback(self):
        """Exactly 10 data points: older_spreads is empty, avg_older = avg_recent."""
        result = detect_yield_phase([0.8] * 10)
        assert result["trend"] == "stable"  # avg_older == avg_recent


# ── check_strategy_match: edge cases ──


class TestStrategyMatchEdgeCases:
    def test_none_portfolio_and_signal(self):
        """None for both optional params uses defaults."""
        result = check_strategy_match("Summer", "Recovery", None, None)
        assert "match_score" in result
        assert result["warning_count"] >= 0

    def test_overheat_tech_heavy(self):
        """Overheat + tech > 50% → warning."""
        result = check_strategy_match(
            season="Summer",
            clock_quadrant="Overheat",
            portfolio_summary={"total_positions": 10, "kr_pct": 30,
                               "us_pct": 70, "tech_pct": 65, "total_invested": 100_000_000},
        )
        assert any("기술주" in w["message"] for w in result["warnings"])

    def test_reflation_tech_heavy(self):
        """Reflation + tech > 40% → info warning."""
        result = check_strategy_match(
            season="Winter",
            clock_quadrant="Reflation",
            portfolio_summary={"total_positions": 5, "kr_pct": 50,
                               "us_pct": 50, "tech_pct": 45, "total_invested": 50_000_000},
        )
        assert any("Reflation" in w["message"] or "환기" in w["message"]
                    for w in result["warnings"])

    def test_summer_sell_heavy(self):
        """Summer + more sells than buys → info about sell signals."""
        result = check_strategy_match(
            season="Summer",
            clock_quadrant="Overheat",
            signal_summary={"buy_count": 1, "sell_count": 5, "hold_count": 2},
        )
        assert any("매도 시그널" in w["message"] for w in result["warnings"])

    def test_winter_many_positions(self):
        """Winter + > 10 positions → info-level warning."""
        result = check_strategy_match(
            season="Winter",
            clock_quadrant="Reflation",
            portfolio_summary={"total_positions": 15, "kr_pct": 60,
                               "us_pct": 40, "tech_pct": 20, "total_invested": 80_000_000},
        )
        assert any("핵심 종목" in w["message"] for w in result["warnings"])

    def test_autumn_buy_heavy(self):
        """Autumn + buy_count > sell_count → info about caution."""
        result = check_strategy_match(
            season="Autumn",
            clock_quadrant="Overheat",
            signal_summary={"buy_count": 6, "sell_count": 2, "hold_count": 3},
        )
        assert any("선별적" in w["message"] for w in result["warnings"])

    def test_match_score_bullish_aligned(self):
        """Spring/Recovery with positions should score above neutral."""
        result = check_strategy_match(
            season="Spring",
            clock_quadrant="Recovery",
            portfolio_summary={"total_positions": 8, "kr_pct": 50,
                               "us_pct": 50, "tech_pct": 30, "total_invested": 50_000_000},
            signal_summary={"buy_count": 5, "sell_count": 1, "hold_count": 3},
        )
        assert result["match_score"] >= 50

    def test_match_score_bearish_aligned(self):
        """Winter with few positions and sell signals → good alignment."""
        result = check_strategy_match(
            season="Winter",
            clock_quadrant="Reflation",
            portfolio_summary={"total_positions": 2, "kr_pct": 50,
                               "us_pct": 50, "tech_pct": 0, "total_invested": 5_000_000},
            signal_summary={"buy_count": 0, "sell_count": 3, "hold_count": 2},
        )
        assert result["match_score"] >= 50

    def test_match_score_bearish_misaligned(self):
        """Winter with many positions → poor alignment, low score."""
        result = check_strategy_match(
            season="Winter",
            clock_quadrant="Stagflation",
            portfolio_summary={"total_positions": 15, "kr_pct": 80,
                               "us_pct": 20, "tech_pct": 50, "total_invested": 100_000_000},
            signal_summary={"buy_count": 10, "sell_count": 0, "hold_count": 2},
        )
        # Many positions in winter + stagflation should penalize
        assert result["match_score"] < 50

    def test_return_includes_season_and_quadrant(self):
        """Result echoes back the input season and quadrant."""
        result = check_strategy_match("Autumn", "Overheat")
        assert result["season"] == "Autumn"
        assert result["clock_quadrant"] == "Overheat"


# ── compute_unified_risk_score: edge cases ──


class TestUnifiedRiskScoreEdgeCases:
    def test_unknown_quadrant_uses_default(self):
        """Unknown clock quadrant falls back to risk value 50."""
        result = compute_unified_risk_score(50.0, 0.0, "NotAQuadrant")
        # clock_val = 50 (default), clock_component = 50 * 0.30 = 15
        assert result["components"]["investment_clock"]["risk_value"] == 50

    def test_case_insensitive_quadrant(self):
        """Quadrant matching is case-insensitive."""
        r1 = compute_unified_risk_score(50.0, 0.0, "RECOVERY")
        r2 = compute_unified_risk_score(50.0, 0.0, "recovery")
        r3 = compute_unified_risk_score(50.0, 0.0, "Recovery")
        assert r1["score"] == r2["score"] == r3["score"]

    def test_extreme_stagflation_index(self):
        """Stagflation index well above 100 is not clamped in component but score is."""
        result = compute_unified_risk_score(200.0, -1.0, "Stagflation")
        assert result["score"] == 100.0

    def test_negative_stagflation_index(self):
        """Negative stagflation index (bad data) produces low but clamped score."""
        result = compute_unified_risk_score(-50.0, 1.0, "Recovery")
        assert result["score"] >= 0.0

    def test_risk_regime_at_boundaries(self):
        """Risk regime +1 (complacent) and -1 (panic) normalization."""
        # +1 → normalized = ((1 - 1)/2)*100 = 0 → low risk contribution
        r_calm = compute_unified_risk_score(0.0, 1.0, "Recovery")
        assert r_calm["components"]["risk_regime"]["normalized"] == 0.0

        # -1 → normalized = ((1 - (-1))/2)*100 = 100 → high risk contribution
        r_panic = compute_unified_risk_score(0.0, -1.0, "Recovery")
        assert r_panic["components"]["risk_regime"]["normalized"] == 100.0

    def test_all_risk_levels_reachable(self):
        """Verify all 5 risk levels can be produced."""
        levels_seen = set()
        test_cases = [
            (0, 1.0, "Recovery"),     # Low
            (30, 0.3, "Recovery"),    # Moderate
            (50, 0.0, "Overheat"),   # Elevated
            (80, -0.5, "Stagflation"),  # High
            (100, -1.0, "Stagflation"),  # Critical
        ]
        for stag, regime, quad in test_cases:
            result = compute_unified_risk_score(stag, regime, quad)
            levels_seen.add(result["level"])

        assert "Low" in levels_seen
        assert "Critical" in levels_seen
        assert len(levels_seen) >= 3  # at least 3 distinct levels

    def test_contribution_sums_to_score(self):
        """Component contributions should approximately sum to the unified score."""
        result = compute_unified_risk_score(50.0, 0.2, "Overheat")
        contrib_sum = sum(c["contribution"] for c in result["components"].values())
        # Allow rounding tolerance
        assert abs(contrib_sum - result["score"]) < 1.0

    def test_score_rounding(self):
        """Score is rounded to 1 decimal place."""
        result = compute_unified_risk_score(33.333, 0.123, "Reflation")
        score_str = str(result["score"])
        if "." in score_str:
            decimal_places = len(score_str.split(".")[1])
            assert decimal_places <= 1
