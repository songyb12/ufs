"""Tests for app.backtesting.metrics — backtest metric calculations."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.backtesting.metrics import compute_backtest_metrics


class TestComputeBacktestMetricsEmpty:
    def test_empty_trades(self):
        r = compute_backtest_metrics([])
        assert r["total_trades"] == 0
        assert r["hit_rate"] is None
        assert r["avg_return"] is None
        assert r["sharpe_ratio"] is None
        assert r["max_drawdown"] is None

    def test_no_valid_returns(self):
        trades = [{"holding_days": 10}, {"holding_days": 5}]
        r = compute_backtest_metrics(trades)
        assert r["total_trades"] == 2
        assert r["hit_rate"] is None


class TestComputeBacktestMetricsSingle:
    def test_single_winning_trade(self):
        trades = [{"return_pct": 10.0, "holding_days": 20}]
        r = compute_backtest_metrics(trades)
        assert r["total_trades"] == 1
        assert r["hit_rate"] == 1.0
        assert r["avg_return"] == 10.0
        assert r["total_return"] is not None
        assert r["max_drawdown"] == 0

    def test_single_losing_trade(self):
        trades = [{"return_pct": -5.0, "holding_days": 10}]
        r = compute_backtest_metrics(trades)
        assert r["hit_rate"] == 0.0
        assert r["avg_return"] == -5.0
        assert r["max_drawdown"] is not None


class TestComputeBacktestMetricsMultiple:
    def test_mixed_trades(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 20},
            {"return_pct": -5.0, "holding_days": 15},
            {"return_pct": 8.0, "holding_days": 25},
            {"return_pct": -3.0, "holding_days": 10},
            {"return_pct": 12.0, "holding_days": 30},
        ]
        r = compute_backtest_metrics(trades)
        assert r["total_trades"] == 5
        assert r["hit_rate"] == 0.6  # 3 wins out of 5
        assert r["avg_return"] is not None
        assert r["sharpe_ratio"] is not None
        assert r["max_drawdown"] is not None
        assert r["profit_factor"] is not None
        assert r["win_loss_ratio"] is not None

    def test_all_winning(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 10},
            {"return_pct": 8.0, "holding_days": 15},
            {"return_pct": 3.0, "holding_days": 20},
        ]
        r = compute_backtest_metrics(trades)
        assert r["hit_rate"] == 1.0
        assert r["profit_factor"] is not None
        assert r["max_drawdown"] == 0

    def test_all_losing(self):
        trades = [
            {"return_pct": -3.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 15},
            {"return_pct": -2.0, "holding_days": 20},
        ]
        r = compute_backtest_metrics(trades)
        assert r["hit_rate"] == 0.0
        assert r["profit_factor"] == 0
        assert r["max_drawdown"] is not None
        assert r["max_drawdown"] > 0  # max_drawdown is positive (absolute pct)

    def test_sharpe_capped(self):
        # Extreme positive returns with very low variance
        trades = [
            {"return_pct": 100.0, "holding_days": 5},
            {"return_pct": 100.0, "holding_days": 5},
            {"return_pct": 100.0, "holding_days": 5},
        ]
        r = compute_backtest_metrics(trades)
        if r["sharpe_ratio"] is not None:
            assert r["sharpe_ratio"] <= 99

    def test_total_return_compounding(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        # Compounded: (1.10)(0.95) - 1 = 0.045 = 4.5%
        assert r["total_return"] is not None
        assert abs(r["total_return"] - 4.5) < 0.5

    def test_max_drawdown_calculation(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": -15.0, "holding_days": 10},
            {"return_pct": 5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        assert r["max_drawdown"] is not None
        assert r["max_drawdown"] > 0  # max_drawdown is positive (absolute pct from peak)

    def test_profit_factor(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        assert r["profit_factor"] is not None
        assert r["profit_factor"] > 0  # gross_profit=10, gross_loss=5 → PF=2.0
        assert abs(r["profit_factor"] - 2.0) < 0.1

    def test_win_loss_ratio(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        assert r["win_loss_ratio"] is not None
        assert abs(r["win_loss_ratio"] - 2.0) < 0.1

    def test_zero_return_counts_as_loss(self):
        trades = [
            {"return_pct": 0.0, "holding_days": 10},
            {"return_pct": 5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        assert r["hit_rate"] == 0.5  # 0% is a loss (r <= 0)
