"""Tests for action plan indicator module.

Covers: stance determination, cash ratio, Kelly fraction, position sizing,
price targets, portfolio actions, and daily strategy generation.
"""

import pytest

from app.indicators.action_plan import (
    compute_kelly_fraction,
    recommend_position_size,
    compute_price_targets,
    generate_portfolio_actions,
    generate_daily_strategy,
    _compute_stance,
    _compute_cash_ratio,
    _compute_sector_bias,
    _determine_position_action,
    _risk_level_kr,
    _summarize_guru_consensus,
    rank_top_picks,
)


# ── Stance Determination ──

class TestComputeStance:
    """_compute_stance: 8-step priority chain."""

    def test_peak_fear_overrides_all(self):
        key, kr, reason = _compute_stance(risk_score=20, fear_phase="Peak Fear", season="spring")
        assert key == "contrarian_buy"
        assert "역발상" in kr

    def test_initial_panic_overrides_risk(self):
        key, kr, reason = _compute_stance(risk_score=10, fear_phase="Initial Panic", season="summer")
        assert key == "defensive"
        assert "방어" in kr

    def test_high_risk_very_defensive(self):
        key, kr, reason = _compute_stance(risk_score=80, fear_phase="Normal", season="spring")
        assert key == "very_defensive"

    def test_moderate_risk_cautious(self):
        key, kr, reason = _compute_stance(risk_score=65, fear_phase="Normal", season="spring")
        assert key == "cautious"

    def test_autumn_season_cautious(self):
        key, kr, reason = _compute_stance(risk_score=40, fear_phase="Normal", season="autumn")
        assert key == "cautious"
        assert "역금융장세" in reason

    def test_winter_season_cautious(self):
        key, kr, reason = _compute_stance(risk_score=40, fear_phase="Normal", season="winter")
        assert key == "cautious"
        assert "역실적장세" in reason

    def test_low_risk_spring_aggressive(self):
        key, kr, reason = _compute_stance(risk_score=25, fear_phase="Normal", season="spring")
        assert key == "aggressive"
        assert "적극 매수" in kr

    def test_low_risk_summer_aggressive(self):
        key, kr, reason = _compute_stance(risk_score=20, fear_phase="Normal", season="summer")
        assert key == "aggressive"

    def test_moderate_risk_moderate_buy(self):
        key, kr, reason = _compute_stance(risk_score=40, fear_phase="Normal", season="spring")
        assert key == "moderate_buy"

    def test_mid_risk_neutral(self):
        key, kr, reason = _compute_stance(risk_score=55, fear_phase="Normal", season="spring")
        assert key == "neutral"
        assert "중립" in kr


# ── Cash Ratio ──

class TestComputeCashRatio:
    def test_initial_panic_50(self):
        assert _compute_cash_ratio(30, "Initial Panic", "spring") == 50

    def test_high_risk_40(self):
        assert _compute_cash_ratio(80, "Normal", "spring") == 40

    def test_winter_35(self):
        assert _compute_cash_ratio(50, "Normal", "winter") == 35

    def test_high_risk_or_autumn_30(self):
        assert _compute_cash_ratio(65, "Normal", "spring") == 30

    def test_autumn_season_30(self):
        assert _compute_cash_ratio(40, "Normal", "autumn") == 30

    def test_low_risk_spring_10(self):
        assert _compute_cash_ratio(25, "Normal", "spring") == 10

    def test_moderate_risk_15(self):
        assert _compute_cash_ratio(40, "Normal", "spring") == 15

    def test_default_20(self):
        assert _compute_cash_ratio(55, "Normal", "spring") == 20


# ── Kelly Fraction ──

class TestKellyFraction:
    def test_positive_edge(self):
        result = compute_kelly_fraction(win_rate=0.6, avg_win=10, avg_loss=5)
        assert result > 0

    def test_negative_edge(self):
        result = compute_kelly_fraction(win_rate=0.3, avg_win=5, avg_loss=10)
        assert result == 0  # Should be 0 for negative expectancy

    def test_zero_loss(self):
        result = compute_kelly_fraction(win_rate=0.5, avg_win=10, avg_loss=0)
        # Should handle zero division gracefully
        assert isinstance(result, float)

    def test_bounds(self):
        # Kelly should be bounded (not exceed 100%)
        result = compute_kelly_fraction(win_rate=0.99, avg_win=100, avg_loss=1)
        assert 0 <= result <= 1


