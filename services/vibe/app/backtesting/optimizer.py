"""Parameter Optimizer - Grid search over weight/threshold combinations."""

import logging
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
        import math
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
