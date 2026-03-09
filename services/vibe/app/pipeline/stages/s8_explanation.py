"""Stage 8: Korean Signal Explanation Generator.

Dual-mode: rule-based templates (always) + LLM-enhanced rich analysis (optional).
Generates human-readable Korean explanations for each signal.
"""

import json
import logging
from typing import Any

from app.utils.formatting import fmt_float as _fmt

from app.config import Settings
from app.models.enums import SignalType
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s8")

EXPLANATION_SYSTEM_PROMPT = """당신은 한국어 투자 해설가입니다.
각 종목의 분석 결과를 개인 투자자가 이해할 수 있는 2~3문장 한국어 해설로 작성하세요.
전문 용어를 최소화하고, 핵심 판단 근거와 주의점을 명확히 전달하세요.
반드시 JSON 형식으로 응답: {"종목코드1": "해설...", "종목코드2": "해설..."}"""


class SignalExplanationStage(BaseStage):
    """Stage 8: Korean signal explanation generator."""

    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s8_explanation"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return (
            "s7_red_team" in context
            or "s6_signal_generation" in context
        )

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        if not self.config.EXPLANATION_ALWAYS_ENABLED:
            return StageResult(
                stage_name=self.name,
                status="skipped",
                data={"reason": "Explanation disabled"},
            )

        # Get final signals (prefer S7 over S6)
        s7 = context.get("s7_red_team")
        s6 = context.get("s6_signal_generation")
        source = s7 if s7 and s7.status == "success" else s6
        if not source:
            return StageResult(
                stage_name=self.name,
                status="skipped",
                data={"reason": "No signal data available"},
            )

        per_symbol = source.data.get("per_symbol", {})
        symbol_names = context.get("symbol_names", {})

        # Macro context for explanation
        macro_result = context.get("s3_macro_analysis")
        macro_score = 0.0
        if macro_result and macro_result.data:
            macro_score = macro_result.data.get("macro_score", 0.0) * 100

        # Sentiment context
        sentiment_result = context.get("s3b_sentiment_analysis")
        sentiment_score = 0
        if sentiment_result and sentiment_result.status == "success":
            sentiment_score = sentiment_result.data.get("sentiment_score", 0)

        result_data: dict[str, dict] = {}

        # Phase 1: Rule-based explanation (always)
        for symbol, signal in per_symbol.items():
            name = symbol_names.get(symbol, symbol)
            explanation_rule = _generate_rule_based_explanation(
                name=name,
                signal=signal,
                macro_score=macro_score,
                sentiment_score=sentiment_score,
                market=market,
            )
            result_data[symbol] = {
                **signal,
                "explanation_rule": explanation_rule,
                "explanation_llm": None,
            }

        # Phase 2: LLM batch explanation (optional)
        if self.config.LLM_EXPLANATION_ENABLED and self.config.LLM_API_KEY:
            try:
                llm_explanations = await self._generate_llm_explanations(
                    per_symbol, symbol_names, context,
                )
                if llm_explanations:
                    for symbol, text in llm_explanations.items():
                        if symbol in result_data:
                            result_data[symbol]["explanation_llm"] = text
                    logger.info(
                        "[S8] LLM explanations generated for %d symbols",
                        len(llm_explanations),
                    )
            except Exception as e:
                logger.error("[S8] LLM explanation failed, using rule-based: %s", e, exc_info=True)

        logger.info("[S8] Explanations generated for %d symbols", len(result_data))

        return StageResult(
            stage_name=self.name,
            status="success",
            data={"per_symbol": result_data},
        )

    async def _generate_llm_explanations(
        self,
        per_symbol: dict[str, dict],
        symbol_names: dict[str, str],
        context: dict,
    ) -> dict[str, str] | None:
        """Batch LLM call for all symbols in ONE request."""
        lines = []
        for symbol, signal in per_symbol.items():
            name = symbol_names.get(symbol, symbol)
            lines.append(
                f"[{name}({symbol})] Signal: {signal.get('final_signal', 'HOLD')}, "
                f"Score: {signal.get('raw_score', 0):+.1f}, "
                f"RSI: {_fmt(signal.get('rsi_value'))}, "
                f"Disp: {_fmt(signal.get('disparity_value'))}%, "
                f"Fund: {signal.get('fundamental_score', 0):+.0f}, "
                f"Weekly: {signal.get('weekly_trend', 'N/A')}, "
                f"Conf: {(signal.get('confidence') if signal.get('confidence') is not None else 1.0):.0%}"
            )

        prompt = (
            f"Market: {context.get('market', 'N/A')}, "
            f"Date: {context.get('date', 'N/A')}\n\n"
            f"다음 종목별 분석 결과를 2~3문장 한국어 해설로 작성하세요:\n\n"
            + "\n".join(lines)
        )

        provider = self.config.LLM_PROVIDER

        if provider == "anthropic":
            return await self._call_anthropic(prompt)
        elif provider == "openai":
            return await self._call_openai(prompt)
        else:
            logger.warning("[S8] Unknown LLM provider: %s", provider)
            return None

    async def _call_anthropic(self, prompt: str) -> dict[str, str] | None:
        """Call Anthropic Claude API for batch explanation (native async)."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.config.LLM_API_KEY)
            model = self.config.LLM_EXPLANATION_MODEL or self.config.LLM_MODEL
            response = await client.messages.create(
                model=model,
                max_tokens=4000,
                system=EXPLANATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("[S8] LLM response not valid JSON, skipping")
            return None
        except Exception as e:
            logger.error("[S8] Anthropic API call failed: %s", e, exc_info=True)
            return None

    async def _call_openai(self, prompt: str) -> dict[str, str] | None:
        """Call OpenAI API for batch explanation (native async)."""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.config.LLM_API_KEY)
            model = self.config.LLM_EXPLANATION_MODEL or self.config.LLM_MODEL
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("[S8] LLM response not valid JSON, skipping")
            return None
        except Exception as e:
            logger.error("[S8] OpenAI API call failed: %s", e, exc_info=True)
            return None


def _generate_rule_based_explanation(
    name: str,
    signal: dict,
    macro_score: float,
    sentiment_score: float,
    market: str,
) -> str:
    """Generate Korean explanation using rule-based templates."""
    final_signal = signal.get("final_signal", "HOLD")
    rsi = signal.get("rsi_value")
    disparity = signal.get("disparity_value")
    fund_score = signal.get("fundamental_score", 0)
    weekly_trend = signal.get("weekly_trend", "neutral")
    confidence = signal.get("confidence", 1.0)
    hard_limit = signal.get("hard_limit_triggered", False)

    parts = []

    # RSI interpretation
    if rsi is not None:
        if rsi < 30:
            parts.append(f"RSI {rsi:.0f}로 과매도 구간 진입")
        elif rsi < 40:
            parts.append(f"RSI {rsi:.0f}로 과매도 접근 중")
        elif rsi < 50:
            parts.append(f"RSI {rsi:.0f}로 중립 하단")
        elif rsi < 60:
            parts.append(f"RSI {rsi:.0f}로 중립")
        elif rsi < 70:
            parts.append(f"RSI {rsi:.0f}로 과매수 접근")
        else:
            parts.append(f"RSI {rsi:.0f}로 과매수 구간")

    # Disparity interpretation
    if disparity is not None:
        disp_text = ""
        if disparity > 105:
            disp_text = f"이격도 {disparity:.1f}%로 고평가"
        elif disparity < 95:
            disp_text = f"이격도 {disparity:.1f}%로 저평가"
        if disp_text:
            if parts:
                parts[-1] += f", {disp_text}"
            else:
                parts.append(disp_text)

    # Fundamental
    if fund_score > 30:
        parts.append("펀더멘털 우수(저PER+고ROE)")
    elif fund_score > 0:
        parts.append("펀더멘털 양호")
    elif fund_score > -30:
        parts.append("펀더멘털 보통")
    elif fund_score != 0:
        parts.append("펀더멘털 취약")

    # Weekly trend
    trend_map = {
        "bullish": "주봉 상승추세와 일치",
        "bearish": "주봉 하락추세와 역행 주의",
        "neutral": "주봉 중립",
    }
    parts.append(trend_map.get(weekly_trend, "주봉 중립"))

    # Macro context
    if macro_score > 20:
        macro_desc = "매크로 우호적 환경"
    elif macro_score > 0:
        macro_desc = "매크로 소폭 긍정"
    elif macro_score > -20:
        macro_desc = "매크로 약세"
    else:
        macro_desc = "매크로 악화 주의"

    # Signal conclusion
    conclusion_map = {
        SignalType.BUY: "매수 유효",
        SignalType.SELL: "매도 권고",
        SignalType.HOLD: "관망 추천",
        "BUY": "매수 유효",
        "SELL": "매도 권고",
        "HOLD": "관망 추천",
    }
    conclusion = conclusion_map.get(final_signal, "관망 추천")

    # Hard limit override note
    if hard_limit:
        hl_reason = signal.get("hard_limit_reason", "")
        conclusion = f"Hard Limit 발동으로 관망({hl_reason})"

    # Low confidence note
    if confidence < 0.5 and final_signal in (SignalType.BUY, "BUY"):
        conclusion = "신뢰도 부족으로 관망 전환"

    # Connector: use "에도" when signal is BUY but macro is negative
    if final_signal in (SignalType.BUY, "BUY") and macro_score < 0:
        connector = f"{macro_desc}에도 {conclusion}"
    else:
        connector = f"{macro_desc}. {conclusion}"

    # Assemble
    explanation = f"{name}: {', '.join(parts)}. {connector}."

    # Add confidence note for BUY signals
    if final_signal in (SignalType.BUY, "BUY") and confidence < 0.7:
        explanation += f" (확신도 {confidence:.0%}로 주의 필요)"

    return explanation
