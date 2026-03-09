"""Tests for backtest performance metric calculations."""

import math
import pytest
from app.backtesting.metrics import compute_backtest_metrics


class TestEmptyInput:
    """Edge cases with no or invalid trades."""

    def test_empty_trades(self):
        result = compute_backtest_metrics([])
        assert result["total_trades"] == 0
        assert result["hit_rate"] is None
        assert result["avg_return"] is None
        assert result["sharpe_ratio"] is None
        assert result["max_drawdown"] is None
        assert result["profit_factor"] is None
        assert result["win_loss_ratio"] is None
        assert result["total_return"] is None

    def test_trades_with_no_return_pct(self):
        trades = [{"return_pct": None, "holding_days": 5}]
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 1
        assert result["hit_rate"] is None

    def test_trades_missing_return_pct_key(self):
        trades = [{"holding_days": 5}]
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 1
        assert result["hit_rate"] is None


class TestSingleTrade:
    """Metrics with exactly one trade."""

    def test_single_winning_trade(self):
        trades = [{"return_pct": 10.0, "holding_days": 5}]
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 1
        assert result["hit_rate"] == 1.0
        assert result["avg_return"] == 10.0
        assert result["sharpe_ratio"] == 0  # single trade → 0
        assert result["max_drawdown"] == 0.0  # no drawdown
        assert result["total_return"] == 10.0

    def test_single_losing_trade(self):
        trades = [{"return_pct": -5.0, "holding_days": 10}]
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 1
        assert result["hit_rate"] == 0.0
        assert result["avg_return"] == -5.0
        assert result["sharpe_ratio"] == 0
        assert result["total_return"] == pytest.approx(-5.0, abs=0.01)

    def test_single_zero_return(self):
        trades = [{"return_pct": 0.0, "holding_days": 3}]
        result = compute_backtest_metrics(trades)
        assert result["hit_rate"] == 0.0  # 0 is not > 0
        assert result["total_return"] == 0.0


class TestHitRate:
    """Hit rate (win/loss ratio) correctness."""

    def test_all_winners(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 3},
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": 2.0, "holding_days": 7},
        ]
        result = compute_backtest_metrics(trades)
        assert result["hit_rate"] == 1.0

    def test_all_losers(self):
        trades = [
            {"return_pct": -3.0, "holding_days": 4},
            {"return_pct": -8.0, "holding_days": 6},
        ]
        result = compute_backtest_metrics(trades)
        assert result["hit_rate"] == 0.0

    def test_mixed(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 3},
            {"return_pct": -3.0, "holding_days": 4},
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": -1.0, "holding_days": 2},
        ]
        result = compute_backtest_metrics(trades)
        assert result["hit_rate"] == 0.5


