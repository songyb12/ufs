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
