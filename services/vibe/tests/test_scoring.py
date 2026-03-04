"""Tests for signal scoring logic (S6 core)."""

import pytest
from unittest.mock import MagicMock

from app.indicators.scoring import (
    compute_aggregate_signal,
    compute_technical_score,
    compute_fund_flow_score,
)
from app.models.enums import SignalType


class TestComputeTechnicalScore:
    """Test technical indicator scoring."""

    def test_oversold_rsi_gives_positive_score(self):
        indicators = {"rsi_14": 25}
        score = compute_technical_score(indicators)
        assert score > 0, "RSI < 30 should produce positive (bullish) score"

    def test_overbought_rsi_gives_negative_score(self):
        indicators = {"rsi_14": 75}
        score = compute_technical_score(indicators)
        assert score < 0, "RSI > 70 should produce negative (bearish) score"

    def test_neutral_rsi(self):
        indicators = {"rsi_14": 50}
        score = compute_technical_score(indicators)
        # RSI at 50 gives -5 (slightly bearish side of neutral)
        assert -10 <= score <= 10

    def test_positive_macd_histogram(self):
        indicators = {"macd_histogram": 1.5}
        score = compute_technical_score(indicators)
        assert score > 0

    def test_negative_macd_histogram(self):
        indicators = {"macd_histogram": -2.0}
        score = compute_technical_score(indicators)
        assert score < 0

    def test_bollinger_lower_band_bullish(self):
        """Close near lower band = bullish."""
        indicators = {
            "close": 100,
            "bollinger_upper": 120,
            "bollinger_lower": 90,
            "bollinger_middle": 105,
        }
        score = compute_technical_score(indicators)
        assert score > 0

    def test_bollinger_upper_band_bearish(self):
        """Close near upper band = bearish."""
        indicators = {
            "close": 118,
            "bollinger_upper": 120,
            "bollinger_lower": 90,
            "bollinger_middle": 105,
        }
        score = compute_technical_score(indicators)
        assert score < 0

    def test_high_volume_ratio_bullish(self):
        indicators = {"volume_ratio": 2.5}
        score = compute_technical_score(indicators)
        assert score > 0

    def test_empty_indicators_returns_zero(self):
        score = compute_technical_score({})
        assert score == 0.0

    def test_score_bounded_minus100_to_100(self):
        # Extreme values
        indicators = {
            "rsi_14": 10,
            "macd_histogram": 5.0,
            "close": 80,
            "bollinger_upper": 120,
            "bollinger_lower": 90,
            "bollinger_middle": 105,
            "volume_ratio": 3.0,
        }
        score = compute_technical_score(indicators)
        assert -100 <= score <= 100

    def test_disparity_overextended_bearish(self):
        """High disparity (above MA20) = bearish."""
        indicators = {"disparity_20": 108}
        score = compute_technical_score(indicators)
        assert score < 0


class TestComputeAggregateSignal:
    """Test weighted signal aggregation."""

    def _make_config(self, **overrides):
        """Create a mock config with default weights."""
        config = MagicMock()
        config.WEIGHT_TECHNICAL = overrides.get("wt", 0.35)
        config.WEIGHT_MACRO = overrides.get("wm", 0.20)
        config.WEIGHT_FUND_FLOW = overrides.get("wf", 0.25)
        config.WEIGHT_FUNDAMENTAL = overrides.get("wfund", 0.20)
        config.WEIGHT_SENTIMENT = overrides.get("ws", 0.10)
        config.WEIGHT_NEWS = overrides.get("wn", 0.0)
        config.SIGNAL_BUY_THRESHOLD = overrides.get("buy_th", 15.0)
        config.SIGNAL_SELL_THRESHOLD = overrides.get("sell_th", -15.0)
        return config

    def test_strong_buy_signal(self):
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=80,
            macro_score=50,
            fund_flow_score=None,
            market="KR",
            config=config,
            fundamental_score=40,
        )
        assert signal == SignalType.BUY
        assert score > 15

    def test_strong_sell_signal(self):
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=-80,
            macro_score=-50,
            fund_flow_score=None,
            market="KR",
            config=config,
            fundamental_score=-40,
        )
        assert signal == SignalType.SELL
        assert score < -15

    def test_neutral_returns_hold(self):
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=5,
            macro_score=0,
            fund_flow_score=None,
            market="KR",
            config=config,
        )
        assert signal == SignalType.HOLD

    def test_fund_flow_weight_redistribution_us(self):
        """US market should redistribute fund_flow weight."""
        config = self._make_config()
        signal_with, score_with = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=None,
            market="US",
            config=config,
        )
        # Technical weight should be higher for US (redistributed)
        # Score should not be zero just because fund_flow is None
        assert score_with != 0

    def test_fund_flow_zero_triggers_redistribution(self):
        """Fund flow score of 0.0 should trigger redistribution."""
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=0.0,
            market="KR",
            config=config,
        )
        # With redistribution, score should be higher than without
        assert score > 0

    def test_kr_with_fund_flow_uses_direct_weights(self):
        """KR with actual fund flow data uses config weights directly."""
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=40.0,
            market="KR",
            config=config,
        )
        assert score > 0

    def test_timeframe_multiplier_amplifies(self):
        config = self._make_config()
        _, score_1x = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            timeframe_multiplier=1.0,
        )
        _, score_1_2x = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            timeframe_multiplier=1.2,
        )
        assert abs(score_1_2x) > abs(score_1x)

    def test_sentiment_contributes_to_score(self):
        config = self._make_config(ws=0.10)
        _, score_no_sent = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            sentiment_score=0.0,
        )
        _, score_with_sent = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            sentiment_score=50.0,
        )
        assert score_with_sent > score_no_sent

    def test_news_contributes_when_weighted(self):
        config = self._make_config(wn=0.05)
        _, score_no_news = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            news_score=0.0,
        )
        _, score_with_news = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            news_score=80.0,
        )
        assert score_with_news > score_no_news


class TestComputeFundFlowScore:
    """Test fund flow scoring."""

    def test_foreign_buying_positive(self):
        score = compute_fund_flow_score({"foreign_net_buy": 5e9})
        assert score > 0

    def test_foreign_selling_negative(self):
        score = compute_fund_flow_score({"foreign_net_buy": -5e9})
        assert score < 0

    def test_empty_data_returns_zero(self):
        score = compute_fund_flow_score({})
        assert score == 0.0

    def test_score_bounded(self):
        score = compute_fund_flow_score({
            "foreign_net_buy": 100e9,
            "institution_net_buy": 100e9,
        })
        assert -100 <= score <= 100
