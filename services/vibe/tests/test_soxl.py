"""
Tests for SOXL dedicated dashboard router.

Covers:
- _calc_performance() — empty, single, normal, None values, volatility calc
- _build_strategy() — all stance combos, RSI ranges, MACD cross, disparity, volume, risk warnings
- GET /soxl/dashboard — integration with DB
- GET /soxl/levels — fibonacci, pivot points, edge cases
- Trading rules structure validation
"""

import math

import pytest
import pytest_asyncio

from tests.conftest import cleanup_all

from app.routers.soxl import _calc_performance, _build_strategy


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def _price(close, volume=1_000_000, date="2025-06-01", open_=None, high=None, low=None):
    """Shorthand to build a price dict."""
    return {
        "date": date,
        "open": open_ or close,
        "high": high or close,
        "low": low or close,
        "close": close,
        "volume": volume,
    }


def _prices_seq(closes, volume=1_000_000):
    """Build a list of price dicts from a sequence of close values."""
    return [
        _price(c, volume=volume, date=f"2025-01-{i + 1:02d}")
        for i, c in enumerate(closes)
    ]


def _technicals(rsi=50.0, macd=0.0, macd_signal=0.0, disparity=100.0, volume_ratio=1.0):
    """Shorthand to build a technicals dict."""
    return {
        "rsi_14": rsi,
        "ma_5": 100.0,
        "ma_20": 100.0,
        "ma_60": 100.0,
        "macd": macd,
        "macd_signal": macd_signal,
        "bb_upper": 110.0,
        "bb_middle": 100.0,
        "bb_lower": 90.0,
        "volume_ratio": volume_ratio,
        "disparity_20": disparity,
        "updated_at": "2025-06-01T00:00:00",
    }


# ════════════════════════════════════════════════════════════════
# _calc_performance  UNIT TESTS
# ════════════════════════════════════════════════════════════════


class TestCalcPerformanceEmpty:
    """Edge cases: empty, single, and insufficient data."""

    def test_empty_prices(self):
        assert _calc_performance([]) == {}

    def test_single_price(self):
        assert _calc_performance([_price(100.0)]) == {}

    def test_two_prices(self):
        prices = _prices_seq([100.0, 110.0])
        perf = _calc_performance(prices)
        assert perf != {}
        assert perf["current_price"] == 110.0
        # 1-day change: (110 - 100) / 100 = 10%
        assert perf["change_1d"] == pytest.approx(10.0, abs=0.01)

    def test_current_close_none(self):
        """If the last price has close=None, return empty."""
        prices = [_price(100.0), _price(None)]
        assert _calc_performance(prices) == {}


class TestCalcPerformanceReturns:
    """Percentage return calculations for various lookback periods."""

    def test_1d_return(self):
        prices = _prices_seq([100.0, 105.0])
        perf = _calc_performance(prices)
        assert perf["change_1d"] == pytest.approx(5.0, abs=0.01)

    def test_5d_return(self):
        closes = [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]
        prices = _prices_seq(closes)
        perf = _calc_performance(prices)
        # 5d: from prices[-(5+1)] = prices[0]=100 -> 110 = 10%
        assert perf["change_5d"] == pytest.approx(10.0, abs=0.01)

    def test_20d_return(self):
        closes = list(range(80, 102))  # 22 values, [80..101]
        prices = _prices_seq(closes)
        perf = _calc_performance(prices)
        # 20d: prices[-(20+1)] = prices[1]=81; current=101 -> (101-81)/81
        expected = round((101 - 81) / 81 * 100, 2)
        assert perf["change_20d"] == pytest.approx(expected, abs=0.01)

    def test_60d_return_insufficient_data(self):
        """If fewer than 61 prices, 60d return should be None."""
        closes = [100.0 + i for i in range(30)]
        prices = _prices_seq(closes)
        perf = _calc_performance(prices)
        assert perf["change_60d"] is None

    def test_60d_return_with_enough_data(self):
        closes = [100.0 + i * 0.5 for i in range(70)]
        prices = _prices_seq(closes)
        perf = _calc_performance(prices)
        assert perf["change_60d"] is not None

    def test_negative_return(self):
        prices = _prices_seq([100.0, 90.0])
        perf = _calc_performance(prices)
        assert perf["change_1d"] == pytest.approx(-10.0, abs=0.01)

    def test_pct_with_none_in_old_close(self):
        """If the lookback price has close=None, return None for that period."""
        prices = [_price(None, date="2025-01-01"), _price(100.0, date="2025-01-02")]
        perf = _calc_performance(prices)
        # 1d: old close is None => None
        assert perf["change_1d"] is None


