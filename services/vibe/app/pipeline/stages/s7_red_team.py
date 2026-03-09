"""Stage 7: LLM Red-Team Validation.

Dual-mode: Rule-based (always) + LLM adversarial review (optional).
The LLM acts as a skeptical senior analyst challenging BUY signals.
"""

import json
import logging
from typing import Any

from app.config import Settings
from app.database import repositories as repo
from app.models.enums import SignalType
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s7")

# LLM Red-Team system prompt
RED_TEAM_SYSTEM_PROMPT = """You are a skeptical senior investment analyst. Your job is to challenge BUY recommendations and find reasons why they might fail.

For each BUY signal, analyze the provided context and:
1. Identify 3 specific risks that could cause this trade to fail
2. Rate your overall concern level: LOW, MEDIUM, or HIGH
3. If HIGH concern, suggest the signal should be downgraded

Respond in JSON format:
{
    "concern_level": "LOW|MEDIUM|HIGH",
    "risk_flags": ["risk1", "risk2", "risk3"],
    "reasoning": "brief explanation",
    "recommended_action": "MAINTAIN|DOWNGRADE"
}"""


class LLMRedTeamStage(BaseStage):
    """Stage 7: LLM-enhanced Red-Team validation."""

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

        # Sentiment data (Phase D)
        sentiment_result = context.get("s3b_sentiment_analysis")
        sentiment_score = 0
        if sentiment_result and sentiment_result.status == "success":
            sentiment_score = sentiment_result.data.get("sentiment_score", 0)

        per_symbol: dict[str, dict] = {}

        for symbol, signal in s6_data.items():
            warnings = []
            confidence = 1.0
            final_signal = signal["final_signal"]

            rsi = signal.get("rsi_value")
            disparity = signal.get("disparity_value")
            vix = macro_data.get("raw_data", {}).get("vix") if macro_data else None

            # ── Phase 1: Rule-based adversarial checks (always run) ──

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

                # Check 5: Sentiment extreme greed (Phase D)
                if sentiment_score < -30:
                    warnings.append(f"Sentiment {sentiment_score:.0f} extreme greed - contrarian sell")
                    confidence -= 0.15

            elif final_signal == SignalType.SELL:
                # Check: Oversold bounce risk
                if rsi is not None and rsi < 25:
                    warnings.append(f"RSI {rsi:.1f} deeply oversold - bounce risk")
                    confidence -= 0.10

                # Check: VIX extreme (capitulation = potential reversal)
                if vix is not None and vix > 35:
                    warnings.append(f"VIX {vix:.1f} extreme - capitulation risk")
                    confidence -= 0.15

                # Check: Sentiment extreme fear (Phase D)
                if sentiment_score > 30:
                    warnings.append(f"Sentiment {sentiment_score:.0f} extreme fear - contrarian buy")
                    confidence -= 0.10

            # ── Phase 2: LLM adversarial review (optional) ──
            llm_result = None
            if (self.config.LLM_RED_TEAM_ENABLED
                    and final_signal == SignalType.BUY
                    and confidence > 0.5):
                try:
                    llm_result = await self._llm_review(symbol, signal, context)
                    if llm_result:
                        if llm_result.get("concern_level") == "HIGH":
                            confidence -= 0.25
                            warnings.append(
                                f"LLM: HIGH concern - {llm_result.get('reasoning', 'N/A')[:60]}"
                            )
                        elif llm_result.get("concern_level") == "MEDIUM":
                            confidence -= 0.10
                            warnings.append(
                                f"LLM: MEDIUM concern - {llm_result.get('reasoning', 'N/A')[:60]}"
                            )

                        # Store LLM review to DB for audit
                        await repo.insert_llm_review({
                            "run_id": context.get("run_id", ""),
                            "symbol": symbol,
                            "market": market,
                            "review_date": context.get("date", ""),
                            "input_context": json.dumps(
                                self._build_llm_context(signal, context),
                                default=str,
                            ),
                            "llm_response": json.dumps(llm_result, default=str),
                            "model_used": self.config.LLM_MODEL,
                            "risk_flags": json.dumps(
                                llm_result.get("risk_flags", [])
                            ),
                            "confidence_adjustment": -0.25 if llm_result.get("concern_level") == "HIGH" else -0.10 if llm_result.get("concern_level") == "MEDIUM" else 0,
                            "signal_override": llm_result.get("recommended_action"),
                        })
                except Exception as e:
                    logger.error("[S7] LLM review failed for %s: %s", symbol, e, exc_info=True)
                    warnings.append("LLM review failed")

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

    async def _llm_review(
        self, symbol: str, signal: dict, context: dict,
    ) -> dict | None:
        """Call LLM for adversarial review of a BUY signal."""
        llm_context = self._build_llm_context(signal, context)
        prompt = f"""Analyze this BUY signal for {symbol}:

Technical Score: {signal.get('technical_score', 0):+.1f}
Macro Score: {signal.get('macro_score', 0):+.1f}
Fundamental Score: {signal.get('fundamental_score', 0):+.1f}
RSI: {signal.get('rsi_value', 'N/A')}
Disparity: {signal.get('disparity_value', 'N/A')}%
Weekly Trend: {signal.get('weekly_trend', 'N/A')}
Raw Score: {signal.get('raw_score', 0):+.1f}

Market: {context.get('market', 'N/A')}
Date: {context.get('date', 'N/A')}

Challenge this BUY recommendation. Find 3 reasons it could fail."""

        provider = self.config.LLM_PROVIDER

        if provider == "anthropic":
            return await self._call_anthropic(prompt)
        elif provider == "openai":
            return await self._call_openai(prompt)
        else:
            logger.warning("[S7] Unknown LLM provider: %s", provider)
            return None

    async def _call_anthropic(self, prompt: str) -> dict | None:
        """Call Anthropic Claude API (native async)."""
        text = ""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.config.LLM_API_KEY)
            response = await client.messages.create(
                model=self.config.LLM_MODEL,
                max_tokens=500,
                system=RED_TEAM_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            return json.loads(text)
        except json.JSONDecodeError:
            return {"concern_level": "LOW", "risk_flags": [], "reasoning": text[:200]}
        except Exception as e:
            logger.error("Anthropic API call failed: %s", e, exc_info=True)
            return None

    async def _call_openai(self, prompt: str) -> dict | None:
        """Call OpenAI API (native async)."""
        text = ""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.config.LLM_API_KEY)
            response = await client.chat.completions.create(
                model=self.config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": RED_TEAM_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content
            return json.loads(text)
        except json.JSONDecodeError:
            return {"concern_level": "LOW", "risk_flags": [], "reasoning": text[:200]}
        except Exception as e:
            logger.error("OpenAI API call failed: %s", e, exc_info=True)
            return None

    def _build_llm_context(self, signal: dict, context: dict) -> dict:
        """Build context dict for LLM review."""
        return {
            "symbol": signal.get("symbol"),
            "market": context.get("market"),
            "date": context.get("date"),
            "technical_score": signal.get("technical_score"),
            "macro_score": signal.get("macro_score"),
            "fundamental_score": signal.get("fundamental_score"),
            "rsi": signal.get("rsi_value"),
            "disparity": signal.get("disparity_value"),
            "weekly_trend": signal.get("weekly_trend"),
            "raw_score": signal.get("raw_score"),
        }
