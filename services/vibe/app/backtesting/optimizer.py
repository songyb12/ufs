"""Parameter Optimizer - Grid search and random search over backtest parameters."""

import logging
import math
import random
from itertools import product
from typing import Any

from app.backtesting.engine import BacktestEngine
from app.config import Settings

logger = logging.getLogger("vibe.backtest.optimizer")


class ParameterOptimizer:
    """Grid search optimizer for scoring weights and thresholds."""

    # Default parameter grid
    DEFAULT_GRID = {
        "WEIGHT_TECHNICAL": [0.30, 0.35, 0.40],
        "WEIGHT_MACRO": [0.15, 0.20, 0.25],
        "WEIGHT_FUND_FLOW": [0.0, 0.20, 0.25, 0.30],
        "WEIGHT_FUNDAMENTAL": [0.10, 0.15, 0.20],
    }

    def __init__(self, config: Settings):
        self.config = config
        self.engine = BacktestEngine(config)

    async def optimize(
        self,
        market: str,
        start_date: str,
        end_date: str,
        param_grid: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Run backtests for each valid parameter combination.

        Returns list of results sorted by sharpe_ratio descending.
        """
        grid = param_grid or self.DEFAULT_GRID

        # Generate valid combinations (weights must sum to ~1.0)
        combinations = self._generate_valid_combinations(grid, market)

        logger.info(
            "Optimizer starting: %d valid combinations for %s [%s to %s]",
            len(combinations), market, start_date, end_date,
        )

        results = []
        for i, combo in enumerate(combinations):
            logger.info("Running combination %d/%d: %s", i + 1, len(combinations), combo)

            result = await self.engine.run(
                market=market,
                start_date=start_date,
                end_date=end_date,
                config_overrides=combo,
            )

            if result.get("metrics"):
                results.append({
                    "config": combo,
                    "metrics": result["metrics"],
                    "backtest_id": result["backtest_id"],
                })

        # Sort by sharpe_ratio descending (guard against NaN)
        def _safe_sharpe(r):
            v = r["metrics"].get("sharpe_ratio")
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return -999
            return v
        results.sort(key=_safe_sharpe, reverse=True)

        logger.info(
            "Optimizer completed: %d results. Best sharpe=%.2f",
            len(results),
            results[0]["metrics"].get("sharpe_ratio", 0) if results else 0,
        )

        return results

    def _generate_valid_combinations(
        self, grid: dict, market: str,
    ) -> list[dict]:
        """Generate parameter combinations where weights sum to ~1.0."""
        weight_keys = [k for k in grid.keys() if k.startswith("WEIGHT_")]
        non_weight_keys = [k for k in grid.keys() if not k.startswith("WEIGHT_")]

        valid = []

        if weight_keys:
            weight_values = [grid[k] for k in weight_keys]
            for combo in product(*weight_values):
                weight_dict = dict(zip(weight_keys, combo))

                # Check sum ≈ 1.0 (tolerance 0.05)
                total = sum(weight_dict.values())
                if abs(total - 1.0) > 0.05:
                    continue

                # For US market, fund_flow weight should be 0
                if market == "US" and weight_dict.get("WEIGHT_FUND_FLOW", 0) > 0:
                    continue

                # Add non-weight params
                if non_weight_keys:
                    nw_values = [grid[k] for k in non_weight_keys]
                    for nw_combo in product(*nw_values):
                        full = {**weight_dict, **dict(zip(non_weight_keys, nw_combo))}
                        valid.append(full)
                else:
                    valid.append(weight_dict)
        else:
            # Only non-weight params
            values = [grid[k] for k in non_weight_keys]
            for combo in product(*values):
                valid.append(dict(zip(non_weight_keys, combo)))

        return valid


# ════════════════════════════════════════════════════════════════
# SOXL-specific Random Search Optimizer
# ════════════════════════════════════════════════════════════════

# Continuous parameter ranges for random sampling
SOXL_PARAM_RANGES: dict[str, tuple[float, float, float]] = {
    # (min, max, step) — step used for rounding
    "rsi_entry": (25.0, 45.0, 1.0),
    "rsi_exit_partial": (55.0, 75.0, 1.0),
    "stop_loss_pct": (-12.0, -3.0, 0.5),
    "take_profit_pct": (8.0, 35.0, 1.0),
    "trailing_stop_pct": (2.0, 10.0, 0.5),
    "max_hold_days": (5, 40, 1),
    "cooldown_days": (0, 3, 1),
    "atr_stop_multiplier": (1.5, 4.0, 0.5),
    "vix_max_entry": (25.0, 40.0, 1.0),
}


def _sample_soxl_params() -> dict:
    """Sample a random SOXL parameter combination from defined ranges."""
    sampled = {}
    for param, (lo, hi, step) in SOXL_PARAM_RANGES.items():
        raw = random.uniform(lo, hi)
        # Snap to step grid
        sampled[param] = round(round(raw / step) * step, 4)
    # Integer params
    for k in ("max_hold_days", "cooldown_days"):
        sampled[k] = int(sampled[k])
    return sampled


class SoxlParameterOptimizer:
    """Random search optimizer for SOXL backtest parameters.

    Instead of exhaustive grid search, samples `max_iter` random parameter
    combinations and returns the top N results ranked by Sharpe ratio.
    """

    async def optimize(
        self,
        mode: str = "A",
        start_date: str | None = None,
        end_date: str | None = None,
        max_iter: int = 50,
        top_n: int = 5,
    ) -> dict:
        """Run random search optimization.

        Args:
            mode: Strategy mode (A/B/C/D).
            start_date: Backtest start (default: 1 year ago).
            end_date: Backtest end (default: today).
            max_iter: Number of random parameter samples to evaluate.
            top_n: Number of top results to return.

        Returns:
            dict with 'results' (top N), 'total_evaluated', 'mode', 'period'.
        """
        from datetime import datetime, timedelta
        from app.backtesting.soxl_engine import (
            SoxlBacktestEngine,
            SoxlBacktestParams,
            StrategyMode,
        )

        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (
                datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=365)
            ).strftime("%Y-%m-%d")

        try:
            strategy_mode = StrategyMode(mode.upper())
        except ValueError:
            return {"status": "failed", "error": f"Invalid mode '{mode}'"}

        engine = SoxlBacktestEngine()
        all_results = []
        evaluated = 0

        logger.info(
            "SOXL optimizer: mode=%s, max_iter=%d, top_n=%d, period=%s~%s",
            mode, max_iter, top_n, start_date, end_date,
        )

        for i in range(max_iter):
            sampled = _sample_soxl_params()
            params = SoxlBacktestParams()
            for k, v in sampled.items():
                if hasattr(params, k):
                    setattr(params, k, type(getattr(params, k))(v))

            result = await engine.run(start_date, end_date, strategy_mode, params)
            evaluated += 1

            if result.get("status") == "completed" and result.get("metrics"):
                metrics = result["metrics"]
                sharpe = metrics.get("sharpe_ratio")
                if sharpe is not None and not (isinstance(sharpe, float) and math.isnan(sharpe)):
                    all_results.append({
                        "params": sampled,
                        "metrics": {
                            "sharpe_ratio": metrics.get("sharpe_ratio"),
                            "sortino_ratio": metrics.get("sortino_ratio"),
                            "max_drawdown": metrics.get("max_drawdown"),
                            "total_return": metrics.get("total_return"),
                            "hit_rate": metrics.get("hit_rate"),
                            "total_trades": metrics.get("total_trades"),
                            "profit_factor": metrics.get("profit_factor"),
                            "avg_return": metrics.get("avg_return"),
                        },
                    })

        # Sort by Sharpe descending
        all_results.sort(
            key=lambda r: r["metrics"].get("sharpe_ratio") or -999,
            reverse=True,
        )

        top_results = all_results[:top_n]

        logger.info(
            "SOXL optimizer done: %d evaluated, %d valid, top sharpe=%.2f",
            evaluated, len(all_results),
            top_results[0]["metrics"]["sharpe_ratio"] if top_results else 0,
        )

        return {
            "status": "ok",
            "mode": mode.upper(),
            "period": f"{start_date} ~ {end_date}",
            "total_evaluated": evaluated,
            "valid_results": len(all_results),
            "top_n": len(top_results),
            "results": top_results,
        }
