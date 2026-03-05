"""Tests for Stage 7 Red-Team validation (rule-based path)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.pipeline.base import StageResult
from app.pipeline.stages.s7_red_team import LLMRedTeamStage
from app.models.enums import SignalType


def _make_config(**overrides):
    config = MagicMock()
    config.RED_TEAM_ENABLED = True
    config.LLM_RED_TEAM_ENABLED = False
    config.LLM_API_KEY = ""
    config.LLM_MODEL = "claude-3-5-haiku-20241022"
    config.LLM_PROVIDER = "anthropic"
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


def _make_signal(final_signal="BUY", rsi=45, disparity=100, macro_score=0, raw_score=20):
    return {
        "symbol": "005930",
        "final_signal": final_signal,
        "rsi_value": rsi,
        "disparity_value": disparity,
        "macro_score": macro_score,
        "raw_score": raw_score,
        "technical_score": 30,
        "fundamental_score": 10,
        "weekly_trend": "neutral",
    }


def _make_context(signals, vix=None, sentiment_score=0):
    s6 = StageResult(
        stage_name="s6_signal_generation",
        status="success",
        data={"per_symbol": signals},
    )
    macro = StageResult(
        stage_name="s3_macro_analysis",
        status="success",
        data={"raw_data": {"vix": vix}} if vix is not None else {},
    )
    sentiment = StageResult(
        stage_name="s3b_sentiment_analysis",
        status="success",
        data={"sentiment_score": sentiment_score},
    )
    return {
        "s6_signal_generation": s6,
        "s3_macro_analysis": macro,
        "s3b_sentiment_analysis": sentiment,
    }


class TestRedTeamRuleBased:
    """Test rule-based adversarial checks."""

    @pytest.mark.asyncio
    async def test_buy_no_warnings_high_confidence(self):
        """BUY with safe values should pass through with high confidence."""
        signals = {"005930": _make_signal(rsi=40, disparity=99)}
        context = _make_context(signals, vix=15)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert sym["final_signal"] == SignalType.BUY
        assert sym["confidence"] == 1.0
        assert sym["red_team_warning"] is None

    @pytest.mark.asyncio
    async def test_buy_high_rsi_warning(self):
        """RSI > 55 should trigger warning for BUY."""
        signals = {"005930": _make_signal(rsi=60)}
        context = _make_context(signals, vix=15)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert sym["confidence"] < 1.0
        assert "RSI" in sym["red_team_warning"]

    @pytest.mark.asyncio
    async def test_buy_high_vix_warning(self):
        """VIX > 25 should trigger warning for BUY."""
        signals = {"005930": _make_signal(rsi=40)}
        context = _make_context(signals, vix=30)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert sym["confidence"] < 1.0
        assert "VIX" in sym["red_team_warning"]

    @pytest.mark.asyncio
    async def test_buy_negative_macro_warning(self):
        """Macro score < -20 should trigger warning."""
        signals = {"005930": _make_signal(macro_score=-25)}
        context = _make_context(signals, vix=15)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert "Macro" in sym["red_team_warning"]

    @pytest.mark.asyncio
    async def test_buy_high_disparity_warning(self):
        """Disparity > 103 should trigger warning."""
        signals = {"005930": _make_signal(disparity=105)}
        context = _make_context(signals, vix=15)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert "Disparity" in sym["red_team_warning"]

    @pytest.mark.asyncio
    async def test_buy_extreme_greed_sentiment(self):
        """Extreme greed (sentiment < -30) should trigger warning."""
        signals = {"005930": _make_signal(rsi=40)}
        context = _make_context(signals, vix=15, sentiment_score=-40)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert "Sentiment" in sym["red_team_warning"]

    @pytest.mark.asyncio
    async def test_buy_downgraded_to_hold_low_confidence(self):
        """Multiple warnings should drop confidence below 0.5 and downgrade to HOLD."""
        signals = {"005930": _make_signal(rsi=60, disparity=105, macro_score=-25)}
        context = _make_context(signals, vix=30, sentiment_score=-40)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert sym["final_signal"] == SignalType.HOLD
        assert sym["confidence"] < 0.5
        assert "downgraded" in sym["red_team_warning"].lower()

    @pytest.mark.asyncio
    async def test_sell_oversold_bounce_warning(self):
        """SELL with RSI < 25 should get oversold bounce warning."""
        signals = {"005930": _make_signal(final_signal="SELL", rsi=20)}
        context = _make_context(signals, vix=15)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert "oversold" in sym["red_team_warning"].lower()

    @pytest.mark.asyncio
    async def test_sell_extreme_vix_warning(self):
        """SELL with VIX > 35 should get capitulation warning."""
        signals = {"005930": _make_signal(final_signal="SELL", rsi=40)}
        context = _make_context(signals, vix=40)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert "capitulation" in sym["red_team_warning"].lower()

    @pytest.mark.asyncio
    async def test_hold_no_warnings(self):
        """HOLD signal should pass through without warnings."""
        signals = {"005930": _make_signal(final_signal="HOLD", rsi=50)}
        context = _make_context(signals, vix=15)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert sym["final_signal"] == SignalType.HOLD
        assert sym["red_team_warning"] is None

    @pytest.mark.asyncio
    async def test_confidence_floor_at_0_1(self):
        """Confidence should never go below 0.1."""
        signals = {"005930": _make_signal(rsi=60, disparity=110, macro_score=-30)}
        context = _make_context(signals, vix=40, sentiment_score=-50)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")
        sym = result.data["per_symbol"]["005930"]

        assert sym["confidence"] >= 0.1

    @pytest.mark.asyncio
    async def test_disabled_returns_skipped(self):
        """Disabled Red-Team should return skipped."""
        config = _make_config(RED_TEAM_ENABLED=False)
        stage = LLMRedTeamStage(config)
        context = _make_context({"005930": _make_signal()})

        result = await stage.execute(context, "KR")

        assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_multiple_symbols(self):
        """Should process all symbols independently."""
        signals = {
            "005930": _make_signal(rsi=60),  # Warning
            "000660": _make_signal(rsi=40, disparity=100),  # No warning
        }
        context = _make_context(signals, vix=15)
        stage = LLMRedTeamStage(_make_config())

        result = await stage.execute(context, "KR")

        assert "005930" in result.data["per_symbol"]
        assert "000660" in result.data["per_symbol"]
        assert result.data["per_symbol"]["005930"]["red_team_warning"] is not None
        assert result.data["per_symbol"]["000660"]["red_team_warning"] is None

    def test_validate_input_requires_s6(self):
        stage = LLMRedTeamStage(_make_config())
        assert stage.validate_input({"s6_signal_generation": "data"}) is True
        assert stage.validate_input({}) is False

    def test_stage_name(self):
        stage = LLMRedTeamStage(_make_config())
        assert stage.name == "s7_red_team"
