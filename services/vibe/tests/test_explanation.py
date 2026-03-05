"""Tests for Stage 8 Korean signal explanation generator (rule-based)."""

import pytest

from app.indicators.fundamental import compute_fundamental_score
from app.models.enums import SignalType
from app.pipeline.stages.s8_explanation import (
    _generate_rule_based_explanation,
    _fmt,
)


class TestRuleBasedExplanation:
    """Test rule-based Korean explanation generation."""

    def test_buy_signal_basic(self):
        explanation = _generate_rule_based_explanation(
            name="삼성전자",
            signal={"final_signal": "BUY", "rsi_value": 35, "disparity_value": 98,
                     "fundamental_score": 20, "weekly_trend": "bullish",
                     "confidence": 0.9, "hard_limit_triggered": False},
            macro_score=10,
            sentiment_score=0,
            market="KR",
        )
        assert "삼성전자" in explanation
        assert "매수" in explanation  # Should have buy conclusion
        assert "RSI" in explanation

    def test_sell_signal(self):
        explanation = _generate_rule_based_explanation(
            name="카카오",
            signal={"final_signal": "SELL", "rsi_value": 75, "disparity_value": 107,
                     "fundamental_score": -20, "weekly_trend": "bearish",
                     "confidence": 0.8, "hard_limit_triggered": False},
            macro_score=-10,
            sentiment_score=0,
            market="KR",
        )
        assert "카카오" in explanation
        assert "매도" in explanation

    def test_hold_signal(self):
        explanation = _generate_rule_based_explanation(
            name="NAVER",
            signal={"final_signal": "HOLD", "rsi_value": 50, "disparity_value": 100,
                     "fundamental_score": 0, "weekly_trend": "neutral",
                     "confidence": 1.0, "hard_limit_triggered": False},
            macro_score=5,
            sentiment_score=0,
            market="KR",
        )
        assert "관망" in explanation

    def test_hard_limit_override(self):
        explanation = _generate_rule_based_explanation(
            name="SK하이닉스",
            signal={"final_signal": "HOLD", "rsi_value": 70, "disparity_value": 106,
                     "fundamental_score": 10, "weekly_trend": "bullish",
                     "confidence": 1.0, "hard_limit_triggered": True,
                     "hard_limit_reason": "RSI>65"},
            macro_score=10,
            sentiment_score=0,
            market="KR",
        )
        assert "Hard Limit" in explanation

    def test_low_confidence_note(self):
        explanation = _generate_rule_based_explanation(
            name="기아",
            signal={"final_signal": "BUY", "rsi_value": 40, "disparity_value": 100,
                     "fundamental_score": 10, "weekly_trend": "neutral",
                     "confidence": 0.4, "hard_limit_triggered": False},
            macro_score=5,
            sentiment_score=0,
            market="KR",
        )
        assert "신뢰도 부족" in explanation

    def test_buy_with_negative_macro_uses_connector(self):
        """BUY in negative macro should use '에도' connector."""
        explanation = _generate_rule_based_explanation(
            name="현대차",
            signal={"final_signal": "BUY", "rsi_value": 35, "disparity_value": 98,
                     "fundamental_score": 15, "weekly_trend": "bullish",
                     "confidence": 0.9, "hard_limit_triggered": False},
            macro_score=-15,
            sentiment_score=0,
            market="KR",
        )
        assert "에도" in explanation

    def test_oversold_rsi_mention(self):
        explanation = _generate_rule_based_explanation(
            name="포스코",
            signal={"final_signal": "BUY", "rsi_value": 25, "disparity_value": 95,
                     "fundamental_score": 0, "weekly_trend": "neutral",
                     "confidence": 0.8, "hard_limit_triggered": False},
            macro_score=0,
            sentiment_score=0,
            market="KR",
        )
        assert "과매도" in explanation

    def test_overbought_rsi_mention(self):
        explanation = _generate_rule_based_explanation(
            name="LG화학",
            signal={"final_signal": "SELL", "rsi_value": 75, "disparity_value": 107,
                     "fundamental_score": 0, "weekly_trend": "neutral",
                     "confidence": 0.8, "hard_limit_triggered": False},
            macro_score=0,
            sentiment_score=0,
            market="KR",
        )
        assert "과매수" in explanation

    def test_high_fundamental_score(self):
        explanation = _generate_rule_based_explanation(
            name="삼성전자",
            signal={"final_signal": "BUY", "rsi_value": 40, "disparity_value": 100,
                     "fundamental_score": 40, "weekly_trend": "neutral",
                     "confidence": 0.9, "hard_limit_triggered": False},
            macro_score=10,
            sentiment_score=0,
            market="KR",
        )
        assert "펀더멘털 우수" in explanation

    def test_high_disparity_mention(self):
        explanation = _generate_rule_based_explanation(
            name="NVDA",
            signal={"final_signal": "HOLD", "rsi_value": 60, "disparity_value": 108,
                     "fundamental_score": 0, "weekly_trend": "neutral",
                     "confidence": 1.0, "hard_limit_triggered": False},
            macro_score=0,
            sentiment_score=0,
            market="US",
        )
        assert "이격도" in explanation
        assert "고평가" in explanation

    def test_low_disparity_mention(self):
        explanation = _generate_rule_based_explanation(
            name="삼성SDI",
            signal={"final_signal": "BUY", "rsi_value": 30, "disparity_value": 93,
                     "fundamental_score": 0, "weekly_trend": "neutral",
                     "confidence": 0.8, "hard_limit_triggered": False},
            macro_score=0,
            sentiment_score=0,
            market="KR",
        )
        assert "저평가" in explanation

    def test_bearish_weekly_trend(self):
        explanation = _generate_rule_based_explanation(
            name="카카오",
            signal={"final_signal": "SELL", "rsi_value": 55, "disparity_value": 100,
                     "fundamental_score": 0, "weekly_trend": "bearish",
                     "confidence": 0.8, "hard_limit_triggered": False},
            macro_score=0,
            sentiment_score=0,
            market="KR",
        )
        assert "하락추세" in explanation

    def test_confidence_warning_for_buy(self):
        """BUY signal with confidence < 0.7 should show warning."""
        explanation = _generate_rule_based_explanation(
            name="LG전자",
            signal={"final_signal": "BUY", "rsi_value": 40, "disparity_value": 100,
                     "fundamental_score": 10, "weekly_trend": "neutral",
                     "confidence": 0.6, "hard_limit_triggered": False},
            macro_score=5,
            sentiment_score=0,
            market="KR",
        )
        assert "확신도" in explanation
        assert "주의" in explanation

    def test_no_rsi_value(self):
        """Should handle None RSI gracefully."""
        explanation = _generate_rule_based_explanation(
            name="테스트",
            signal={"final_signal": "HOLD", "rsi_value": None, "disparity_value": None,
                     "fundamental_score": 0, "weekly_trend": "neutral",
                     "confidence": 1.0, "hard_limit_triggered": False},
            macro_score=0,
            sentiment_score=0,
            market="KR",
        )
        assert "테스트" in explanation
        # Should not crash, just produce explanation without RSI


class TestFmt:
    """Test _fmt helper."""

    def test_normal_value(self):
        assert _fmt(45.67) == "45.7"

    def test_none_value(self):
        assert _fmt(None) == "N/A"

    def test_zero_value(self):
        assert _fmt(0.0) == "0.0"
