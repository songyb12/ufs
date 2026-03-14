"""Backtest performance metric calculations.

Extended metrics include: Sortino ratio, Calmar ratio, CAGR, max consecutive
win/loss, expectancy, recovery factor, payoff ratio, Ulcer Index, exposure time.
"""

import math
from datetime import datetime


def compute_backtest_metrics(trades: list[dict], start_date: str | None = None, end_date: str | None = None) -> dict:
    """Compute performance metrics from a list of closed trades.

    Each trade must have: return_pct (float), holding_days (int).
    Optional: entry_date, exit_date (for CAGR/exposure calculation).

    Returns dict with: hit_rate, avg_return, sharpe_ratio, sortino_ratio,
    calmar_ratio, max_drawdown, profit_factor, win_loss_ratio, total_return,
    total_trades, cagr, max_consecutive_wins, max_consecutive_losses,
    avg_win, avg_loss, expectancy, recovery_factor, payoff_ratio,
    ulcer_index, exposure_pct, avg_holding_days, median_return,
    best_trade, worst_trade.
    """
    _empty = {
        "total_trades": 0,
        "hit_rate": None,
        "avg_return": None,
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "calmar_ratio": None,
        "max_drawdown": None,
        "profit_factor": None,
        "win_loss_ratio": None,
        "total_return": None,
        "cagr": None,
        "max_consecutive_wins": 0,
        "max_consecutive_losses": 0,
        "avg_win": None,
        "avg_loss": None,
        "expectancy": None,
        "recovery_factor": None,
        "payoff_ratio": None,
        "ulcer_index": None,
        "exposure_pct": None,
        "avg_holding_days": None,
        "median_return": None,
        "best_trade": None,
        "worst_trade": None,
    }

    if not trades:
        return _empty

    returns = [t["return_pct"] for t in trades if t.get("return_pct") is not None]
    if not returns:
        _empty["total_trades"] = len(trades)
        return _empty

    # ── Basic stats ──
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    hit_rate = len(wins) / len(returns) if returns else 0
    avg_return = sum(returns) / len(returns)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0

    # Median return
    sorted_returns = sorted(returns)
    n = len(sorted_returns)
    if n % 2 == 0:
        median_return = (sorted_returns[n // 2 - 1] + sorted_returns[n // 2]) / 2
    else:
        median_return = sorted_returns[n // 2]

    # Best / worst trade
    best_trade = max(returns)
    worst_trade = min(returns)

    # ── Total return (compounded) ──
    total_return = 1.0
    for r in returns:
        total_return *= (1 + r / 100)
    total_return = (total_return - 1) * 100  # to percentage

    # ── CAGR ──
    cagr = None
    total_days = sum(t.get("holding_days", 0) for t in trades)
    if total_days > 0:
        years = total_days / 365.25
        if years > 0 and (1 + total_return / 100) > 0:
            cagr = ((1 + total_return / 100) ** (1 / years) - 1) * 100

    # ── Average holding days ──
    holding_days_list = [t.get("holding_days", 0) for t in trades if t.get("holding_days") is not None]
    avg_holding_days = sum(holding_days_list) / len(holding_days_list) if holding_days_list else None

    # ── Sharpe ratio (annualized, ~252 trading days) ──
    sharpe_ratio = 0.0
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(var_r) if var_r > 0 else 0

        avg_holding = sum(t.get("holding_days", 10) for t in trades) / len(trades)
        trades_per_year = 252 / max(avg_holding, 1)

        if std_r > 0:
            sharpe_ratio = (mean_r / std_r) * math.sqrt(trades_per_year)
        sharpe_ratio = max(-99, min(99, sharpe_ratio))

    # ── Sortino ratio (annualized, downside deviation only) ──
    sortino_ratio = 0.0
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        downside_returns = [min(0, r) for r in returns]
        downside_var = sum(d ** 2 for d in downside_returns) / len(returns)
        downside_dev = math.sqrt(downside_var) if downside_var > 0 else 0

        avg_holding = sum(t.get("holding_days", 10) for t in trades) / len(trades)
        trades_per_year = 252 / max(avg_holding, 1)

        if downside_dev > 0:
            sortino_ratio = (mean_r / downside_dev) * math.sqrt(trades_per_year)
        sortino_ratio = max(-99, min(99, sortino_ratio))

    # ── Max drawdown (equity curve based) ──
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    equity_curve = [1.0]
    for r in returns:
        equity *= (1 + r / 100)
        equity_curve.append(equity)
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100
        max_dd = max(max_dd, dd)

    # ── Calmar ratio (CAGR / max_drawdown) ──
    calmar_ratio = None
    if cagr is not None and max_dd > 0:
        calmar_ratio = cagr / max_dd
        calmar_ratio = max(-99, min(99, calmar_ratio))

    # ── Ulcer Index (RMS of drawdowns) ──
    ulcer_index = 0.0
    if len(equity_curve) > 1:
        dd_squared_sum = 0.0
        running_peak = equity_curve[0]
        for e in equity_curve[1:]:
            running_peak = max(running_peak, e)
            dd_pct = ((running_peak - e) / running_peak * 100) if running_peak > 0 else 0
            dd_squared_sum += dd_pct ** 2
        ulcer_index = math.sqrt(dd_squared_sum / (len(equity_curve) - 1))

    # ── Profit factor ──
    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    # ── Win/Loss ratio ──
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf") if avg_win > 0 else 0

    # ── Payoff ratio (same as win_loss_ratio conceptually, but based on median) ──
    median_win = _median([r for r in returns if r > 0]) if wins else 0
    median_loss = abs(_median([r for r in returns if r < 0])) if [r for r in returns if r < 0] else 0
    payoff_ratio = median_win / median_loss if median_loss > 0 else float("inf") if median_win > 0 else 0

    # ── Expectancy (avg profit per trade considering hit rate) ──
    expectancy = (hit_rate * avg_win) - ((1 - hit_rate) * avg_loss)

    # ── Recovery factor (total_return / max_drawdown) ──
    recovery_factor = None
    if max_dd > 0 and total_return is not None:
        recovery_factor = total_return / max_dd

    # ── Max consecutive wins/losses ──
    max_con_wins = 0
    max_con_losses = 0
    cur_wins = 0
    cur_losses = 0
    for r in returns:
        if r > 0:
            cur_wins += 1
            cur_losses = 0
            max_con_wins = max(max_con_wins, cur_wins)
        else:
            cur_losses += 1
            cur_wins = 0
            max_con_losses = max(max_con_losses, cur_losses)

    # ── Exposure percentage (days in market / total calendar days) ──
    exposure_pct = None
    if start_date and end_date:
        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d")
            dt_end = datetime.strptime(end_date, "%Y-%m-%d")
            calendar_days = (dt_end - dt_start).days
            if calendar_days > 0:
                exposure_pct = (total_days / calendar_days) * 100
        except (ValueError, TypeError):
            pass

    return {
        "total_trades": len(trades),
        "hit_rate": round(hit_rate, 4),
        "avg_return": round(avg_return, 4),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "sortino_ratio": round(sortino_ratio, 4),
        "calmar_ratio": round(min(calmar_ratio, 999), 4) if calmar_ratio is not None else None,
        "max_drawdown": round(max_dd, 4),
        "profit_factor": round(min(profit_factor, 999), 4),
        "win_loss_ratio": round(min(win_loss_ratio, 999), 4),
        "total_return": round(total_return, 4),
        "cagr": round(cagr, 4) if cagr is not None else None,
        "max_consecutive_wins": max_con_wins,
        "max_consecutive_losses": max_con_losses,
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "expectancy": round(expectancy, 4),
        "recovery_factor": round(min(recovery_factor, 999), 4) if recovery_factor is not None else None,
        "payoff_ratio": round(min(payoff_ratio, 999), 4),
        "ulcer_index": round(ulcer_index, 4),
        "exposure_pct": round(exposure_pct, 2) if exposure_pct is not None else None,
        "avg_holding_days": round(avg_holding_days, 1) if avg_holding_days is not None else None,
        "median_return": round(median_return, 4),
        "best_trade": round(best_trade, 4),
        "worst_trade": round(worst_trade, 4),
    }


def _median(values: list[float]) -> float:
    """Compute median of a list of floats."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return s[n // 2]


def compute_monthly_returns(trades: list[dict]) -> list[dict]:
    """Aggregate trade returns by month.

    Returns list of {month: 'YYYY-MM', return_pct, trade_count, win_rate}.
    """
    monthly: dict[str, list[float]] = {}
    for t in trades:
        exit_date = t.get("exit_date") or t.get("entry_date")
        if not exit_date:
            continue
        month = exit_date[:7]  # 'YYYY-MM'
        ret = t.get("return_pct")
        if ret is not None:
            monthly.setdefault(month, []).append(ret)

    result = []
    for month in sorted(monthly.keys()):
        rets = monthly[month]
        wins = sum(1 for r in rets if r > 0)
        compounded = 1.0
        for r in rets:
            compounded *= (1 + r / 100)
        result.append({
            "month": month,
            "return_pct": round((compounded - 1) * 100, 2),
            "trade_count": len(rets),
            "win_rate": round(wins / len(rets), 4) if rets else 0,
        })
    return result


def compute_exit_reason_stats(trades: list[dict]) -> list[dict]:
    """Statistics grouped by exit reason.

    Returns list of {reason, count, avg_return, win_rate, avg_holding_days}.
    """
    by_reason: dict[str, list[dict]] = {}
    for t in trades:
        reason = t.get("exit_reason", "unknown")
        by_reason.setdefault(reason, []).append(t)

    result = []
    for reason in sorted(by_reason.keys()):
        trades_group = by_reason[reason]
        rets = [t["return_pct"] for t in trades_group if t.get("return_pct") is not None]
        wins = sum(1 for r in rets if r > 0)
        days = [t.get("holding_days", 0) for t in trades_group]
        result.append({
            "reason": reason,
            "count": len(trades_group),
            "avg_return": round(sum(rets) / len(rets), 2) if rets else 0,
            "win_rate": round(wins / len(rets), 4) if rets else 0,
            "avg_holding_days": round(sum(days) / len(days), 1) if days else 0,
        })
    return result


def compute_drawdown_periods(trades: list[dict]) -> list[dict]:
    """Identify drawdown periods from trade sequence.

    Returns list of {start_date, end_date, depth_pct, duration_trades, recovered}.
    """
    returns = [t.get("return_pct", 0) for t in trades]
    dates = [t.get("exit_date", t.get("entry_date", "")) for t in trades]

    equity = 1.0
    peak = 1.0
    peak_idx = 0
    drawdowns = []
    in_dd = False
    dd_start_idx = 0
    dd_max_depth = 0.0

    for i, r in enumerate(returns):
        equity *= (1 + r / 100)
        if equity >= peak:
            if in_dd:
                # Drawdown recovered
                drawdowns.append({
                    "start_date": dates[dd_start_idx] if dd_start_idx < len(dates) else "",
                    "end_date": dates[i] if i < len(dates) else "",
                    "depth_pct": round(dd_max_depth, 2),
                    "duration_trades": i - dd_start_idx,
                    "recovered": True,
                })
                in_dd = False
            peak = equity
            peak_idx = i
        else:
            dd = (peak - equity) / peak * 100
            if not in_dd:
                in_dd = True
                dd_start_idx = peak_idx + 1
                dd_max_depth = dd
            else:
                dd_max_depth = max(dd_max_depth, dd)

    # If still in drawdown at end
    if in_dd:
        drawdowns.append({
            "start_date": dates[dd_start_idx] if dd_start_idx < len(dates) else "",
            "end_date": dates[-1] if dates else "",
            "depth_pct": round(dd_max_depth, 2),
            "duration_trades": len(returns) - dd_start_idx,
            "recovered": False,
        })

    return drawdowns
