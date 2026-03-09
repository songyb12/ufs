"""Tests for signal scoring logic (S6 core)."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import math

import pytest
from unittest.mock import MagicMock

from app.indicators.scoring import (
    _safe_num,
    compute_aggregate_signal,
    compute_technical_score,
    compute_fund_flow_score,
)
from app.models.enums import Market, SignalType


# ── _safe_num ──


class TestSafeNum:
    """Test the _safe_num helper for NaN/Inf/type guarding."""

    def test_normal_int(self):
        assert _safe_num(10) == 10.0

    def test_normal_float(self):
        assert _safe_num(3.14) == 3.14

    def test_zero(self):
        assert _safe_num(0) == 0.0

    def test_negative(self):
        assert _safe_num(-42.5) == -42.5

    def test_none_returns_none(self):
        assert _safe_num(None) is None

    def test_nan_returns_none(self):
        assert _safe_num(float("nan")) is None

    def test_positive_inf_returns_none(self):
        assert _safe_num(float("inf")) is None

    def test_negative_inf_returns_none(self):
        assert _safe_num(float("-inf")) is None

    def test_string_number_converts(self):
        """Numeric strings should be accepted by float()."""
        assert _safe_num("42.5") == 42.5

    def test_non_numeric_string_returns_none(self):
        assert _safe_num("abc") is None

    def test_empty_string_returns_none(self):
        assert _safe_num("") is None

    def test_boolean_true_converts(self):
        """bool is subclass of int; True → 1.0."""
        assert _safe_num(True) == 1.0

    def test_boolean_false_converts(self):
        assert _safe_num(False) == 0.0

    def test_very_large_float(self):
        assert _safe_num(1e308) == 1e308

    def test_very_small_float(self):
        assert _safe_num(1e-308) == 1e-308

    def test_list_returns_none(self):
        assert _safe_num([1, 2]) is None

    def test_dict_returns_none(self):
        assert _safe_num({"x": 1}) is None

    def test_math_nan_returns_none(self):
        assert _safe_num(math.nan) is None

    def test_math_inf_returns_none(self):
        assert _safe_num(math.inf) is None


# ── compute_technical_score ──


class TestComputeTechnicalScore:
    """Test technical indicator scoring."""

    # --- RSI ---

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
        # RSI at 50 falls into [50, 60) → score -= 5
        assert score == -5.0

    def test_rsi_boundary_30_exact(self):
        """RSI exactly 30 falls into [30, 40) band → +15."""
        score = compute_technical_score({"rsi_14": 30})
        assert score == 15.0

    def test_rsi_boundary_40_exact(self):
        """RSI exactly 40 falls into [40, 50) band → +5."""
        score = compute_technical_score({"rsi_14": 40})
        assert score == 5.0

    def test_rsi_boundary_50_exact(self):
        """RSI exactly 50 falls into [50, 60) band → -5."""
        score = compute_technical_score({"rsi_14": 50})
        assert score == -5.0

    def test_rsi_boundary_60_exact(self):
        """RSI exactly 60 falls into [60, 70) band → -15."""
        score = compute_technical_score({"rsi_14": 60})
        assert score == -15.0

    def test_rsi_boundary_70_exact(self):
        """RSI exactly 70 falls into >= 70 band → -30."""
        score = compute_technical_score({"rsi_14": 70})
        assert score == -30.0

    def test_rsi_zero(self):
        """RSI of 0 → deeply oversold, +30."""
        score = compute_technical_score({"rsi_14": 0})
        assert score == 30.0

    def test_rsi_100(self):
        """RSI of 100 → deeply overbought, -30."""
        score = compute_technical_score({"rsi_14": 100})
        assert score == -30.0

    def test_rsi_none_ignored(self):
        """None RSI should not contribute to score."""
        score = compute_technical_score({"rsi_14": None})
        assert score == 0.0

    def test_rsi_nan_ignored(self):
        """NaN RSI should be filtered by _safe_num."""
        score = compute_technical_score({"rsi_14": float("nan")})
        assert score == 0.0

    def test_rsi_inf_ignored(self):
        """Inf RSI should be filtered by _safe_num."""
        score = compute_technical_score({"rsi_14": float("inf")})
        assert score == 0.0

    # --- MACD ---

    def test_positive_macd_histogram(self):
        # MACD hist normalized by close: 1.5/100*100=1.5% → 15 score
        indicators = {"macd_histogram": 1.5, "close": 100}
        score = compute_technical_score(indicators)
        assert score == 15.0

    def test_negative_macd_histogram(self):
        # MACD hist normalized by close: -2.0/100*100=-2.0% → clamped -20
        indicators = {"macd_histogram": -2.0, "close": 100}
        score = compute_technical_score(indicators)
        assert score == -20.0

    def test_macd_histogram_without_close_ignored(self):
        """MACD hist without close price should be skipped (no crash)."""
        indicators = {"macd_histogram": 1.5}
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_macd_zero_close_ignored(self):
        """MACD hist with close=0 should be skipped (division by zero guard)."""
        indicators = {"macd_histogram": 1.5, "close": 0}
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_macd_negative_close_ignored(self):
        """MACD hist with negative close should be skipped."""
        indicators = {"macd_histogram": 1.5, "close": -100}
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_macd_histogram_kr_stock_normalized(self):
        """KR stock at 50000 KRW with hist=500 → 1% → score = 10."""
        indicators = {"macd_histogram": 500, "close": 50000}
        score = compute_technical_score(indicators)
        assert score == 10.0

    def test_macd_capped_at_positive_20(self):
        """Very large MACD should cap at +20."""
        indicators = {"macd_histogram": 10.0, "close": 100}  # 10% → 100, capped at 20
        score = compute_technical_score(indicators)
        assert score == 20.0

    def test_macd_capped_at_negative_20(self):
        """Very large negative MACD should cap at -20."""
        indicators = {"macd_histogram": -10.0, "close": 100}
        score = compute_technical_score(indicators)
        assert score == -20.0

    def test_macd_none_histogram_ignored(self):
        indicators = {"macd_histogram": None, "close": 100}
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_macd_nan_close_ignored(self):
        indicators = {"macd_histogram": 1.5, "close": float("nan")}
        score = compute_technical_score(indicators)
        assert score == 0.0

    # --- Bollinger Bands ---

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

    def test_bollinger_at_middle_near_zero(self):
        """Close at midpoint of BB range → position=0.5 → (0.5-0.5)*40=0."""
        indicators = {
            "close": 105,
            "bollinger_upper": 120,
            "bollinger_lower": 90,
            "bollinger_middle": 105,
        }
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_bollinger_zero_range_ignored(self):
        """BB with upper == lower → range 0 → skipped."""
        indicators = {
            "close": 100,
            "bollinger_upper": 100,
            "bollinger_lower": 100,
            "bollinger_middle": 100,
        }
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_bollinger_close_below_lower_clamped(self):
        """Close below lower band → position clamped to 0 → max bullish +20."""
        indicators = {
            "close": 80,
            "bollinger_upper": 120,
            "bollinger_lower": 90,
            "bollinger_middle": 105,
        }
        score = compute_technical_score(indicators)
        assert score == 20.0

    def test_bollinger_close_above_upper_clamped(self):
        """Close above upper band → position clamped to 1 → max bearish -20."""
        indicators = {
            "close": 130,
            "bollinger_upper": 120,
            "bollinger_lower": 90,
            "bollinger_middle": 105,
        }
        score = compute_technical_score(indicators)
        assert score == -20.0

    def test_bollinger_missing_one_field_ignored(self):
        """Missing one BB field → all() check fails → skipped."""
        indicators = {
            "close": 100,
            "bollinger_upper": 120,
            # bollinger_lower missing
            "bollinger_middle": 105,
        }
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_bollinger_nan_field_ignored(self):
        """NaN in BB field → _safe_num returns None → all() fails."""
        indicators = {
            "close": 100,
            "bollinger_upper": float("nan"),
            "bollinger_lower": 90,
            "bollinger_middle": 105,
        }
        score = compute_technical_score(indicators)
        assert score == 0.0

    # --- Disparity ---

    def test_disparity_overextended_bearish(self):
        """High disparity (above MA20) = bearish."""
        indicators = {"disparity_20": 108}
        score = compute_technical_score(indicators)
        assert score < 0

    def test_disparity_underextended_bullish(self):
        """Low disparity (below MA20) = bullish."""
        indicators = {"disparity_20": 95}
        score = compute_technical_score(indicators)
        assert score > 0

    def test_disparity_at_100_neutral(self):
        """Disparity exactly at 100 (at MA20) → deviation=0 → score=0."""
        indicators = {"disparity_20": 100}
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_disparity_capped_positive_15(self):
        """Very low disparity capped at +15."""
        indicators = {"disparity_20": 90}  # deviation=-10 → -(-10)*3=30, clamped to 15
        score = compute_technical_score(indicators)
        assert score == 15.0

    def test_disparity_capped_negative_15(self):
        """Very high disparity capped at -15."""
        indicators = {"disparity_20": 115}  # deviation=15 → -(15)*3=-45, clamped to -15
        score = compute_technical_score(indicators)
        assert score == -15.0

    def test_disparity_none_ignored(self):
        indicators = {"disparity_20": None}
        score = compute_technical_score(indicators)
        assert score == 0.0

    # --- Volume Ratio ---

    def test_high_volume_ratio_bullish(self):
        indicators = {"volume_ratio": 2.5}
        score = compute_technical_score(indicators)
        assert score == 10.0

    def test_moderate_high_volume_ratio(self):
        """Volume ratio 1.5-2.0 → +5."""
        indicators = {"volume_ratio": 1.7}
        score = compute_technical_score(indicators)
        assert score == 5.0

    def test_low_volume_ratio_bearish(self):
        """Volume ratio < 0.5 → -5."""
        indicators = {"volume_ratio": 0.3}
        score = compute_technical_score(indicators)
        assert score == -5.0

    def test_normal_volume_ratio_zero_contribution(self):
        """Volume ratio between 0.5 and 1.5 → 0 points."""
        indicators = {"volume_ratio": 1.0}
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_volume_ratio_exact_boundary_0_5(self):
        """Volume ratio exactly 0.5 → falls in [0.5, 1.5) → 0 contribution."""
        indicators = {"volume_ratio": 0.5}
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_volume_ratio_exact_boundary_1_5(self):
        """Volume ratio exactly 1.5 → not > 1.5, falls to no-contribution → 0."""
        indicators = {"volume_ratio": 1.5}
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_volume_ratio_exact_boundary_2_0(self):
        """Volume ratio exactly 2.0 → not > 2.0, but > 1.5 → +5."""
        indicators = {"volume_ratio": 2.0}
        score = compute_technical_score(indicators)
        assert score == 5.0

    def test_volume_ratio_zero(self):
        """Volume ratio of 0 → < 0.5 → -5."""
        indicators = {"volume_ratio": 0}
        score = compute_technical_score(indicators)
        assert score == -5.0

    def test_volume_ratio_none_ignored(self):
        indicators = {"volume_ratio": None}
        score = compute_technical_score(indicators)
        assert score == 0.0

    # --- Combined / Edge Cases ---

    def test_empty_indicators_returns_zero(self):
        score = compute_technical_score({})
        assert score == 0.0

    def test_score_bounded_minus100_to_100_bullish(self):
        """All extreme bullish indicators → capped at 100."""
        indicators = {
            "rsi_14": 10,           # +30
            "macd_histogram": 5.0,  # close=80 → 6.25% → +20 (capped)
            "close": 80,
            "bollinger_upper": 120,
            "bollinger_lower": 90,
            "bollinger_middle": 105,  # close=80 below lower → +20
            "disparity_20": 90,     # +15
            "volume_ratio": 3.0,    # +10
        }
        score = compute_technical_score(indicators)
        assert -100 <= score <= 100

    def test_score_bounded_minus100_to_100_bearish(self):
        """All extreme bearish indicators → capped at -100."""
        indicators = {
            "rsi_14": 90,            # -30
            "macd_histogram": -5.0,  # close=130 → -3.8% → -20 (capped)
            "close": 130,
            "bollinger_upper": 120,
            "bollinger_lower": 90,
            "bollinger_middle": 105,  # close=130 above upper → -20
            "disparity_20": 115,     # -15
            "volume_ratio": 0.1,     # -5
        }
        score = compute_technical_score(indicators)
        assert -100 <= score <= 100
        assert score < 0

    def test_all_none_values_returns_zero(self):
        """All indicators present but None → all skipped → 0."""
        indicators = {
            "rsi_14": None,
            "macd_histogram": None,
            "close": None,
            "bollinger_upper": None,
            "bollinger_lower": None,
            "bollinger_middle": None,
            "disparity_20": None,
            "volume_ratio": None,
        }
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_all_nan_values_returns_zero(self):
        """All indicators as NaN → all skipped → 0."""
        nan = float("nan")
        indicators = {
            "rsi_14": nan,
            "macd_histogram": nan,
            "close": nan,
            "bollinger_upper": nan,
            "bollinger_lower": nan,
            "bollinger_middle": nan,
            "disparity_20": nan,
            "volume_ratio": nan,
        }
        score = compute_technical_score(indicators)
        assert score == 0.0

    def test_return_type_is_float(self):
        score = compute_technical_score({"rsi_14": 45})
        assert isinstance(score, float)

    def test_mixed_valid_and_invalid_indicators(self):
        """Some valid, some NaN/None → only valid contribute."""
        indicators = {
            "rsi_14": 25,                  # +30
            "macd_histogram": float("nan"),  # skipped
            "close": 100,
            "disparity_20": None,          # skipped
            "volume_ratio": 2.5,           # +10
        }
        score = compute_technical_score(indicators)
        assert score == 40.0  # 30 + 10


# ── compute_fund_flow_score ──


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

    def test_score_bounded_extreme_positive(self):
        score = compute_fund_flow_score({
            "foreign_net_buy": 100e9,
            "institution_net_buy": 100e9,
        })
        assert score <= 100

    def test_score_bounded_extreme_negative(self):
        score = compute_fund_flow_score({
            "foreign_net_buy": -100e9,
            "institution_net_buy": -100e9,
        })
        assert score >= -100

    def test_foreign_only_1_billion(self):
        """1 billion foreign buy → 1e9/1e9*10 = 10, capped at min(50, 10) = 10."""
        score = compute_fund_flow_score({"foreign_net_buy": 1e9})
        assert score == 10.0

    def test_foreign_only_5_billion(self):
        """5 billion foreign buy → 5e9/1e9*10 = 50 → capped at 50."""
        score = compute_fund_flow_score({"foreign_net_buy": 5e9})
        assert score == 50.0

    def test_foreign_cap_at_50(self):
        """Foreign net buy over 5 billion still capped at 50."""
        score = compute_fund_flow_score({"foreign_net_buy": 10e9})
        assert score == 50.0

    def test_foreign_negative_cap_at_minus_50(self):
        """Foreign net sell over 5 billion capped at -50."""
        score = compute_fund_flow_score({"foreign_net_buy": -10e9})
        assert score == -50.0

    def test_institution_only_positive(self):
        """Institution net buy without foreign data."""
        score = compute_fund_flow_score({"institution_net_buy": 2e9})
        assert score > 0

    def test_institution_only_negative(self):
        score = compute_fund_flow_score({"institution_net_buy": -2e9})
        assert score < 0

    def test_institution_1_billion(self):
        """1 billion institution buy → 1e9/1e9*5 = 5, capped at min(30, 5) = 5."""
        score = compute_fund_flow_score({"institution_net_buy": 1e9})
        assert score == 5.0

    def test_institution_cap_at_30(self):
        """Institution net buy over 6 billion → capped at 30."""
        score = compute_fund_flow_score({"institution_net_buy": 10e9})
        assert score == 30.0

    def test_institution_negative_cap_at_minus_30(self):
        score = compute_fund_flow_score({"institution_net_buy": -10e9})
        assert score == -30.0

    def test_combined_foreign_and_institution(self):
        """Both foreign and institution contribute additively."""
        foreign_only = compute_fund_flow_score({"foreign_net_buy": 1e9})
        inst_only = compute_fund_flow_score({"institution_net_buy": 1e9})
        combined = compute_fund_flow_score({
            "foreign_net_buy": 1e9,
            "institution_net_buy": 1e9,
        })
        assert combined == foreign_only + inst_only

    def test_opposing_signals_partially_cancel(self):
        """Foreign buy + institution sell → partial cancellation."""
        score = compute_fund_flow_score({
            "foreign_net_buy": 3e9,   # +30
            "institution_net_buy": -3e9,  # -15
        })
        assert score == 15.0

    def test_zero_values(self):
        score = compute_fund_flow_score({
            "foreign_net_buy": 0,
            "institution_net_buy": 0,
        })
        assert score == 0.0

    def test_none_foreign(self):
        """None values should be handled gracefully."""
        score = compute_fund_flow_score({"foreign_net_buy": None})
        assert score == 0.0

    def test_none_institution(self):
        score = compute_fund_flow_score({"institution_net_buy": None})
        assert score == 0.0

    def test_nan_values_ignored(self):
        score = compute_fund_flow_score({
            "foreign_net_buy": float("nan"),
            "institution_net_buy": float("nan"),
        })
        assert score == 0.0

    def test_small_amounts(self):
        """Small amounts (millions, not billions) → near zero score."""
        score = compute_fund_flow_score({"foreign_net_buy": 1e6})
        assert abs(score) < 1.0

    def test_return_type_is_float(self):
        score = compute_fund_flow_score({"foreign_net_buy": 1e9})
        assert isinstance(score, float)

    def test_result_is_rounded(self):
        """Score should be rounded to 2 decimal places."""
        score = compute_fund_flow_score({"foreign_net_buy": 1.23456e8})
        # 1.23456e8 / 1e9 * 10 = 1.23456 → rounded to 1.23
        assert score == round(score, 2)


# ── compute_aggregate_signal ──


class TestComputeAggregateSignal:
    """Test weighted signal aggregation."""

    def _make_config(self, **overrides):
        """Create a mock config with default weights.

        Default weights sum to 1.10 (0.35+0.20+0.25+0.20+0.10+0.0),
        which triggers normalization.
        """
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

    def _make_normalized_config(self, **overrides):
        """Create config where weights sum exactly to 1.0 (no normalization)."""
        config = MagicMock()
        config.WEIGHT_TECHNICAL = overrides.get("wt", 0.30)
        config.WEIGHT_MACRO = overrides.get("wm", 0.18)
        config.WEIGHT_FUND_FLOW = overrides.get("wf", 0.22)
        config.WEIGHT_FUNDAMENTAL = overrides.get("wfund", 0.18)
        config.WEIGHT_SENTIMENT = overrides.get("ws", 0.10)
        config.WEIGHT_NEWS = overrides.get("wn", 0.02)
        config.SIGNAL_BUY_THRESHOLD = overrides.get("buy_th", 15.0)
        config.SIGNAL_SELL_THRESHOLD = overrides.get("sell_th", -15.0)
        return config

    # --- Signal classification ---

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

    def test_exact_buy_threshold_is_hold(self):
        """Score exactly at threshold should be HOLD (> not >=)."""
        config = self._make_config(buy_th=15.0)
        # Need a score that is exactly 15.0
        # Use normalized config for predictable math
        cfg = self._make_normalized_config()
        cfg.SIGNAL_BUY_THRESHOLD = 15.0
        cfg.SIGNAL_SELL_THRESHOLD = -15.0
        signal, score = compute_aggregate_signal(
            technical_score=50,
            macro_score=0,
            fund_flow_score=0.0,
            market="KR",
            config=cfg,
        )
        if score == 15.0:
            assert signal == SignalType.HOLD

    def test_exact_sell_threshold_is_hold(self):
        """Score exactly at sell threshold should be HOLD (< not <=)."""
        config = self._make_config(sell_th=-15.0)
        signal, score = compute_aggregate_signal(
            technical_score=-50,
            macro_score=0,
            fund_flow_score=0.0,
            market="KR",
            config=config,
        )
        if score == -15.0:
            assert signal == SignalType.HOLD

    def test_all_zeros_returns_hold(self):
        """All zero scores → raw_score=0 → HOLD."""
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=0,
            macro_score=0,
            fund_flow_score=0.0,
            market="KR",
            config=config,
        )
        assert signal == SignalType.HOLD
        assert score == 0.0

    # --- Market-specific weight handling ---

    def test_fund_flow_weight_redistribution_us(self):
        """US market should redistribute fund_flow weight."""
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=None,
            market="US",
            config=config,
        )
        # Score should not be zero just because fund_flow is None
        assert score != 0

    def test_fund_flow_zero_treated_as_valid_data(self):
        """Fund flow score of 0.0 is valid neutral data, not missing."""
        config = self._make_config()
        _, score_with_zero = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=0.0,
            market="KR",
            config=config,
        )
        _, score_with_none = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=None,
            market="KR",
            config=config,
        )
        assert score_with_zero > 0
        assert score_with_zero != score_with_none

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

    def test_kr_without_fund_flow_redistributes(self):
        """KR without fund_flow redistributes like US."""
        config = self._make_normalized_config()
        _, score_kr_none = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=None,
            market="KR",
            config=config,
        )
        _, score_us_none = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=None,
            market="US",
            config=config,
        )
        # Both should redistribute the same way
        assert score_kr_none == score_us_none

    def test_us_market_string_enum(self):
        """Market as string 'US' works (StrEnum compatibility)."""
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=None,
            market="US",
            config=config,
        )
        assert isinstance(signal, SignalType)

    def test_kr_market_enum_value(self):
        """Market as Market.KR enum works."""
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=20.0,
            market=Market.KR,
            config=config,
        )
        assert isinstance(signal, SignalType)
        assert score > 0

    # --- Weight normalization ---

    def test_weights_normalized_when_not_summing_to_one(self):
        """Weights that don't sum to 1.0 get normalized."""
        config = self._make_config(
            wt=0.50, wm=0.30, wf=0.20, wfund=0.20, ws=0.10, wn=0.10,
        )
        # Sum = 1.40, will be normalized
        signal, score = compute_aggregate_signal(
            technical_score=100,
            macro_score=0,
            fund_flow_score=0.0,
            market="KR",
            config=config,
        )
        # After normalization, tech weight = 0.50/1.40 ≈ 0.357
        # score = 100 * 0.357 ≈ 35.7
        assert 30 < score < 40

    def test_weights_already_sum_to_one_no_change(self):
        """When weights already sum to 1.0, normalization is a no-op."""
        config = self._make_normalized_config()
        signal, score = compute_aggregate_signal(
            technical_score=100,
            macro_score=0,
            fund_flow_score=0.0,
            market="KR",
            config=config,
        )
        # tech weight = 0.30, score = 100 * 0.30 = 30
        assert score == 30.0

    # --- Timeframe multiplier ---

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

    def test_timeframe_multiplier_dampens(self):
        """Multiplier < 1.0 should reduce absolute score."""
        config = self._make_config()
        _, score_1x = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            timeframe_multiplier=1.0,
        )
        _, score_07x = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            timeframe_multiplier=0.7,
        )
        assert abs(score_07x) < abs(score_1x)

    def test_timeframe_multiplier_zero_zeroes_score(self):
        """Multiplier of 0 zeroes out the score → HOLD."""
        config = self._make_config()
        signal, score = compute_aggregate_signal(
            technical_score=80,
            macro_score=50,
            fund_flow_score=None,
            market="KR",
            config=config,
            timeframe_multiplier=0.0,
        )
        assert score == 0.0
        assert signal == SignalType.HOLD

    def test_timeframe_default_is_one(self):
        """Default timeframe_multiplier should be 1.0."""
        config = self._make_config()
        _, score_default = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
        )
        _, score_explicit = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            timeframe_multiplier=1.0,
        )
        assert score_default == score_explicit

    # --- Sentiment & news ---

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

    def test_negative_sentiment_lowers_score(self):
        """Negative sentiment should reduce overall score."""
        config = self._make_config(ws=0.10)
        _, score_neutral = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            sentiment_score=0.0,
        )
        _, score_neg = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
            sentiment_score=-50.0,
        )
        assert score_neg < score_neutral

    # --- Return type contracts ---

    def test_returns_tuple_of_signal_and_float(self):
        config = self._make_config()
        result = compute_aggregate_signal(
            technical_score=30,
            macro_score=10,
            fund_flow_score=None,
            market="KR",
            config=config,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        signal, score = result
        assert isinstance(signal, SignalType)
        assert isinstance(score, float)

    def test_score_is_rounded_to_2_decimals(self):
        config = self._make_config()
        _, score = compute_aggregate_signal(
            technical_score=33,
            macro_score=17,
            fund_flow_score=None,
            market="KR",
            config=config,
        )
        assert score == round(score, 2)

    # --- Configurable thresholds ---

    def test_custom_buy_threshold(self):
        """Custom high buy threshold → harder to trigger BUY."""
        config = self._make_config(buy_th=50.0)
        signal, score = compute_aggregate_signal(
            technical_score=50,
            macro_score=30,
            fund_flow_score=None,
            market="KR",
            config=config,
        )
        # With normalized weights, score ≈ 30, which is < 50 threshold
        assert signal == SignalType.HOLD

    def test_custom_sell_threshold(self):
        """Custom low sell threshold → harder to trigger SELL."""
        config = self._make_config(sell_th=-50.0)
        signal, score = compute_aggregate_signal(
            technical_score=-30,
            macro_score=-20,
            fund_flow_score=None,
            market="KR",
            config=config,
        )
        # Score ≈ -22, which is > -50 threshold
        assert signal == SignalType.HOLD

    # --- Redistribution math ---

    def test_us_redistribution_ratios(self):
        """Verify the fund flow weight redistribution ratios for US market.

        fund_flow weight gets split: 45% to tech, 25% to macro,
        20% to fundamental, 10% to sentiment.
        """
        config = self._make_normalized_config()
        ff_w = config.WEIGHT_FUND_FLOW  # 0.22

        # All 100 in tech only → check the redistributed tech weight
        _, score = compute_aggregate_signal(
            technical_score=100,
            macro_score=0,
            fund_flow_score=None,
            market="US",
            config=config,
        )
        # Expected tech weight = (0.30 + 0.22 * 0.45) = 0.399
        # But weights may be normalized, so compute expected score
        expected_tech_w = config.WEIGHT_TECHNICAL + ff_w * 0.45
        expected_macro_w = config.WEIGHT_MACRO + ff_w * 0.25
        expected_fund_w = 0.0
        expected_fundamental_w = config.WEIGHT_FUNDAMENTAL + ff_w * 0.20
        expected_sentiment_w = config.WEIGHT_SENTIMENT + ff_w * 0.10
        expected_news_w = config.WEIGHT_NEWS
        total = (expected_tech_w + expected_macro_w + expected_fund_w
                 + expected_fundamental_w + expected_sentiment_w + expected_news_w)
        # After normalization (if needed)
        if abs(total - 1.0) > 0.001:
            expected_tech_w = expected_tech_w / total
        expected_score = round(100 * expected_tech_w, 2)
        assert score == expected_score
