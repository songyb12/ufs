"""Tests for app.pipeline.stages.s6_signal_generation — signal gen logic."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models.enums import SignalType
from app.pipeline.stages.s6_signal_generation import SignalGenerationStage, _build_rationale


# ── Helper: Mock classes ──


class MockConfig:
    """Minimal config for signal generation."""
    SIGNAL_BUY_THRESHOLD = 15
    SIGNAL_SELL_THRESHOLD = -15
    WEIGHT_TECHNICAL = 0.4
    WEIGHT_MACRO = 0.3
    WEIGHT_FUND_FLOW = 0.2
    WEIGHT_FUNDAMENTAL = 0.1
    WEIGHT_SENTIMENT = 0.05
    WEIGHT_NEWS = 0.05
    RSI_HARD_LIMIT = 65
    RSI_BUY_BLOCK_KR = 50
    RSI_BUY_BLOCK_US = 55
    DISPARITY_HARD_LIMIT = 105


class MockStageResult:
    def __init__(self, data=None, status="success"):
        self.data = data or {}
        self.status = status


# ── validate_input ──


class TestValidateInput:
    def setup_method(self):
        self.stage = SignalGenerationStage(MockConfig())

    def test_valid_context(self):
        ctx = {
            "s2_technical_analysis": MockStageResult(),
            "s5_hard_limit": MockStageResult(),
        }
        assert self.stage.validate_input(ctx) is True

    def test_missing_s2(self):
        ctx = {"s5_hard_limit": MockStageResult()}
        assert self.stage.validate_input(ctx) is False

    def test_missing_s5(self):
        ctx = {"s2_technical_analysis": MockStageResult()}
        assert self.stage.validate_input(ctx) is False

    def test_empty_context(self):
        assert self.stage.validate_input({}) is False


class TestStageName:
    def test_name(self):
        stage = SignalGenerationStage(MockConfig())
        assert stage.name == "s6_signal_generation"


# ── _build_rationale ──


class TestBuildRationale:
    def test_basic_rationale(self):
        r = _build_rationale(
            "005930", SignalType.BUY, SignalType.BUY,
            tech_score=25.0, macro_score=10.0,
            ff_score=None, fund_score=0.0,
            news_score=0.0, weekly_trend="neutral",
            tf_multiplier=1.0, hard_limit={},
        )
        assert "Tech=+25.0" in r
        assert "Macro=+10.0" in r
        assert "FundFlow" not in r  # None ff_score omitted

    def test_with_fund_flow(self):
        r = _build_rationale(
            "005930", SignalType.BUY, SignalType.BUY,
            tech_score=20.0, macro_score=5.0,
            ff_score=15.0, fund_score=0.0,
            news_score=0.0, weekly_trend="neutral",
            tf_multiplier=1.0, hard_limit={},
        )
        assert "FundFlow=+15.0" in r

    def test_with_news_score(self):
        r = _build_rationale(
            "005930", SignalType.BUY, SignalType.BUY,
            tech_score=20.0, macro_score=5.0,
            ff_score=None, fund_score=0.0,
            news_score=8.0, weekly_trend="neutral",
            tf_multiplier=1.0, hard_limit={},
        )
        assert "News=+8.0" in r

    def test_with_weekly_trend(self):
        r = _build_rationale(
            "005930", SignalType.BUY, SignalType.BUY,
            tech_score=20.0, macro_score=5.0,
            ff_score=None, fund_score=0.0,
            news_score=0.0, weekly_trend="bullish",
            tf_multiplier=1.2, hard_limit={},
        )
        assert "WkTrend=bullish" in r
        assert "1.2" in r

    def test_hard_limit_triggered(self):
        r = _build_rationale(
            "005930", SignalType.BUY, SignalType.HOLD,
            tech_score=30.0, macro_score=15.0,
            ff_score=None, fund_score=0.0,
            news_score=0.0, weekly_trend="neutral",
            tf_multiplier=1.0,
            hard_limit={"hard_limit_triggered": True, "hard_limit_reason": "RSI > 65"},
        )
        assert "HARD LIMIT" in r
        assert "RSI > 65" in r
        assert "BUY->HOLD" in r

    def test_sector_adjustment(self):
        r = _build_rationale(
            "005930", SignalType.BUY, SignalType.BUY,
            tech_score=20.0, macro_score=10.0,
            ff_score=None, fund_score=0.0,
            news_score=0.0, weekly_trend="neutral",
            tf_multiplier=1.0, hard_limit={},
            sector_adj={"adjustment_score": 5.0, "sector": "반도체"},
        )
        assert "SectorAdj=+5.0" in r
        assert "반도체" in r

    def test_zero_sector_adjustment_omitted(self):
        r = _build_rationale(
            "005930", SignalType.HOLD, SignalType.HOLD,
            tech_score=5.0, macro_score=2.0,
            ff_score=None, fund_score=0.0,
            news_score=0.0, weekly_trend="neutral",
            tf_multiplier=1.0, hard_limit={},
            sector_adj={"adjustment_score": 0, "sector": "반도체"},
        )
        assert "SectorAdj" not in r

    def test_fundamental_score(self):
        r = _build_rationale(
            "005930", SignalType.BUY, SignalType.BUY,
            tech_score=20.0, macro_score=10.0,
            ff_score=None, fund_score=12.0,
            news_score=0.0, weekly_trend="neutral",
            tf_multiplier=1.0, hard_limit={},
        )
        assert "Fund=+12.0" in r

    def test_all_components(self):
        r = _build_rationale(
            "005930", SignalType.BUY, SignalType.HOLD,
            tech_score=25.0, macro_score=15.0,
            ff_score=10.0, fund_score=8.0,
            news_score=5.0, weekly_trend="bullish",
            tf_multiplier=1.1,
            hard_limit={"hard_limit_triggered": True, "hard_limit_reason": "RSI > 65"},
            sector_adj={"adjustment_score": 3.0, "sector": "반도체"},
        )
        assert "Tech=+25.0" in r
        assert "Macro=+15.0" in r
        assert "SectorAdj=+3.0" in r
        assert "FundFlow=+10.0" in r
        assert "Fund=+8.0" in r
        assert "News=+5.0" in r
        assert "WkTrend=bullish" in r
        assert "HARD LIMIT" in r
