"""Tests for Stage 9 portfolio scenario generation (rule-based helpers)."""

import pytest
from unittest.mock import MagicMock

from app.pipeline.stages.s9_portfolio_scenarios import (
    _build_hold_scenario,
    _build_entry_scenario,
    _format_hold_summary_kr,
    _format_entry_summary_kr,
    _get_current_price,
)
from app.pipeline.base import StageResult


def _make_config(**overrides):
    config = MagicMock()
    config.BACKTEST_STOP_LOSS_PCT = -7.0
    config.PORTFOLIO_TOTAL = 100_000_000
    config.MAX_SINGLE_POSITION_PCT = 0.10
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


class TestBuildHoldScenario:
    """Test _build_hold_scenario function."""

    def test_profitable_position(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 50, "final_signal": "HOLD", "confidence": 0.9},
            current_price=67000,
            config=_make_config(),
        )
        assert scenario["pnl_pct"] > 10  # 67000/60000 ~= 11.7%
        assert scenario["entry_price"] == 60000
        assert scenario["current_price"] == 67000
        assert any(s["type"] == "trailing_stop" for s in scenario["scenarios"])

    def test_large_profit_triggers_profit_take(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 50000},
            signal={"rsi_value": 50, "final_signal": "HOLD", "confidence": 0.9},
            current_price=60000,
            config=_make_config(),
        )
        assert scenario["pnl_pct"] == 20.0
        assert any(s["type"] == "profit_take" for s in scenario["scenarios"])

    def test_loss_below_stop_loss(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 40, "final_signal": "SELL", "confidence": 0.8},
            current_price=54000,
            config=_make_config(),
        )
        assert scenario["pnl_pct"] == -10.0
        assert any(s["type"] == "stop_loss" for s in scenario["scenarios"])

    def test_mild_loss_shows_stop_approach(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 45, "final_signal": "HOLD", "confidence": 0.9},
            current_price=58000,
            config=_make_config(),
        )
        pnl = scenario["pnl_pct"]
        assert pnl < 0
        assert pnl > -7  # Above stop loss
        assert any(s["type"] == "stop_approach" for s in scenario["scenarios"])

    def test_sell_signal_scenario(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 50, "final_signal": "SELL", "confidence": 0.8},
            current_price=61000,
            config=_make_config(),
        )
        assert any(s["type"] == "signal_sell" for s in scenario["scenarios"])

    def test_buy_signal_on_held_suggests_accumulate(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 40, "final_signal": "BUY", "confidence": 0.9},
            current_price=61000,
            config=_make_config(),
        )
        assert any(s["type"] == "accumulate" for s in scenario["scenarios"])

    def test_high_rsi_warning(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 70, "final_signal": "HOLD", "confidence": 0.9},
            current_price=63000,
            config=_make_config(),
        )
        assert any(s["type"] == "overbought_warning" for s in scenario["scenarios"])

    def test_low_rsi_oversold_bounce(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 20, "final_signal": "SELL", "confidence": 0.7},
            current_price=56000,
            config=_make_config(),
        )
        assert any(s["type"] == "oversold_bounce" for s in scenario["scenarios"])

    def test_target_prices_calculated(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 50, "final_signal": "HOLD", "confidence": 0.9},
            current_price=61000,
            config=_make_config(),
        )
        assert scenario["target_prices"]["stop_loss"] < 60000  # Below entry
        assert scenario["target_prices"]["target_10pct"] == 66000  # Entry * 1.10
        assert scenario["target_prices"]["target_20pct"] == 72000  # Entry * 1.20

    def test_scenario_rule_not_empty(self):
        scenario = _build_hold_scenario(
            symbol="005930", name="삼성전자",
            holding={"entry_price": 60000},
            signal={"rsi_value": 50, "final_signal": "HOLD", "confidence": 0.9},
            current_price=61000,
            config=_make_config(),
        )
        assert len(scenario["scenario_rule"]) > 0
        assert "삼성전자" in scenario["scenario_rule"]