# ── Position Sizing ──

class TestPositionSizing:
    def test_basic_sizing(self):
        result = recommend_position_size(
            total_capital=100_000_000,
            signal_score=3.0,
            confidence=80,
        )
        assert "amount" in result
        assert "pct" in result
        assert result["amount"] > 0

    def test_low_confidence_reduces_size(self):
        high = recommend_position_size(100_000_000, 3.0, 90)
        low = recommend_position_size(100_000_000, 3.0, 30)
        assert high["pct"] >= low["pct"]

    def test_max_single_position_cap(self):
        result = recommend_position_size(
            total_capital=100_000_000,
            signal_score=50.0,
            confidence=100,
            max_single_pct=0.05,
        )
        assert result["pct"] <= 5.0

    def test_zero_capital(self):
        result = recommend_position_size(0, 3.0, 80)
        assert result["amount"] == 0


# ── Price Targets ──

class TestPriceTargets:
    def test_buy_signal(self):
        result = compute_price_targets(
            current_price=50000,
            rsi=35,
            signal_type="BUY",
            ma_20=48000,
            ma_60=45000,
        )
        assert "stop_loss" in result
        assert "target" in result
        assert result["stop_loss"] < 50000
        assert result["target"] > 50000

    def test_sell_signal(self):
        result = compute_price_targets(
            current_price=50000,
            rsi=75,
            signal_type="SELL",
        )
        assert "stop_loss" in result
        assert "target" in result

    def test_none_rsi(self):
        result = compute_price_targets(50000, None, "BUY")
        assert isinstance(result, dict)

    def test_zero_price(self):
        result = compute_price_targets(0, 50, "BUY")
        assert isinstance(result, dict)


# ── Portfolio Actions ──

class TestPortfolioActions:
    def test_empty_inputs(self):
        result = generate_portfolio_actions([], [])
        assert result == []

    def test_with_positions_and_signals(self):
        positions = [
            {"symbol": "005930", "market": "KR", "entry_price": 50000,
             "current_price": 55000, "pnl_pct": 10.0}
        ]
        signals = [
            {"symbol": "005930", "market": "KR", "final_signal": "BUY",
             "raw_score": 2.5, "rsi_value": 40}
        ]
        result = generate_portfolio_actions(positions, signals)
        assert isinstance(result, list)


# ── Daily Strategy ──

class TestDailyStrategy:
    @pytest.fixture
    def base_inputs(self):
        return {
            "macro_data": {"vix": 18, "us_yield_spread": 1.0},
            "regime": {"regime": "expansion", "risk_score": {"score": 35}},
            "season": {"season": "spring", "confidence": 0.7, "clock": {"quadrant_kr": ""}},
            "fear_gauge": {"phase": "Normal", "score": 25},
            "signal_summary": {
                "total": 10, "buy_count": 3, "sell_count": 2, "hold_count": 5,
                "avg_score": 1.2, "kr_count": 5, "us_count": 5,
            },
        }

    def test_returns_required_keys(self, base_inputs):
        result = generate_daily_strategy(**base_inputs)
        assert "stance" in result
        assert "cash_ratio" in result
        assert "action_items" in result

    def test_stance_reflects_inputs(self, base_inputs):
        result = generate_daily_strategy(**base_inputs)
        # spring + low risk → should be aggressive or moderate_buy
        assert result["stance"] in ("aggressive", "moderate_buy")

    def test_high_risk_defensive(self, base_inputs):
        base_inputs["regime"]["risk_score"] = {"score": 85}
        result = generate_daily_strategy(**base_inputs)
        assert result["stance"] in ("very_defensive", "defensive")

    def test_with_guru_consensus(self, base_inputs):
        base_inputs["guru_consensus"] = {
            "avg_conviction": 65,
            "bullish_pct": 0.6,
        }
        result = generate_daily_strategy(**base_inputs)
        assert isinstance(result, dict)


# ── Top Picks Ranking ──

