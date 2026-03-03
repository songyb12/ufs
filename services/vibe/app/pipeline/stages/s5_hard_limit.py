"""Stage 5: Hard Limit Safety Check - RSI/Disparity ceiling enforcement.

This is the SAFETY-CRITICAL stage. Non-negotiable overrides.
If Hard Limit triggers, Stage 6 MUST output HOLD regardless of all other scores.
"""

import logging
from typing import Any

from app.config import Settings
from app.models.enums import Market
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s5")


class HardLimitStage(BaseStage):
    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s5_hard_limit"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return "s2_technical_analysis" in context

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        tech_data = context["s2_technical_analysis"].data
        per_symbol = tech_data.get("per_symbol", {})

        overrides: dict[str, dict] = {}
        warnings = []

        for symbol, indicators in per_symbol.items():
            rsi = indicators.get("rsi_14")
            disparity = indicators.get("disparity_20")
            triggered = False
            reasons = []

            # Rule 1: Absolute RSI ceiling (all markets)
            if rsi is not None and rsi > self.config.RSI_HARD_LIMIT:
                triggered = True
                reasons.append(
                    f"RSI {rsi:.1f} > {self.config.RSI_HARD_LIMIT} ceiling"
                )

            # Rule 2: Market-specific buy threshold
            if market == Market.KR and rsi is not None and rsi > self.config.RSI_BUY_THRESHOLD_KR:
                triggered = True
                reasons.append(
                    f"KR RSI {rsi:.1f} > {self.config.RSI_BUY_THRESHOLD_KR} buy threshold"
                )
            elif market == Market.US and rsi is not None and rsi > self.config.RSI_BUY_THRESHOLD_US:
                triggered = True
                reasons.append(
                    f"US RSI {rsi:.1f} > {self.config.RSI_BUY_THRESHOLD_US} buy threshold"
                )

            # Rule 3: Disparity ceiling (all markets)
            if disparity is not None and disparity > self.config.DISPARITY_HARD_LIMIT:
                triggered = True
                reasons.append(
                    f"20D Disparity {disparity:.1f}% > {self.config.DISPARITY_HARD_LIMIT}% ceiling"
                )

            overrides[symbol] = {
                "hard_limit_triggered": triggered,
                "hard_limit_reason": " | ".join(reasons) if reasons else None,
                "forced_signal": "HOLD" if triggered else None,
            }

            if triggered:
                warnings.append(f"Hard limit: {symbol} -> {' | '.join(reasons)}")
                logger.warning("[S5] HARD LIMIT: %s -> %s", symbol, " | ".join(reasons))

        triggered_count = sum(1 for v in overrides.values() if v["hard_limit_triggered"])
        logger.info(
            "[S5] Hard limit check: %d/%d symbols triggered",
            triggered_count, len(per_symbol),
        )

        return StageResult(
            stage_name=self.name,
            status="success",
            data={"overrides": overrides},
            warnings=warnings,
        )