class TestBuildEntryScenario:
    """Test _build_entry_scenario function."""

    def test_basic_entry(self):
        scenario = _build_entry_scenario(
            symbol="005930", name="삼성전자",
            signal={"raw_score": 25, "confidence": 0.9, "position_recommendation": {}},
            current_price=60000,
            config=_make_config(),
        )
        assert scenario["final_signal"] == "BUY"
        assert scenario["current_price"] == 60000
        assert scenario["target_prices"]["stop_loss"] < 60000
        assert scenario["target_prices"]["target_10pct"] == 66000
        assert scenario["rr_ratio"] > 0

    def test_entry_with_recommended_amount(self):
        scenario = _build_entry_scenario(
            symbol="005930", name="삼성전자",
            signal={"raw_score": 30, "confidence": 1.0,
                     "position_recommendation": {"recommended_amount": 10_000_000}},
            current_price=60000,
            config=_make_config(),
        )
        assert scenario["recommended_amount"] == 10_000_000
        assert "추천 투자금" in scenario["scenario_rule"]

    def test_entry_no_recommended_amount(self):
        scenario = _build_entry_scenario(
            symbol="AAPL", name="Apple",
            signal={"raw_score": 20, "confidence": 0.8, "position_recommendation": {}},
            current_price=200,
            config=_make_config(),
        )
        assert scenario["recommended_amount"] == 0
        assert "추천 투자금" not in scenario["scenario_rule"]

    def test_rr_ratio_calculation(self):
        """R:R = (target - entry) / (entry - stop_loss)."""
        config = _make_config(BACKTEST_STOP_LOSS_PCT=-7.0)
        scenario = _build_entry_scenario(
            symbol="005930", name="삼성전자",
            signal={"raw_score": 25, "confidence": 0.9, "position_recommendation": {}},
            current_price=100000,
            config=config,
        )
        # Target 10%: 110000, Stop 7%: 93000
        # R:R = (110000-100000) / (100000-93000) = 10000/7000 = 1.43
        assert abs(scenario["rr_ratio"] - 1.43) < 0.1


class TestFormatHoldSummaryKr:
    """Test Korean hold scenario formatting."""

    def test_high_profit(self):
        text = _format_hold_summary_kr("삼성전자", [], 20, 72000, 60000)
        assert "익절" in text

    def test_moderate_profit(self):
        text = _format_hold_summary_kr("삼성전자", [], 8, 64800, 60000)
        assert "양호" in text

    def test_breakeven(self):
        text = _format_hold_summary_kr("삼성전자", [], 1, 60600, 60000)
        assert "보합" in text

    def test_near_stop_loss(self):
        text = _format_hold_summary_kr("삼성전자", [], -4, 57600, 60000)
        assert "손절 라인 근접" in text

    def test_below_stop_loss(self):
        text = _format_hold_summary_kr("삼성전자", [], -8, 55200, 60000)
        assert "즉시" in text


class TestFormatEntrySummaryKr:
    """Test Korean entry scenario formatting."""

    def test_basic_format(self):
        text = _format_entry_summary_kr("삼성전자", 60000, 55800, 66000, 0.9, 1.4, 0)
        assert "삼성전자" in text
        assert "진입가" in text
        assert "손절" in text
        assert "R:R" in text

    def test_with_recommended_amount(self):
        text = _format_entry_summary_kr("삼성전자", 60000, 55800, 66000, 0.9, 1.4, 10_000_000)
        assert "추천 투자금" in text


class TestGetCurrentPrice:
    """Test _get_current_price helper."""

    def test_none_s1_returns_none(self):
        assert _get_current_price(None, "005930") is None

    def test_empty_data_returns_none(self):
        s1 = StageResult(stage_name="s1", status="success", data={})
        assert _get_current_price(s1, "005930") is None

    def test_missing_symbol_returns_none(self):
        import pandas as pd
        s1 = StageResult(
            stage_name="s1", status="success",
            data={"ohlcv_data": {}},
        )
        assert _get_current_price(s1, "005930") is None

    def test_valid_data_returns_close(self):
        import pandas as pd
        df = pd.DataFrame({"close": [50000, 51000, 52000]})
        s1 = StageResult(
            stage_name="s1", status="success",
            data={"ohlcv_data": {"005930": df}},
        )
        assert _get_current_price(s1, "005930") == 52000.0
