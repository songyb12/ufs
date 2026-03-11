"""Tests for Structured Output (tool_use) in pipeline stages S7/S8/S9.

Uses mocked Anthropic API to verify tool_use request format and response handling.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.pipeline.stages.s7_red_team import LLMRedTeamStage
from app.pipeline.stages.s8_explanation import SignalExplanationStage
from app.pipeline.stages.s9_portfolio_scenarios import PortfolioScenarioStage


def _make_config(**overrides):
    config = MagicMock()
    config.LLM_API_KEY = "test-key"
    config.LLM_MODEL = "claude-3-5-haiku-20241022"
    config.LLM_EXPLANATION_MODEL = None
    config.LLM_PROVIDER = "anthropic"
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


def _mock_anthropic_module(mock_client):
    """Create a mock anthropic module with AsyncAnthropic returning mock_client."""
    mock_module = MagicMock()
    mock_module.AsyncAnthropic.return_value = mock_client
    return mock_module


# ── S7 Red-Team Structured Output ──


class TestS7StructuredOutput:
    """Verify S7 _call_anthropic uses tool_use correctly."""

    @pytest.mark.asyncio
    async def test_sends_tool_use_request(self):
        """Verify the API call includes tools and tool_choice."""
        config = _make_config()
        stage = LLMRedTeamStage(config)

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = {
            "concern_level": "MEDIUM",
            "risk_flags": ["RSI approaching overbought", "VIX elevated"],
            "reasoning": "Technical indicators suggest caution",
            "recommended_action": "MAINTAIN",
        }

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_mod = _mock_anthropic_module(mock_client)
        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = await stage._call_anthropic("Test prompt")

        assert result is not None
        assert result["concern_level"] == "MEDIUM"
        assert len(result["risk_flags"]) == 2
        assert result["recommended_action"] == "MAINTAIN"

        # Verify tool_use was requested
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["name"] == "red_team_result"
        assert call_kwargs["tool_choice"] == {"type": "tool", "name": "red_team_result"}

    @pytest.mark.asyncio
    async def test_handles_no_tool_block(self):
        """Fallback when response has no tool_use block."""
        config = _make_config()
        stage = LLMRedTeamStage(config)

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Some text response"

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_mod = _mock_anthropic_module(mock_client)
        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = await stage._call_anthropic("Test prompt")

        assert result is not None
        assert result["concern_level"] == "LOW"

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        """Returns None on API failure."""
        config = _make_config()
        stage = LLMRedTeamStage(config)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))

        mock_mod = _mock_anthropic_module(mock_client)
        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = await stage._call_anthropic("Test prompt")

        assert result is None


# ── S8 Explanation Structured Output ──


class TestS8StructuredOutput:
    """Verify S8 _call_anthropic uses tool_use with array schema."""

    @pytest.mark.asyncio
    async def test_returns_dict_from_array(self):
        """Verify array response is converted to {symbol: explanation} dict."""
        config = _make_config()
        stage = SignalExplanationStage(config)

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = {
            "explanations": [
                {"symbol": "005930", "explanation": "삼성전자 매수 유효"},
                {"symbol": "AAPL", "explanation": "애플 관망 추천"},
            ]
        }

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_mod = _mock_anthropic_module(mock_client)
        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = await stage._call_anthropic("Test prompt")

        assert result == {"005930": "삼성전자 매수 유효", "AAPL": "애플 관망 추천"}

    @pytest.mark.asyncio
    async def test_tool_schema_has_signal_explanations(self):
        """Verify correct tool name in request."""
        config = _make_config()
        stage = SignalExplanationStage(config)

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = {"explanations": []}

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_mod = _mock_anthropic_module(mock_client)
        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            await stage._call_anthropic("Test prompt")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["tools"][0]["name"] == "signal_explanations"
        assert call_kwargs["tool_choice"]["name"] == "signal_explanations"


# ── S9 Scenario Structured Output ──


class TestS9StructuredOutput:
    """Verify S9 _call_anthropic uses tool_use with held/entry schema."""

    @pytest.mark.asyncio
    async def test_returns_held_entry_dicts(self):
        """Verify held/entry arrays are converted to dicts."""
        config = _make_config()
        stage = PortfolioScenarioStage(config)

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = {
            "held": [
                {"symbol": "005930", "scenario": "삼성전자 보유 유지"},
            ],
            "entry": [
                {"symbol": "035420", "scenario": "NAVER 신규 진입 검토"},
            ],
        }

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_mod = _mock_anthropic_module(mock_client)
        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = await stage._call_anthropic("Test prompt")

        assert result["held"]["005930"] == "삼성전자 보유 유지"
        assert result["entry"]["035420"] == "NAVER 신규 진입 검토"

    @pytest.mark.asyncio
    async def test_tool_schema_has_portfolio_scenarios(self):
        """Verify correct tool name."""
        config = _make_config()
        stage = PortfolioScenarioStage(config)

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = {"held": [], "entry": []}

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_mod = _mock_anthropic_module(mock_client)
        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            await stage._call_anthropic("Test prompt")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["tools"][0]["name"] == "portfolio_scenarios"