class TestTotalReturn:
    """Compounded total return calculation."""

    def test_compounding(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": -5.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        expected = (1.10 * 0.95 - 1) * 100  # 4.5%
        assert result["total_return"] == pytest.approx(expected, abs=0.01)

    def test_large_losses(self):
        trades = [
            {"return_pct": -50.0, "holding_days": 10},
            {"return_pct": 50.0, "holding_days": 10},
        ]
        result = compute_backtest_metrics(trades)
        expected = (0.50 * 1.50 - 1) * 100  # -25%
        assert result["total_return"] == pytest.approx(expected, abs=0.01)


class TestSharpeRatio:
    """Annualized Sharpe ratio calculation."""

    def test_capped_at_99(self):
        # Very consistent positive returns → huge Sharpe
        trades = [
            {"return_pct": 10.0, "holding_days": 1},
            {"return_pct": 10.0001, "holding_days": 1},
        ]
        result = compute_backtest_metrics(trades)
        assert result["sharpe_ratio"] <= 99

    def test_capped_at_neg_99(self):
        # Very consistent negative returns
        trades = [
            {"return_pct": -10.0, "holding_days": 1},
            {"return_pct": -10.0001, "holding_days": 1},
        ]
        result = compute_backtest_metrics(trades)
        assert result["sharpe_ratio"] >= -99

    def test_zero_std_uses_fallback(self):
        # Identical returns → std should use 0.001 fallback
        trades = [
            {"return_pct": 5.0, "holding_days": 5},
            {"return_pct": 5.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # Should still produce a valid (capped) number, may be int after round()
        assert isinstance(result["sharpe_ratio"], (int, float))
        assert -99 <= result["sharpe_ratio"] <= 99

    def test_normal_sharpe(self):
        # Realistic trades
        trades = [
            {"return_pct": 3.0, "holding_days": 10},
            {"return_pct": -1.0, "holding_days": 8},
            {"return_pct": 5.0, "holding_days": 12},
            {"return_pct": -2.0, "holding_days": 7},
            {"return_pct": 4.0, "holding_days": 9},
        ]
        result = compute_backtest_metrics(trades)
        assert -99 <= result["sharpe_ratio"] <= 99
        assert result["sharpe_ratio"] > 0  # net positive returns


class TestMaxDrawdown:
    """Peak-to-trough equity curve drawdown."""

    def test_no_drawdown_monotonic_gains(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 5},
            {"return_pct": 3.0, "holding_days": 5},
            {"return_pct": 2.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["max_drawdown"] == 0.0

    def test_simple_drawdown(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": -20.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # equity: 1.0 → 1.10 → 0.88. Peak=1.10, dd = (1.10-0.88)/1.10 = 20%
        assert result["max_drawdown"] == pytest.approx(20.0, abs=0.1)

    def test_drawdown_with_recovery(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": -10.0, "holding_days": 5},
            {"return_pct": 20.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # Drawdown after second trade, then recovery
        assert result["max_drawdown"] > 0


class TestProfitFactor:
    """Gross profit / gross loss ratio."""

    def test_no_losses(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 5},
            {"return_pct": 10.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["profit_factor"] == 999  # capped inf

    def test_no_wins(self):
        trades = [
            {"return_pct": -5.0, "holding_days": 5},
            {"return_pct": -10.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["profit_factor"] == 0

    def test_normal(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": -5.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["profit_factor"] == pytest.approx(2.0, abs=0.01)


class TestWinLossRatio:
    """Average win / average loss ratio."""

    def test_no_losses(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 5},
            {"return_pct": 10.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["win_loss_ratio"] == 999  # capped

    def test_balanced(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": -10.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["win_loss_ratio"] == pytest.approx(1.0, abs=0.01)

    def test_asymmetric(self):
        trades = [
            {"return_pct": 20.0, "holding_days": 5},
            {"return_pct": -5.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["win_loss_ratio"] == pytest.approx(4.0, abs=0.01)


class TestRounding:
    """All outputs should be rounded to 4 decimal places."""

    def test_results_rounded(self):
        trades = [
            {"return_pct": 3.33333, "holding_days": 7},
            {"return_pct": -1.11111, "holding_days": 5},
            {"return_pct": 2.22222, "holding_days": 6},
        ]
        result = compute_backtest_metrics(trades)
        for key in ["hit_rate", "avg_return", "sharpe_ratio", "max_drawdown",
                     "profit_factor", "win_loss_ratio", "total_return"]:
            val = result[key]
            assert val == round(val, 4), f"{key} not rounded to 4 decimals"


# ──────────────────────────────────────────────────────────────────
# Extended tests appended below
# ──────────────────────────────────────────────────────────────────


class TestZeroVarianceReturns:
    """All identical returns produce zero standard deviation."""

    def test_identical_positive_returns(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 10},
            {"return_pct": 5.0, "holding_days": 10},
            {"return_pct": 5.0, "holding_days": 10},
        ]
        result = compute_backtest_metrics(trades)
        # Zero variance => sharpe falls back to 0
        assert result["sharpe_ratio"] == 0
        assert result["hit_rate"] == 1.0
        assert result["avg_return"] == 5.0

    def test_identical_negative_returns(self):
        trades = [
            {"return_pct": -3.0, "holding_days": 7},
            {"return_pct": -3.0, "holding_days": 7},
            {"return_pct": -3.0, "holding_days": 7},
        ]
        result = compute_backtest_metrics(trades)
        assert result["sharpe_ratio"] == 0
        assert result["hit_rate"] == 0.0
        assert result["avg_return"] == -3.0

    def test_identical_zero_returns(self):
        trades = [
            {"return_pct": 0.0, "holding_days": 5},
            {"return_pct": 0.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["sharpe_ratio"] == 0
        assert result["avg_return"] == 0.0
        assert result["total_return"] == 0.0
        assert result["max_drawdown"] == 0.0


class TestLargeNumberOfTrades:
    """Stress-test with many trades to ensure no overflow or performance issues."""

    def test_hundred_trades_alternating(self):
        trades = []
        for i in range(100):
            pct = 2.0 if i % 2 == 0 else -1.0
            trades.append({"return_pct": pct, "holding_days": 10})
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 100
        assert result["hit_rate"] == 0.5
        assert result["avg_return"] == pytest.approx(0.5, abs=0.01)
        assert result["sharpe_ratio"] is not None
        assert result["max_drawdown"] is not None
        assert result["profit_factor"] is not None

    def test_five_hundred_trades_all_wins(self):
        trades = [{"return_pct": 0.5, "holding_days": 5} for _ in range(500)]
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 500
        assert result["hit_rate"] == 1.0
        assert result["max_drawdown"] == 0.0
        assert result["profit_factor"] == 999  # inf capped

    def test_thousand_trades_random_pattern(self):
        """Pattern of +3, -1, +2, -4 repeated 250 times."""
        pattern = [3.0, -1.0, 2.0, -4.0]
        trades = [
            {"return_pct": pattern[i % 4], "holding_days": 10}
            for i in range(1000)
        ]
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 1000
        assert result["hit_rate"] == 0.5  # 500 wins, 500 losses
        assert result["avg_return"] == 0.0  # (3 - 1 + 2 - 4) / 4 = 0
        assert isinstance(result["sharpe_ratio"], (int, float))


class TestNegativeTotalReturn:
    """Total return should be negative when losses dominate."""

    def test_net_negative_total_return(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 10},
            {"return_pct": -20.0, "holding_days": 10},
            {"return_pct": 3.0, "holding_days": 10},
        ]
        result = compute_backtest_metrics(trades)
        # (1.05)(0.80)(1.03) - 1 = -0.1332 = -13.32%
        expected = (1.05 * 0.80 * 1.03 - 1) * 100
        assert result["total_return"] == pytest.approx(expected, abs=0.1)
        assert result["total_return"] < 0

    def test_severe_loss(self):
        trades = [
            {"return_pct": -90.0, "holding_days": 10},
        ]
        result = compute_backtest_metrics(trades)
        assert result["total_return"] == pytest.approx(-90.0, abs=0.01)
        assert result["max_drawdown"] == pytest.approx(90.0, abs=0.1)

    def test_all_small_losses(self):
        trades = [
            {"return_pct": -0.1, "holding_days": 5},
            {"return_pct": -0.1, "holding_days": 5},
            {"return_pct": -0.1, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["total_return"] < 0
        assert result["hit_rate"] == 0.0
        assert result["profit_factor"] == 0


class TestMaxDrawdownEdgeCases:
    """Drawdown edge cases beyond what existing tests cover."""

    def test_all_wins_zero_drawdown(self):
        """Monotonically increasing equity => zero drawdown."""
        trades = [
            {"return_pct": 1.0, "holding_days": 5},
            {"return_pct": 2.0, "holding_days": 5},
            {"return_pct": 3.0, "holding_days": 5},
            {"return_pct": 4.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["max_drawdown"] == 0.0

    def test_drawdown_then_new_high(self):
        """Drawdown followed by recovery to new high, then another drawdown."""
        trades = [
            {"return_pct": 20.0, "holding_days": 5},   # equity: 1.20
            {"return_pct": -10.0, "holding_days": 5},   # equity: 1.08
            {"return_pct": 15.0, "holding_days": 5},    # equity: 1.242
            {"return_pct": -25.0, "holding_days": 5},   # equity: 0.9315
        ]
        result = compute_backtest_metrics(trades)
        # Second drawdown: (1.242 - 0.9315) / 1.242 = 25%
        assert result["max_drawdown"] == pytest.approx(25.0, abs=0.1)

    def test_continuous_losses_increasing_drawdown(self):
        """Each trade deepens the drawdown."""
        trades = [
            {"return_pct": -10.0, "holding_days": 5},
            {"return_pct": -10.0, "holding_days": 5},
            {"return_pct": -10.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # equity: 1 -> 0.9 -> 0.81 -> 0.729
        # dd = (1 - 0.729) / 1 = 27.1%
        assert result["max_drawdown"] == pytest.approx(27.1, abs=0.1)

    def test_single_loss_drawdown_equals_loss(self):
        """Single loss trade: drawdown equals the loss percentage."""
        trades = [{"return_pct": -15.0, "holding_days": 10}]
        result = compute_backtest_metrics(trades)
        assert result["max_drawdown"] == pytest.approx(15.0, abs=0.1)


class TestSharpeRatioEdgeCases:
    """Additional Sharpe ratio scenarios."""

    def test_sharpe_positive_for_net_positive_trades(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": 5.0, "holding_days": 10},
            {"return_pct": -2.0, "holding_days": 10},
        ]
        result = compute_backtest_metrics(trades)
        assert result["sharpe_ratio"] > 0

    def test_sharpe_negative_for_net_negative_trades(self):
        trades = [
            {"return_pct": -10.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 10},
            {"return_pct": 2.0, "holding_days": 10},
        ]
        result = compute_backtest_metrics(trades)
        assert result["sharpe_ratio"] < 0

    def test_sharpe_varies_with_holding_days(self):
        """Shorter holding days => more trades per year => higher annualized Sharpe."""
        trades_short = [
            {"return_pct": 2.0, "holding_days": 1},
            {"return_pct": -1.0, "holding_days": 1},
            {"return_pct": 3.0, "holding_days": 1},
        ]
        trades_long = [
            {"return_pct": 2.0, "holding_days": 60},
            {"return_pct": -1.0, "holding_days": 60},
            {"return_pct": 3.0, "holding_days": 60},
        ]
        r_short = compute_backtest_metrics(trades_short)
        r_long = compute_backtest_metrics(trades_long)
        # Same per-trade returns, but short holding => more trades/year => higher Sharpe
        assert abs(r_short["sharpe_ratio"]) > abs(r_long["sharpe_ratio"])

    def test_sharpe_two_trades_minimum_for_calculation(self):
        """With exactly two trades, Sharpe should be calculated (not zero fallback)."""
        trades = [
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": -5.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # len(returns) > 1 so Sharpe is calculated, not the single-trade fallback
        assert isinstance(result["sharpe_ratio"], (int, float))

    def test_sharpe_zero_holding_days_uses_one(self):
        """holding_days=0 should not cause division by zero (max(avg_holding, 1))."""
        trades = [
            {"return_pct": 5.0, "holding_days": 0},
            {"return_pct": -2.0, "holding_days": 0},
        ]
        result = compute_backtest_metrics(trades)
        assert isinstance(result["sharpe_ratio"], (int, float))
        assert -99 <= result["sharpe_ratio"] <= 99

    def test_sharpe_missing_holding_days_key(self):
        """Trades missing holding_days should use default of 10."""
        trades = [
            {"return_pct": 5.0},
            {"return_pct": -2.0},
        ]
        result = compute_backtest_metrics(trades)
        assert isinstance(result["sharpe_ratio"], (int, float))


class TestMixedValidInvalidTrades:
    """Mix of valid and invalid (missing/None return_pct) trades."""

    def test_some_valid_some_none(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": None, "holding_days": 5},
            {"return_pct": -3.0, "holding_days": 5},
            {"holding_days": 5},  # missing key
        ]
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 4
        # Only 2 valid returns: 10.0 and -3.0
        assert result["hit_rate"] == 0.5
        assert result["avg_return"] == pytest.approx(3.5, abs=0.01)

    def test_all_none_return_pct(self):
        trades = [
            {"return_pct": None, "holding_days": 5},
            {"return_pct": None, "holding_days": 10},
        ]
        result = compute_backtest_metrics(trades)
        assert result["total_trades"] == 2
        assert result["hit_rate"] is None
        assert result["avg_return"] is None


class TestTinyReturns:
    """Very small return values near zero."""

    def test_very_small_positive_returns(self):
        trades = [
            {"return_pct": 0.001, "holding_days": 5},
            {"return_pct": 0.003, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["hit_rate"] == 1.0
        # avg = (0.001 + 0.003) / 2 = 0.002
        assert result["avg_return"] == 0.002
        assert result["total_return"] > 0

    def test_very_small_negative_returns(self):
        trades = [
            {"return_pct": -0.0001, "holding_days": 5},
            {"return_pct": -0.0002, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert result["hit_rate"] == 0.0
        assert result["total_return"] < 0


class TestProfitFactorEdgeCases:
    """Additional profit factor edge cases."""

    def test_zero_return_excluded_from_profit(self):
        """Zero return is in losses (r <= 0), so it adds 0 to gross_loss abs sum."""
        trades = [
            {"return_pct": 0.0, "holding_days": 5},
            {"return_pct": 10.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # gross_profit = 10, gross_loss = abs(0) = 0 (only r < 0 counted for loss)
        # Since zero is <= 0 for losses list, but only r < 0 for gross_loss calc
        # gross_loss = abs(sum(r for r in returns if r < 0)) = 0
        # profit_factor = inf capped to 999
        assert result["profit_factor"] == 999

    def test_profit_factor_many_small_wins_one_big_loss(self):
        trades = [
            {"return_pct": 1.0, "holding_days": 5},
            {"return_pct": 1.0, "holding_days": 5},
            {"return_pct": 1.0, "holding_days": 5},
            {"return_pct": -10.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # gross_profit = 3, gross_loss = 10 => PF = 0.3
        assert result["profit_factor"] == pytest.approx(0.3, abs=0.01)


class TestWinLossRatioEdgeCases:
    """Additional win/loss ratio scenarios."""

    def test_no_wins_all_losses(self):
        trades = [
            {"return_pct": -5.0, "holding_days": 5},
            {"return_pct": -10.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # avg_win = 0 (no wins), avg_loss = 7.5 => WLR = 0
        assert result["win_loss_ratio"] == 0

    def test_only_zero_returns(self):
        """All zero returns: no wins, losses have avg_loss of 0 => 0/0 => 0."""
        trades = [
            {"return_pct": 0.0, "holding_days": 5},
            {"return_pct": 0.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        # wins = [], losses = [0, 0]. avg_win=0, avg_loss=0. 0/0 => 0
        assert result["win_loss_ratio"] == 0


class TestOutputKeyCompleteness:
    """All expected keys are always present in the output."""

    EXPECTED_KEYS = {
        "total_trades", "hit_rate", "avg_return", "sharpe_ratio",
        "max_drawdown", "profit_factor", "win_loss_ratio", "total_return",
    }

    def test_empty_trades_has_all_keys(self):
        result = compute_backtest_metrics([])
        assert set(result.keys()) == self.EXPECTED_KEYS

    def test_single_trade_has_all_keys(self):
        result = compute_backtest_metrics([{"return_pct": 5.0, "holding_days": 5}])
        assert set(result.keys()) == self.EXPECTED_KEYS

    def test_multiple_trades_has_all_keys(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 5},
            {"return_pct": -3.0, "holding_days": 5},
        ]
        result = compute_backtest_metrics(trades)
        assert set(result.keys()) == self.EXPECTED_KEYS

    def test_invalid_trades_has_all_keys(self):
        trades = [{"holding_days": 5}]
        result = compute_backtest_metrics(trades)
        assert set(result.keys()) == self.EXPECTED_KEYS