class TestRankTopPicks:
    def test_empty_signals(self):
        result = rank_top_picks([], [], 100_000_000)
        assert result == []

    def test_basic_ranking(self):
        signals = [
            {"symbol": "005930", "name": "삼성전자", "market": "KR",
             "final_signal": "BUY", "raw_score": 3.0, "rsi_value": 35,
             "confidence": 0.8},
            {"symbol": "AAPL", "name": "Apple", "market": "US",
             "final_signal": "BUY", "raw_score": 2.0, "rsi_value": 42,
             "confidence": 0.6},
        ]
        result = rank_top_picks(signals, [], 100_000_000, max_picks=5)
        assert isinstance(result, list)
        # Should only include BUY signals
        for pick in result:
            assert "symbol" in pick

    def test_excludes_held_positions(self):
        signals = [
            {"symbol": "A", "final_signal": "BUY", "raw_score": 50},
            {"symbol": "B", "final_signal": "BUY", "raw_score": 40},
        ]
        positions = [{"symbol": "A"}]
        result = rank_top_picks(signals, positions, 100_000_000)
        assert len(result) == 1
        assert result[0]["symbol"] == "B"

    def test_sorted_by_score_descending(self):
        signals = [
            {"symbol": "A", "final_signal": "BUY", "raw_score": 20},
            {"symbol": "B", "final_signal": "BUY", "raw_score": 50},
            {"symbol": "C", "final_signal": "BUY", "raw_score": 35},
        ]
        result = rank_top_picks(signals, [], 100_000_000)
        assert result[0]["symbol"] == "B"
        assert result[1]["symbol"] == "C"
        assert result[2]["symbol"] == "A"

    def test_max_picks_limit(self):
        signals = [
            {"symbol": f"S{i}", "final_signal": "BUY", "raw_score": 40 - i}
            for i in range(10)
        ]
        result = rank_top_picks(signals, [], 100_000_000, max_picks=3)
        assert len(result) == 3

    def test_picks_have_sizing_and_targets(self):
        signals = [{"symbol": "A", "final_signal": "BUY", "raw_score": 40,
                     "confidence": 70, "rsi_value": 35, "current_price": 50000}]
        result = rank_top_picks(signals, [], 100_000_000)
        assert result[0]["recommended_size"] > 0
        assert result[0]["target_price"] > 50000
        assert result[0]["stop_loss"] < 50000


# ── Position Action Determination ──

class TestDeterminePositionAction:
    def test_cut_loss(self):
        result = _determine_position_action(-8.0, {}, {})
        assert result["action"] == "CUT_LOSS"
        assert result["urgency"] == "high"

    def test_cut_loss_boundary(self):
        result = _determine_position_action(-7.0, {}, {})
        assert result["action"] == "CUT_LOSS"

    def test_take_profit(self):
        result = _determine_position_action(16.0, {}, {})
        assert result["action"] == "TAKE_PROFIT"
        assert result["urgency"] == "high"

    def test_take_profit_boundary(self):
        result = _determine_position_action(15.0, {}, {})
        assert result["action"] == "TAKE_PROFIT"

    def test_partial_profit(self):
        result = _determine_position_action(12.0, {}, {})
        assert result["action"] == "PARTIAL_PROFIT"
        assert result["urgency"] == "medium"

    def test_sell_signal_reduce(self):
        result = _determine_position_action(3.0, {"final_signal": "SELL", "raw_score": -20}, {})
        assert result["action"] == "REDUCE"
        assert result["urgency"] == "high"

    def test_watch_closely(self):
        result = _determine_position_action(-6.0, {}, {})
        assert result["action"] == "WATCH_CLOSELY"
        assert result["urgency"] == "medium"

    def test_add_more(self):
        result = _determine_position_action(2.0, {"final_signal": "BUY", "raw_score": 30}, {})
        assert result["action"] == "ADD_MORE"
        assert result["urgency"] == "low"

    def test_add_not_when_losing(self):
        # pnl_pct <= -3.0 → not eligible for ADD_MORE
        result = _determine_position_action(-4.0, {"final_signal": "BUY", "raw_score": 30}, {})
        assert result["action"] != "ADD_MORE"

    def test_overbought_warning(self):
        result = _determine_position_action(5.0, {"rsi_value": 75}, {})
        assert result["action"] == "WATCH_OVERBOUGHT"

    def test_default_hold(self):
        result = _determine_position_action(3.0, {"final_signal": "HOLD"}, {})
        assert result["action"] == "HOLD"
        assert result["urgency"] == "low"


