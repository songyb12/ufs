"""Stage 6: Signal Generation - Aggregate scoring -> BUY/SELL/HOLD."""

import logging
from typing import Any

from app.config import Settings
from app.indicators.scoring import compute_aggregate_signal, compute_technical_score
from app.indicators.weekly import compute_timeframe_multiplier
from app.models.enums import SignalType
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s6")


class SignalGenerationStage(BaseStage):
    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s6_signal_generation"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return (
            "s2_technical_analysis" in context
            and "s5_hard_limit" in context
        )

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        tech_data = context["s2_technical_analysis"].data.get("per_symbol", {})
        hard_limits = context["s5_hard_limit"].data.get("overrides", {})

        # Macro score (from S3)
        macro_result = context.get("s3_macro_analysis")
        macro_score_normalized = 0.0
        if macro_result:
            # Convert -1..+1 macro score to -100..+100 range
            macro_score_normalized = macro_result.data.get("macro_score", 0.0) * 100

        # Fund flow scores (from S4, KR only)
        fund_flow_data = {}
        s4 = context.get("s4_fund_flow")
        if s4 and s4.status not in ("skipped", "failed"):
            fund_flow_data = s4.data.get("per_symbol", {})

        # Fundamental scores (from S2b, Phase C)
        fundamental_data = {}
        s2b = context.get("s2b_fundamental_analysis")
        if s2b and s2b.status not in ("skipped", "failed"):
            fundamental_data = s2b.data.get("per_symbol", {})

        # Weekly analysis (from S2c, Phase C)
        weekly_data = {}
        s2c = context.get("s2c_weekly_analysis")
        if s2c and s2c.status not in ("skipped", "failed"):
            weekly_data = s2c.data.get("per_symbol", {})

        # Sentiment score (from S3b, Phase D)
        sentiment_score = 0.0
        s3b = context.get("s3b_sentiment_analysis")
        if s3b and s3b.status == "success":
            sentiment_score = s3b.data.get("sentiment_score", 0.0)

        per_symbol_signals: dict[str, dict] = {}

        for symbol, indicators in tech_data.items():
            # Technical score
            tech_score = compute_technical_score(indicators)

            # Fund flow score (KR only)
            ff_score = None
            if symbol in fund_flow_data:
                ff_score = fund_flow_data[symbol].get("fund_flow_score", 0.0)

            # Fundamental score (Phase C)
            fund_score = 0.0
            if symbol in fundamental_data:
                fund_score = fundamental_data[symbol].get("fundamental_score", 0.0)

            # Weekly trend (Phase C) - compute multiplier after initial signal
            weekly_trend = "neutral"
            if symbol in weekly_data:
                weekly_trend = weekly_data[symbol].get("trend_direction", "neutral")

            # First pass: get preliminary signal for timeframe alignment
            prelim_signal, _ = compute_aggregate_signal(
                technical_score=tech_score,
                macro_score=macro_score_normalized,
                fund_flow_score=ff_score,
                market=market,
                config=self.config,
                fundamental_score=fund_score,
                sentiment_score=sentiment_score,
                timeframe_multiplier=1.0,
            )

            # Compute timeframe multiplier based on preliminary signal
            tf_multiplier = compute_timeframe_multiplier(prelim_signal, weekly_trend)

            # Final aggregate signal with timeframe alignment
            raw_signal, raw_score = compute_aggregate_signal(
                technical_score=tech_score,
                macro_score=macro_score_normalized,
                fund_flow_score=ff_score,
                market=market,
                config=self.config,
                fundamental_score=fund_score,
                sentiment_score=sentiment_score,
                timeframe_multiplier=tf_multiplier,
            )

            # Apply Hard Limit override (non-negotiable)
            hl = hard_limits.get(symbol, {})
            if hl.get("hard_limit_triggered") and raw_signal == SignalType.BUY:
                final_signal = SignalType.HOLD
            else:
                final_signal = raw_signal

            signal_data = {
                "symbol": symbol,
                "market": market,
                "raw_signal": raw_signal,
                "raw_score": raw_score,
                "final_signal": final_signal,
                "hard_limit_triggered": hl.get("hard_limit_triggered", False),
                "hard_limit_reason": hl.get("hard_limit_reason"),
                "rsi_value": indicators.get("rsi_14"),
                "disparity_value": indicators.get("disparity_20"),
                "technical_score": tech_score,
                "macro_score": macro_score_normalized,
                "fund_flow_score": ff_score,
                "fundamental_score": fund_score,
                "weekly_trend": weekly_trend,
                "timeframe_multiplier": tf_multiplier,
                "rationale": _build_rationale(
                    symbol, raw_signal, final_signal,
                    tech_score, macro_score_normalized, ff_score,
                    fund_score, weekly_trend, tf_multiplier, hl,
                ),
            }

            per_symbol_signals[symbol] = signal_data

            log_fn = logger.warning if hl.get("hard_limit_triggered") else logger.info
            log_fn(
                "[S6] %s: %s (raw=%s, score=%.1f, RSI=%.1f, Fund=%.1f, WkTrend=%s, HL=%s)",
                symbol, final_signal, raw_signal, raw_score,
                indicators.get("rsi_14", 0), fund_score,
                weekly_trend,
                "YES" if hl.get("hard_limit_triggered") else "NO",
            )

        return StageResult(
            stage_name=self.name,
            status="success",
            data={"per_symbol": per_symbol_signals},
        )


def _build_rationale(
    symbol: str,
    raw_signal: SignalType,
    final_signal: SignalType,
    tech_score: float,
    macro_score: float,
    ff_score: float | None,
    fund_score: float,
    weekly_trend: str,
    tf_multiplier: float,
    hard_limit: dict,
) -> str:
    parts = [f"Tech={tech_score:+.1f}", f"Macro={macro_score:+.1f}"]
    if ff_score is not None:
        parts.append(f"FundFlow={ff_score:+.1f}")
    if fund_score != 0:
        parts.append(f"Fund={fund_score:+.1f}")
    if weekly_trend != "neutral":
        parts.append(f"WkTrend={weekly_trend}(×{tf_multiplier:.1f})")

    rationale = f"Scores: {', '.join(parts)}"

    if hard_limit.get("hard_limit_triggered"):
        rationale += f" | HARD LIMIT: {raw_signal}->{final_signal} ({hard_limit['hard_limit_reason']})"

    return rationale
