"""Stage 2c: Weekly Analysis - Multi-timeframe confirmation."""

import logging
from typing import Any

from app.config import Settings
from app.indicators.weekly import compute_weekly_indicators
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s2c")


class WeeklyAnalysisStage(BaseStage):
    """Stage 2c: Compute weekly indicators for timeframe alignment."""

    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s2c_weekly_analysis"

    def validate_input(self, context: dict[str, Any]) -> bool:
        s1 = context.get("s1_data_collection")
        return s1 is not None and s1.status in ("success", "partial")

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        s1_data = context["s1_data_collection"].data
        ohlcv_data = s1_data.get("ohlcv_data", {})

        per_symbol: dict[str, dict] = {}
        warnings = []

        for symbol, df in ohlcv_data.items():
            try:
                weekly = compute_weekly_indicators(df)
                if weekly is None:
                    warnings.append(f"{symbol}: insufficient data for weekly analysis")
                    per_symbol[symbol] = {"trend_direction": "neutral"}
                    continue

                per_symbol[symbol] = weekly

                logger.debug(
                    "[S2c] %s: weekly_trend=%s, weekly_rsi=%.1f",
                    symbol, weekly["trend_direction"],
                    weekly.get("rsi_14_weekly") or 0,
                )

            except Exception as e:
                logger.error("[S2c] %s: weekly analysis failed - %s", symbol, e)
                per_symbol[symbol] = {"trend_direction": "neutral"}

        logger.info("[S2c] Weekly analysis for %d symbols", len(per_symbol))

        return StageResult(
            stage_name=self.name,
            status="success" if per_symbol else "partial",
            data={"per_symbol": per_symbol},
            warnings=warnings,
        )
