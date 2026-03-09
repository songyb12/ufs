"""Backtest performance metric calculations."""

import math


def compute_backtest_metrics(trades: list[dict]) -> dict:
    """Compute performance metrics from a list of closed trades.

    Each trade must have: return_pct (float), holding_days (int).

    Returns dict with: hit_rate, avg_return, sharpe_ratio, max_drawdown,
    profit_factor, win_loss_ratio, total_return, total_trades.
    """
    if not trades:
        return {
            "total_trades": 0,
            "hit_rate": None,
            "avg_return": None,
            "sharpe_ratio": None,
            "max_drawdown": None,
            "profit_factor": None,
            "win_loss_ratio": None,
            "total_return": None,
        }

    returns = [t["return_pct"] for t in trades if t.get("return_pct") is not None]
    if not returns:
        return {
            "total_trades": len(trades),
            "hit_rate": None,
            "avg_return": None,
            "sharpe_ratio": None,
            "max_drawdown": None,
            "profit_factor": None,
            "win_loss_ratio": None,
            "total_return": None,
        }

    # Hit rate
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    hit_rate = len(wins) / len(returns) if returns else 0

    # Average return
    avg_return = sum(returns) / len(returns)

    # Total return (compounded)
    total_return = 1.0
    for r in returns:
        total_return *= (1 + r / 100)
    total_return = (total_return - 1) * 100  # to percentage

    # Sharpe ratio (annualized, assuming ~252 trading days)
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(var_r) if var_r > 0 else 0

        # Estimate trades per year from average holding period
        avg_holding = sum(t.get("holding_days", 10) for t in trades) / len(trades)
        trades_per_year = 252 / max(avg_holding, 1)

        if std_r > 0:
            sharpe_ratio = (mean_r / std_r) * math.sqrt(trades_per_year)
        else:
            # Zero variance: all returns identical — Sharpe undefined
            sharpe_ratio = 0
        sharpe_ratio = max(-99, min(99, sharpe_ratio))  # Cap to reasonable range
    else:
        sharpe_ratio = 0

    # Max drawdown (equity curve based)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= (1 + r / 100)
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100
        max_dd = max(max_dd, dd)

    # Profit factor
    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    # Win/Loss ratio
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf") if avg_win > 0 else 0

    return {
        "total_trades": len(trades),
        "hit_rate": round(hit_rate, 4),
        "avg_return": round(avg_return, 4),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "max_drawdown": round(max_dd, 4),
        "profit_factor": round(min(profit_factor, 999), 4),
        "win_loss_ratio": round(min(win_loss_ratio, 999), 4),
        "total_return": round(total_return, 4),
    }
