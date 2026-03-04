"""Tests for Hard Limit stage (S5) - critical safety mechanism."""

import pytest
from unittest.mock import MagicMock

from app.pipeline.stages.s5_hard_limit import HardLimitStage
from app.pipeline.base import StageResult


class TestHardLimitStage:
    """Test Hard Limit enforcement logic."""

    def _make_config(self, **overrides):
        config = MagicMock()
        config.RSI_HARD_LIMIT = overrides.get("rsi_hard", 65.0)
        config.RSI_BUY_THRESHOLD_KR = overrides.get("rsi_buy_kr", 45.0)
        config.RSI_BUY_THRESHOLD_US = overrides.get("rsi_buy_us", 50.0)
        config.DISPARITY_HARD_LIMIT = overrides.get("disp_hard", 105.0)
        return config

    def _make_context(self, symbol: str, rsi: float, disparity: float = 100.0):
        return {
            "s2_technical_analysis": StageResult(
                stage_name="s2",
                status="success",
                data={
                    "per_symbol": {
                        symbol: {
                            "rsi_14": rsi,
                            "disparity_20": disparity,
                        }
                    }
                },
            ),
        }

    @pytest.mark.asyncio
    async def test_rsi_above_hard_limit_triggers(self):
        """RSI > 65 must trigger hard limit."""
        config = self._make_config()
        stage = HardLimitStage(config)
        context = self._make_context("005930", rsi=68.0)

        result = await stage.execute(context, "KR")

        overrides = result.data["overrides"]
        assert "005930" in overrides
        assert overrides["005930"]["hard_limit_triggered"] is True
        assert "RSI" in overrides["005930"]["hard_limit_reason"]

    @pytest.mark.asyncio
    async def test_rsi_below_all_thresholds_no_trigger(self):
        """RSI below both hard limit and buy threshold should not trigger."""
        config = self._make_config()
        stage = HardLimitStage(config)
        # RSI=35 is below hard limit (65) AND below buy threshold (45)
        context = self._make_context("005930", rsi=35.0)

        result = await stage.execute(context, "KR")

        overrides = result.data["overrides"]
        if "005930" in overrides:
            assert overrides["005930"]["hard_limit_triggered"] is False

    @pytest.mark.asyncio
    async def test_disparity_above_limit_triggers(self):
        """Disparity > 105% must trigger hard limit."""
        config = self._make_config()
        stage = HardLimitStage(config)
        context = self._make_context("005930", rsi=40.0, disparity=108.0)

        result = await stage.execute(context, "KR")

        overrides = result.data["overrides"]
        assert "005930" in overrides
        assert overrides["005930"]["hard_limit_triggered"] is True

    @pytest.mark.asyncio
    async def test_rsi_buy_threshold_kr(self):
        """RSI above KR buy threshold should block buy."""
        config = self._make_config(rsi_buy_kr=45.0)
        stage = HardLimitStage(config)
        context = self._make_context("005930", rsi=48.0)

        result = await stage.execute(context, "KR")

        overrides = result.data["overrides"]
        assert "005930" in overrides
        assert overrides["005930"]["hard_limit_triggered"] is True

    @pytest.mark.asyncio
    async def test_rsi_buy_threshold_us(self):
        """RSI above US buy threshold should block buy."""
        config = self._make_config(rsi_buy_us=50.0)
        stage = HardLimitStage(config)
        context = self._make_context("AAPL", rsi=52.0)

        result = await stage.execute(context, "US")

        overrides = result.data["overrides"]
        assert "AAPL" in overrides
        assert overrides["AAPL"]["hard_limit_triggered"] is True

    @pytest.mark.asyncio
    async def test_low_rsi_passes_all_checks(self):
        """Low RSI and normal disparity should pass all checks."""
        config = self._make_config()
        stage = HardLimitStage(config)
        context = self._make_context("005930", rsi=30.0, disparity=98.0)

        result = await stage.execute(context, "KR")

        overrides = result.data["overrides"]
        if "005930" in overrides:
            assert overrides["005930"]["hard_limit_triggered"] is False

    @pytest.mark.asyncio
    async def test_multiple_symbols(self):
        """Test with multiple symbols - some trigger, some don't."""
        config = self._make_config()
        stage = HardLimitStage(config)
        context = {
            "s2_technical_analysis": StageResult(
                stage_name="s2",
                status="success",
                data={
                    "per_symbol": {
                        "005930": {"rsi_14": 70.0, "disparity_20": 100.0},
                        "000660": {"rsi_14": 30.0, "disparity_20": 98.0},
                        "035420": {"rsi_14": 40.0, "disparity_20": 110.0},
                    }
                },
            ),
        }

        result = await stage.execute(context, "KR")
        overrides = result.data["overrides"]

        # 005930: RSI 70 > 65 → hard limit
        assert overrides["005930"]["hard_limit_triggered"] is True
        # 035420: disparity 110 > 105 → hard limit
        assert overrides["035420"]["hard_limit_triggered"] is True