class TestCalcPerformanceVolume:
    """Volume statistics."""

    def test_avg_volume_and_latest(self):
        closes = [100.0 + i for i in range(25)]
        prices = [_price(c, volume=1000 * (i + 1), date=f"2025-01-{i + 1:02d}")
                  for i, c in enumerate(closes)]
        perf = _calc_performance(prices)
        assert perf["latest_volume"] == 1000 * 25
        assert perf["avg_volume_20d"] is not None

    def test_avg_volume_with_missing_volumes(self):
        """Prices with no volume key should be skipped."""
        prices = _prices_seq([100.0, 110.0, 120.0])
        # Remove volume from one
        prices[1]["volume"] = None
        perf = _calc_performance(prices)
        assert perf["latest_volume"] is not None

    def test_no_volume_at_all(self):
        """All volumes None => avg_vol_20 is None, latest_vol is None."""
        prices = [
            {"date": "2025-01-01", "open": 100, "high": 100, "low": 100, "close": 100},
            {"date": "2025-01-02", "open": 110, "high": 110, "low": 110, "close": 110},
        ]
        perf = _calc_performance(prices)
        assert perf["avg_volume_20d"] is None
        assert perf["latest_volume"] is None


class TestCalcPerformanceVolatility:
    """Annualized 20-day volatility."""

    def test_volatility_calculated(self):
        closes = [100.0 + i for i in range(25)]
        prices = _prices_seq(closes)
        perf = _calc_performance(prices)
        assert perf["volatility_20d_ann"] is not None
        assert perf["volatility_20d_ann"] > 0

    def test_flat_prices_low_volatility(self):
        """Constant prices => zero daily returns => zero volatility."""
        closes = [100.0] * 25
        prices = _prices_seq(closes)
        perf = _calc_performance(prices)
        assert perf["volatility_20d_ann"] == pytest.approx(0.0, abs=0.01)

    def test_high_volatility(self):
        """Alternating large moves => high volatility."""
        closes = [100.0 if i % 2 == 0 else 120.0 for i in range(25)]
        prices = _prices_seq(closes)
        perf = _calc_performance(prices)
        assert perf["volatility_20d_ann"] > 100  # very high

    def test_volatility_with_none_close(self):
        """If one close is None in the last 20, it should be skipped."""
        closes = [100.0 + i for i in range(25)]
        prices = _prices_seq(closes)
        prices[10]["close"] = None
        perf = _calc_performance(prices)
        # Should still compute (skips the None pair)
        # May be None or a number — depends on whether enough returns exist
        # The function checks `if i > 0 and prices[i]["close"] and prices[i-1]["close"]`
        assert "volatility_20d_ann" in perf


# ════════════════════════════════════════════════════════════════
# _build_strategy  UNIT TESTS
# ════════════════════════════════════════════════════════════════


class TestBuildStrategyNullInputs:
    """Edge cases when technicals or perf data is missing."""

    def test_none_technicals(self):
        strategy = _build_strategy(None, {})
        assert strategy["stance"] == "HOLD"
        assert strategy["buy_signals"] == 0
        assert strategy["sell_signals"] == 0
        assert strategy["conditions"] == []

    def test_empty_technicals(self):
        strategy = _build_strategy({}, {})
        assert strategy["stance"] == "HOLD"

    def test_none_perf(self):
        tech = _technicals(rsi=25.0, macd=1.0, macd_signal=0.5, disparity=85.0)
        strategy = _build_strategy(tech, {})
        # Should still work — volatility just won't trigger risk warnings
        assert strategy["stance"] in ("STRONG_BUY", "BUY", "SELL", "STRONG_SELL", "HOLD")


