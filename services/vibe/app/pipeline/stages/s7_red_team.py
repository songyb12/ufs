"""Stage 7: Red-Team Validation - Rule-based adversarial review.

Phase 1: Rule-based checks for known dangerous patterns.
Phase 2 (future): LLM-based adversarial prompt for deeper analysis.
"""

import logging
from typing import Any

from app.config import Settings
from app.models.enums import SignalType
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s7")


class RedTeamStage(BaseStage):
    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s7_red_team"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return "s6_signal_generation" in context

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        if not self.config.RED_TEAM_ENABLED:
            return StageResult(
                stage_name=self.name,
                status="skipped",
                data={"reason": "Red-Team validation disabled"},
            )

        s6_data = context["s6_signal_generation"].data.get("per_symbol", {})
        macro_result = context.get("s3_macro_analysis")
        macro_data = macro_result.data if macro_result else {}

        per_symbol: dict[str, dict] = {}

        for symbol, signal in s6_data.items():
            warnings = []
            confidence = 1.0
            final_signal = signal["final_signal"]

            rsi = signal.get("rsi_value")
            disparity = signal.get("disparity_value")
            vix = macro_data.get("raw_data", {}).get("vix") if macro_data else None

            # ── Rule-based adversarial checks ──

            if final_signal == SignalType.BUY:
                # Check 1: RSI approaching overbought
                if rsi is not None and rsi > 55:
                    warnings.append(f"RSI {rsi:.1f} approaching overbought zone")
                    confidence -= 0.15

                # Check 2: VIX elevated
                if vix is not None and vix > 25:
                    warnings.append(f"VIX {vix:.1f} elevated - market stress")
                    confidence -= 0.20

                # Check 3: Negative macro environment
                macro_score = signal.get("macro_score", 0)
                if macro_score < -20:
                    warnings.append(f"Macro score {macro_score:.1f} negative - headwind")
                    confidence -= 0.15

                # Check 4: Disparity stretched
                if disparity is not None and disparity > 103:
                    warnings.append(f"Disparity {disparity:.1f}% stretched above MA20")
                    confidence -= 0.10

            elif final_signal == SignalType.SELL:
                # Check: Oversold bounce risk
                if rsi is not None and rsi < 25:
                    warnings.append(f"RSI {rsi:.1f} deeply oversold - bounce risk")
                    confidence -= 0.10

                # Check: VIX extreme (capitulation = potential reversal)
                if vix is not None and vix > 35:
                    warnings.append(f"VIX {vix:.1f} extreme - capitulation risk")
                    confidence -= 0.15

            # Confidence floor
            confidence = max(0.1, min(1.0, confidence))

            # Downgrade BUY to HOLD if confidence too low
            if final_signal == SignalType.BUY and confidence < 0.5:
                warnings.append(
                    f"Confidence {confidence:.0%} too low - downgraded to HOLD"
                )
                final_signal = SignalType.HOLD

            per_symbol[symbol] = {
                **signal,
                "final_signal": final_signal,
                "confidence": round(confidence, 2),
                "red_team_warning": " | ".join(warnings) if warnings else None,
            }

            if warnings:
                logger.warning(
                    "[S7] %s: %s (conf=%.0f%%) - %s",
                    symbol, final_signal, confidence * 100,
                    " | ".join(warnings),
                )

        return StageResult(
            stage_name=self.name,
            status="success",
            data={"per_symbol": per_symbol},
        )