# ── Sector Bias ──

class TestSectorBias:
    def test_spring_sectors(self):
        biases = _compute_sector_bias("spring", "", {})
        sectors = [b["sector"] for b in biases]
        assert "성장주/기술주" in sectors

    def test_winter_sectors(self):
        biases = _compute_sector_bias("winter", "", {})
        sectors = [b["sector"] for b in biases]
        assert "현금/단기채" in sectors

    def test_unknown_season(self):
        biases = _compute_sector_bias("unknown", "", {})
        assert any("분산 투자" in b["sector"] for b in biases)

    def test_high_vix_adds_gold(self):
        biases = _compute_sector_bias("spring", "", {"vix": 30})
        sectors = [b["sector"] for b in biases]
        assert "금/안전자산" in sectors

    def test_high_wti_adds_energy(self):
        biases = _compute_sector_bias("spring", "", {"wti_crude": 90})
        sectors = [b["sector"] for b in biases]
        assert "에너지" in sectors


# ── Risk Level KR ──

class TestRiskLevelKr:
    def test_very_high(self):
        assert "매우 높음" in _risk_level_kr(80)

    def test_high(self):
        assert "높음" in _risk_level_kr(65)

    def test_moderate(self):
        assert "보통" in _risk_level_kr(50)

    def test_low(self):
        assert "낮음" in _risk_level_kr(30)

    def test_very_low(self):
        assert "매우 낮음" in _risk_level_kr(20)


# ── Guru Consensus ──

class TestGuruConsensus:
    def test_none_input(self):
        assert _summarize_guru_consensus(None) is None

    def test_empty_gurus(self):
        assert _summarize_guru_consensus({"gurus": []}) is None

    def test_bullish_consensus(self):
        gurus = [
            {"market_view": {"stance": "bullish", "conviction": 70}},
            {"market_view": {"stance": "bullish", "conviction": 80}},
            {"market_view": {"stance": "neutral", "conviction": 50}},
        ]
        result = _summarize_guru_consensus(gurus)
        assert result["consensus"] == "bullish"
        assert result["guru_count"] == 3
        assert abs(result["avg_conviction"] - 66.7) < 0.1

    def test_selective_buy(self):
        gurus = [
            {"market_view": {"stance": "selective_buy", "conviction": 60}},
            {"market_view": {"stance": "selective_buy", "conviction": 60}},
            {"market_view": {"stance": "neutral", "conviction": 50}},
        ]
        result = _summarize_guru_consensus(gurus)
        assert result["consensus"] == "selective_buy"

    def test_dict_input(self):
        data = {"gurus": [
            {"market_view": {"stance": "bearish", "conviction": 60}},
            {"market_view": {"stance": "bearish", "conviction": 55}},
        ]}
        result = _summarize_guru_consensus(data)
        assert result["consensus"] == "bearish"


# ── Portfolio Actions (sorted) ──

class TestPortfolioActionsSorted:
    def test_sorted_by_urgency(self):
        positions = [
            {"symbol": "A", "pnl_pct": 3.0, "current_price": 100},
            {"symbol": "B", "pnl_pct": -8.0, "current_price": 100},
        ]
        signals = [
            {"symbol": "A", "final_signal": "HOLD"},
            {"symbol": "B", "final_signal": "HOLD"},
        ]
        actions = generate_portfolio_actions(positions, signals)
        assert len(actions) == 2
        assert actions[0]["symbol"] == "B"  # CUT_LOSS = high urgency
        assert actions[0]["action"] == "CUT_LOSS"

    def test_missing_pnl_skipped(self):
        positions = [{"symbol": "A", "pnl_pct": None, "current_price": 100}]
        assert generate_portfolio_actions(positions, []) == []

    def test_missing_current_price_skipped(self):
        positions = [{"symbol": "A", "pnl_pct": 5.0, "current_price": None}]
        assert generate_portfolio_actions(positions, []) == []