class TestBuildStrategyRSI:
    """RSI-based signal classification."""

    def test_oversold_rsi_below_30(self):
        tech = _technicals(rsi=25.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "OVERSOLD"
        assert rsi_cond["value"] == 25.0
        assert strategy["buy_signals"] >= 2  # RSI oversold => +2

    def test_approaching_oversold_rsi_30_to_40(self):
        tech = _technicals(rsi=35.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "APPROACHING_OVERSOLD"
        assert strategy["buy_signals"] >= 1

    def test_overbought_rsi_above_70(self):
        tech = _technicals(rsi=75.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "OVERBOUGHT"
        assert strategy["sell_signals"] >= 2

    def test_approaching_overbought_rsi_60_to_70(self):
        tech = _technicals(rsi=65.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "APPROACHING_OVERBOUGHT"
        assert strategy["sell_signals"] >= 1

    def test_neutral_rsi_40_to_60(self):
        tech = _technicals(rsi=50.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "NEUTRAL"

    def test_rsi_boundary_30_exact(self):
        """RSI == 30 should be APPROACHING_OVERSOLD (not < 30 oversold)."""
        tech = _technicals(rsi=30.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "APPROACHING_OVERSOLD"

    def test_rsi_boundary_40_exact(self):
        """RSI == 40 is NOT < 40, so it falls to neutral."""
        tech = _technicals(rsi=40.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "NEUTRAL"

    def test_rsi_boundary_60_exact(self):
        """RSI == 60 is NOT > 60, so it falls to neutral."""
        tech = _technicals(rsi=60.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "NEUTRAL"

    def test_rsi_boundary_70_exact(self):
        """RSI == 70 should be APPROACHING_OVERBOUGHT (not > 70 overbought)."""
        tech = _technicals(rsi=70.0)
        strategy = _build_strategy(tech, {})
        rsi_cond = [c for c in strategy["conditions"] if c["indicator"] == "RSI"][0]
        assert rsi_cond["signal"] == "APPROACHING_OVERBOUGHT"

    def test_rsi_none(self):
        """If RSI is None, no RSI condition added."""
        tech = _technicals(rsi=None)
        strategy = _build_strategy(tech, {})
        rsi_conds = [c for c in strategy["conditions"] if c["indicator"] == "RSI"]
        assert len(rsi_conds) == 0


class TestBuildStrategyMACD:
    """MACD golden/dead cross signals."""

    def test_golden_cross(self):
        tech = _technicals(macd=1.5, macd_signal=0.5)
        strategy = _build_strategy(tech, {})
        macd_cond = [c for c in strategy["conditions"] if c["indicator"] == "MACD"][0]
        assert macd_cond["signal"] == "BULLISH"
        assert macd_cond["value"] == pytest.approx(1.0, abs=0.001)

    def test_dead_cross(self):
        tech = _technicals(macd=-0.5, macd_signal=0.5)
        strategy = _build_strategy(tech, {})
        macd_cond = [c for c in strategy["conditions"] if c["indicator"] == "MACD"][0]
        assert macd_cond["signal"] == "BEARISH"
        assert macd_cond["value"] == pytest.approx(-1.0, abs=0.001)

    def test_macd_equal_to_signal(self):
        """When MACD == signal, it's not > signal, so BEARISH."""
        tech = _technicals(macd=0.5, macd_signal=0.5)
        strategy = _build_strategy(tech, {})
        macd_cond = [c for c in strategy["conditions"] if c["indicator"] == "MACD"][0]
        assert macd_cond["signal"] == "BEARISH"

    def test_macd_none(self):
        """No MACD condition if macd is None."""
        tech = _technicals(macd=None, macd_signal=None)
        strategy = _build_strategy(tech, {})
        macd_conds = [c for c in strategy["conditions"] if c["indicator"] == "MACD"]
        assert len(macd_conds) == 0

    def test_macd_partial_none(self):
        """No MACD condition if macd_signal is None."""
        tech = _technicals(macd=1.0, macd_signal=None)
        strategy = _build_strategy(tech, {})
        macd_conds = [c for c in strategy["conditions"] if c["indicator"] == "MACD"]
        assert len(macd_conds) == 0


class TestBuildStrategyDisparity:
    """Disparity (distance from 20MA) signals."""

    def test_overextended_above_110(self):
        tech = _technicals(disparity=115.0)
        strategy = _build_strategy(tech, {})
        disp_cond = [c for c in strategy["conditions"] if c["indicator"] == "Disparity"][0]
        assert disp_cond["signal"] == "OVEREXTENDED"

    def test_underextended_below_90(self):
        tech = _technicals(disparity=85.0)
        strategy = _build_strategy(tech, {})
        disp_cond = [c for c in strategy["conditions"] if c["indicator"] == "Disparity"][0]
        assert disp_cond["signal"] == "UNDEREXTENDED"

    def test_disparity_in_normal_range(self):
        """Disparity between 90 and 110 => no disparity condition."""
        tech = _technicals(disparity=100.0)
        strategy = _build_strategy(tech, {})
        disp_conds = [c for c in strategy["conditions"] if c["indicator"] == "Disparity"]
        assert len(disp_conds) == 0

    def test_disparity_boundary_110(self):
        """Disparity == 110.0 is NOT > 110, so no condition."""
        tech = _technicals(disparity=110.0)
        strategy = _build_strategy(tech, {})
        disp_conds = [c for c in strategy["conditions"] if c["indicator"] == "Disparity"]
        assert len(disp_conds) == 0

    def test_disparity_boundary_90(self):
        """Disparity == 90.0 is NOT < 90, so no condition."""
        tech = _technicals(disparity=90.0)
        strategy = _build_strategy(tech, {})
        disp_conds = [c for c in strategy["conditions"] if c["indicator"] == "Disparity"]
        assert len(disp_conds) == 0

    def test_disparity_none(self):
        """No condition if disparity is None."""
        tech = _technicals(disparity=None)
        strategy = _build_strategy(tech, {})
        disp_conds = [c for c in strategy["conditions"] if c["indicator"] == "Disparity"]
        assert len(disp_conds) == 0


class TestBuildStrategyVolume:
    """Volume ratio signals."""

    def test_high_volume(self):
        tech = _technicals(volume_ratio=2.5)
        strategy = _build_strategy(tech, {})
        vol_cond = [c for c in strategy["conditions"] if c["indicator"] == "Volume"][0]
        assert vol_cond["signal"] == "HIGH_VOLUME"

    def test_low_volume(self):
        tech = _technicals(volume_ratio=0.3)
        strategy = _build_strategy(tech, {})
        vol_cond = [c for c in strategy["conditions"] if c["indicator"] == "Volume"][0]
        assert vol_cond["signal"] == "LOW_VOLUME"

    def test_normal_volume(self):
        """Volume ratio between 0.5 and 2.0 => no volume condition."""
        tech = _technicals(volume_ratio=1.0)
        strategy = _build_strategy(tech, {})
        vol_conds = [c for c in strategy["conditions"] if c["indicator"] == "Volume"]
        assert len(vol_conds) == 0

    def test_volume_boundary_2(self):
        """volume_ratio == 2.0 is NOT > 2.0, so no high volume signal."""
        tech = _technicals(volume_ratio=2.0)
        strategy = _build_strategy(tech, {})
        vol_conds = [c for c in strategy["conditions"] if c["indicator"] == "Volume"]
        assert len(vol_conds) == 0

    def test_volume_boundary_0_5(self):
        """volume_ratio == 0.5 is NOT < 0.5, so no low volume signal."""
        tech = _technicals(volume_ratio=0.5)
        strategy = _build_strategy(tech, {})
        vol_conds = [c for c in strategy["conditions"] if c["indicator"] == "Volume"]
        assert len(vol_conds) == 0

    def test_volume_none(self):
        tech = _technicals(volume_ratio=None)
        strategy = _build_strategy(tech, {})
        vol_conds = [c for c in strategy["conditions"] if c["indicator"] == "Volume"]
        assert len(vol_conds) == 0

    def test_volume_does_not_affect_buy_sell_signals(self):
        """Volume conditions don't increment buy_signals or sell_signals."""
        tech = _technicals(rsi=50.0, macd=None, macd_signal=None,
                           disparity=100.0, volume_ratio=3.0)
        strategy = _build_strategy(tech, {})
        assert strategy["buy_signals"] == 0
        assert strategy["sell_signals"] == 0


# ════════════════════════════════════════════════════════════════
# Stance determination (composite signal counting)
# ════════════════════════════════════════════════════════════════


class TestBuildStrategyStance:
    """Overall stance determination based on signal counts."""

    def test_strong_buy(self):
        """buy_signals >= 3: RSI oversold (+2) + MACD bullish (+1) + disparity under (+1) = 4."""
        tech = _technicals(rsi=25.0, macd=1.0, macd_signal=0.5, disparity=85.0)
        strategy = _build_strategy(tech, {})
        assert strategy["stance"] == "STRONG_BUY"
        assert strategy["buy_signals"] >= 3

    def test_buy(self):
        """buy_signals == 2: RSI approaching oversold (+1) + MACD bullish (+1) = 2."""
        tech = _technicals(rsi=35.0, macd=1.0, macd_signal=0.5, disparity=100.0)
        strategy = _build_strategy(tech, {})
        assert strategy["stance"] == "BUY"
        assert strategy["buy_signals"] == 2

    def test_strong_sell(self):
        """sell_signals >= 3: RSI overbought (+2) + MACD bearish (+1) + disparity over (+1) = 4."""
        tech = _technicals(rsi=75.0, macd=-0.5, macd_signal=0.5, disparity=115.0)
        strategy = _build_strategy(tech, {})
        assert strategy["stance"] == "STRONG_SELL"
        assert strategy["sell_signals"] >= 3

    def test_sell(self):
        """sell_signals == 2: RSI approaching overbought (+1) + MACD bearish (+1) = 2."""
        tech = _technicals(rsi=65.0, macd=-0.5, macd_signal=0.5, disparity=100.0)
        strategy = _build_strategy(tech, {})
        assert strategy["stance"] == "SELL"
        assert strategy["sell_signals"] == 2

    def test_hold_neutral(self):
        """No clear direction => HOLD."""
        tech = _technicals(rsi=50.0, macd=0.0, macd_signal=0.0, disparity=100.0)
        strategy = _build_strategy(tech, {})
        assert strategy["stance"] == "HOLD"

    def test_buy_priority_over_sell_when_equal(self):
        """When buy_signals >= 3 and sell_signals >= 3, buy check comes first in code."""
        # RSI oversold (+2 buy) + disparity under (+1 buy) = 3 buy
        # MACD bearish (+1 sell) + ... not enough for 3 sell
        # Actually, let's set up a realistic scenario
        # buy_signals=3, sell_signals=2: should be STRONG_BUY
        tech = _technicals(rsi=25.0, macd=1.0, macd_signal=0.5, disparity=85.0, volume_ratio=0.3)
        strategy = _build_strategy(tech, {})
        # buy=4 (rsi oversold+2, macd+1, disparity under+1), sell=0
        assert strategy["stance"] == "STRONG_BUY"

    def test_mixed_signals_hold(self):
        """1 buy + 1 sell => neither >= 2, so HOLD."""
        tech = _technicals(rsi=50.0, macd=1.0, macd_signal=0.5, disparity=115.0)
        strategy = _build_strategy(tech, {})
        # MACD bullish +1 buy, disparity over +1 sell => HOLD
        assert strategy["buy_signals"] == 1
        assert strategy["sell_signals"] == 1
        assert strategy["stance"] == "HOLD"

    def test_stance_desc_matches_stance(self):
        """Ensure stance_desc corresponds to the stance value."""
        test_cases = [
            (_technicals(rsi=25.0, macd=1.0, macd_signal=0.5, disparity=85.0), "STRONG_BUY"),
            (_technicals(rsi=35.0, macd=1.0, macd_signal=0.5), "BUY"),
            (_technicals(rsi=75.0, macd=-0.5, macd_signal=0.5, disparity=115.0), "STRONG_SELL"),
            (_technicals(rsi=65.0, macd=-0.5, macd_signal=0.5), "SELL"),
            (_technicals(rsi=50.0), "HOLD"),
        ]
        for tech, expected_stance in test_cases:
            strategy = _build_strategy(tech, {})
            assert strategy["stance"] == expected_stance
            # stance_desc should be a non-empty string
            assert isinstance(strategy["stance_desc"], str)
            assert len(strategy["stance_desc"]) > 0


# ════════════════════════════════════════════════════════════════
# Risk warnings
# ════════════════════════════════════════════════════════════════


class TestBuildStrategyRiskWarnings:
    """SOXL-specific risk warnings."""

    def test_base_risk_warnings_always_present(self):
        strategy = _build_strategy(None, {})
        assert len(strategy["risk_warnings"]) >= 2
        # Check the two static warnings are present
        warnings_text = " ".join(strategy["risk_warnings"])
        assert "3x" in warnings_text
        assert "decay" in warnings_text or "감쇠" in warnings_text

    def test_extreme_volatility_warning(self):
        """Volatility > 80 adds extreme volatility warning."""
        strategy = _build_strategy(None, {"volatility_20d_ann": 90.0})
        vol_warnings = [w for w in strategy["risk_warnings"] if "90" in w]
        assert len(vol_warnings) >= 1

    def test_high_volatility_warning(self):
        """Volatility > 60 adds position sizing warning."""
        strategy = _build_strategy(None, {"volatility_20d_ann": 65.0})
        sizing_warnings = [w for w in strategy["risk_warnings"] if "50%" in w or "축소" in w]
        assert len(sizing_warnings) >= 1

    def test_volatility_above_80_adds_both_warnings(self):
        """Volatility > 80 triggers BOTH >80 and >60 warnings."""
        strategy = _build_strategy(None, {"volatility_20d_ann": 85.0})
        # Should have base 2 + extreme + high = 4 warnings
        assert len(strategy["risk_warnings"]) == 4

    def test_volatility_61_only_high_warning(self):
        """Volatility 61 triggers only the >60 warning, not the >80 one."""
        strategy = _build_strategy(None, {"volatility_20d_ann": 61.0})
        assert len(strategy["risk_warnings"]) == 3  # base 2 + high vol
        extreme_warnings = [w for w in strategy["risk_warnings"] if "극단적" in w]
        assert len(extreme_warnings) == 0

    def test_low_volatility_no_extra_warnings(self):
        """Volatility <= 60 => only the 2 base warnings."""
        strategy = _build_strategy(None, {"volatility_20d_ann": 50.0})
        assert len(strategy["risk_warnings"]) == 2

    def test_no_volatility_data(self):
        """Missing volatility => only base warnings."""
        strategy = _build_strategy(None, {})
        assert len(strategy["risk_warnings"]) == 2

    def test_volatility_boundary_80(self):
        """Volatility == 80 does NOT trigger >80 warning (strict >)."""
        strategy = _build_strategy(None, {"volatility_20d_ann": 80.0})
        # Only >60 warning + 2 base = 3
        assert len(strategy["risk_warnings"]) == 3

    def test_volatility_boundary_60(self):
        """Volatility == 60 does NOT trigger >60 warning (strict >)."""
        strategy = _build_strategy(None, {"volatility_20d_ann": 60.0})
        assert len(strategy["risk_warnings"]) == 2


# ════════════════════════════════════════════════════════════════
# Trading rules structure
# ════════════════════════════════════════════════════════════════


class TestBuildStrategyTradingRules:
    """Validate the static trading rules structure."""

    def test_trading_rules_present(self):
        strategy = _build_strategy(None, {})
        rules = strategy["trading_rules"]
        assert "entry_rules" in rules
        assert "exit_rules" in rules
        assert "position_sizing" in rules

    def test_entry_rules_count(self):
        strategy = _build_strategy(None, {})
        assert len(strategy["trading_rules"]["entry_rules"]) == 4

    def test_exit_rules_count(self):
        strategy = _build_strategy(None, {})
        assert len(strategy["trading_rules"]["exit_rules"]) == 4

    def test_position_sizing_count(self):
        strategy = _build_strategy(None, {})
        assert len(strategy["trading_rules"]["position_sizing"]) == 3

    def test_each_rule_has_required_keys(self):
        strategy = _build_strategy(None, {})
        for category in ("entry_rules", "exit_rules", "position_sizing"):
            for rule in strategy["trading_rules"][category]:
                assert "rule" in rule, f"Missing 'rule' key in {category}"
                assert "desc" in rule, f"Missing 'desc' key in {category}"
                assert isinstance(rule["rule"], str)
                assert isinstance(rule["desc"], str)
                assert len(rule["rule"]) > 0
                assert len(rule["desc"]) > 0


# ════════════════════════════════════════════════════════════════
# API Integration Tests
# ════════════════════════════════════════════════════════════════


async def _seed_soxl_data():
    """Insert SOXL price, technical, and signal data for integration tests."""
    from app.database.connection import get_db

    db = await get_db()

    # Price history — 30 days
    for i in range(30):
        close = 30.0 + i * 0.5
        await db.execute(
            """INSERT OR IGNORE INTO price_history
               (symbol, market, trade_date, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("SOXL", "US", f"2025-05-{i + 1:02d}", close - 0.5, close + 1.0,
             close - 1.0, close, 5_000_000 + i * 100_000),
        )

    # Technical indicators
    await db.execute(
        """INSERT OR IGNORE INTO technical_indicators
           (symbol, market, trade_date, rsi_14, ma_5, ma_20, ma_60,
            macd, macd_signal, bollinger_upper, bollinger_middle, bollinger_lower,
            volume_ratio, disparity_20)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("SOXL", "US", "2025-05-30", 55.0, 43.0, 40.0, 35.0,
         0.8, 0.5, 48.0, 44.0, 40.0, 1.2, 102.5),
    )

    # Signals
    for i in range(5):
        await db.execute(
            """INSERT OR IGNORE INTO signals
               (run_id, symbol, market, signal_date, raw_signal, raw_score,
                final_signal, hard_limit_triggered, confidence, rationale)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"soxl-run-{i}", "SOXL", "US", f"2025-05-{25 + i:02d}",
             "BUY" if i % 2 == 0 else "HOLD", 1.5 if i % 2 == 0 else 0.3,
             "BUY" if i % 2 == 0 else "HOLD", 0, 0.7, "Test rationale"),
        )

    await db.commit()


async def _cleanup_soxl_data():
    """Remove SOXL-specific test data."""
    from app.database.connection import get_db

    db = await get_db()
    for table in ("price_history", "technical_indicators", "signals"):
        await db.execute(f"DELETE FROM {table} WHERE symbol='SOXL'")  # noqa: S608
    await db.commit()


@pytest_asyncio.fixture()
async def soxl_client(setup_db):
    """Client with SOXL router registered + SOXL data seeded."""
    import httpx
    from fastapi import FastAPI
    from app.routers import soxl

    test_app = FastAPI()
    test_app.include_router(soxl.router)

    await _seed_soxl_data()

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await _cleanup_soxl_data()


class TestSoxlDashboardEndpoint:
    """GET /soxl/dashboard integration tests."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_200(self, soxl_client):
        resp = await soxl_client.get("/soxl/dashboard")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_dashboard_static_metadata(self, soxl_client):
        data = (await soxl_client.get("/soxl/dashboard")).json()
        assert data["symbol"] == "SOXL"
        assert data["name"] == "Direxion Daily Semiconductor Bull 3X Shares"
        assert data["asset_type"] == "3x Leveraged ETF"
        assert data["underlying"] == "ICE Semiconductor Index"

    @pytest.mark.asyncio
    async def test_dashboard_has_prices(self, soxl_client):
        data = (await soxl_client.get("/soxl/dashboard")).json()
        assert len(data["prices"]) > 0
        # Should be sorted ascending (earliest first after reverse)
        dates = [p["date"] for p in data["prices"]]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_dashboard_has_technicals(self, soxl_client):
        data = (await soxl_client.get("/soxl/dashboard")).json()
        tech = data["technicals"]
        assert tech is not None
        assert tech["rsi_14"] == 55.0
        assert tech["macd"] == 0.8
        assert tech["macd_signal"] == 0.5

    @pytest.mark.asyncio
    async def test_dashboard_has_signals(self, soxl_client):
        data = (await soxl_client.get("/soxl/dashboard")).json()
        assert len(data["signals"]) == 5
        # Each signal should have required keys
        for sig in data["signals"]:
            assert "date" in sig
            assert "raw_signal" in sig
            assert "final_signal" in sig
            assert "hard_limit" in sig

    @pytest.mark.asyncio
    async def test_dashboard_has_performance(self, soxl_client):
        data = (await soxl_client.get("/soxl/dashboard")).json()
        perf = data["performance"]
        assert perf["current_price"] is not None
        assert "change_1d" in perf

    @pytest.mark.asyncio
    async def test_dashboard_has_strategy(self, soxl_client):
        data = (await soxl_client.get("/soxl/dashboard")).json()
        strat = data["strategy"]
        assert strat["stance"] in ("STRONG_BUY", "BUY", "SELL", "STRONG_SELL", "HOLD")
        assert "conditions" in strat
        assert "risk_warnings" in strat
        assert "trading_rules" in strat

    @pytest.mark.asyncio
    async def test_dashboard_days_parameter(self, soxl_client):
        resp_30 = await soxl_client.get("/soxl/dashboard", params={"days": 10})
        assert resp_30.status_code == 200
        data_30 = resp_30.json()
        assert len(data_30["prices"]) <= 10

    @pytest.mark.asyncio
    async def test_dashboard_has_updated_at(self, soxl_client):
        data = (await soxl_client.get("/soxl/dashboard")).json()
        assert "updated_at" in data
        assert "T" in data["updated_at"]  # ISO format


class TestSoxlLevelsEndpoint:
    """GET /soxl/levels integration tests."""

    @pytest.mark.asyncio
    async def test_levels_returns_200(self, soxl_client):
        resp = await soxl_client.get("/soxl/levels")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_levels_has_fibonacci(self, soxl_client):
        data = (await soxl_client.get("/soxl/levels")).json()
        fib = data["fibonacci"]
        assert "52w_high" in fib
        assert "52w_low" in fib
        assert "fib_618" in fib
        assert "fib_382" in fib
        assert "fib_500" in fib
        # 52w_high >= 52w_low
        assert fib["52w_high"] >= fib["52w_low"]

    @pytest.mark.asyncio
    async def test_levels_fibonacci_ordering(self, soxl_client):
        data = (await soxl_client.get("/soxl/levels")).json()
        fib = data["fibonacci"]
        # Levels should be in descending order
        assert fib["52w_high"] >= fib["fib_786"]
        assert fib["fib_786"] >= fib["fib_618"]
        assert fib["fib_618"] >= fib["fib_500"]
        assert fib["fib_500"] >= fib["fib_382"]
        assert fib["fib_382"] >= fib["fib_236"]
        assert fib["fib_236"] >= fib["52w_low"]

    @pytest.mark.asyncio
    async def test_levels_has_pivot_points(self, soxl_client):
        data = (await soxl_client.get("/soxl/levels")).json()
        pp = data["pivot_points"]
        assert "pivot" in pp
        assert "r1" in pp
        assert "r2" in pp
        assert "s1" in pp
        assert "s2" in pp
        # Resistance > Support
        assert pp["r2"] >= pp["r1"]
        assert pp["r1"] >= pp["pivot"]
        assert pp["pivot"] >= pp["s1"]
        assert pp["s1"] >= pp["s2"]

    @pytest.mark.asyncio
    async def test_levels_has_position(self, soxl_client):
        data = (await soxl_client.get("/soxl/levels")).json()
        pos = data["position"]
        assert "pct_from_52w_high" in pos
        assert "pct_from_52w_low" in pos
        # pct_from_high should be <= 0, pct_from_low should be >= 0
        assert pos["pct_from_52w_high"] <= 0
        assert pos["pct_from_52w_low"] >= 0

    @pytest.mark.asyncio
    async def test_levels_current_price(self, soxl_client):
        data = (await soxl_client.get("/soxl/levels")).json()
        assert "current_price" in data
        assert data["current_price"] > 0


class TestSoxlLevelsEmpty:
    """GET /soxl/levels with no data."""

    @pytest.mark.asyncio
    async def test_levels_empty_db(self, setup_db):
        """No SOXL data => empty levels response."""
        import httpx
        from fastapi import FastAPI
        from app.routers import soxl

        test_app = FastAPI()
        test_app.include_router(soxl.router)

        # Ensure no SOXL data
        await _cleanup_soxl_data()

        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/soxl/levels")
            assert resp.status_code == 200
            data = resp.json()
            assert data["levels"] == []
            assert data["zones"] == []
