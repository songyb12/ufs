"""Stage 9: Portfolio Scenario Generator.

For HELD stocks: sell conditions, target prices, risk scenarios.
For BUY signals on non-held stocks: entry scenarios with stop-loss.
Dual-mode: rule-based (always) + LLM-enhanced (optional).
"""

import json
import logging
from typing import Any

from app.config import Settings
from app.database import repositories as repo
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s9")

SCENARIO_SYSTEM_PROMPT = """당신은 한국어 포트폴리오 어드바이저입니다.
각 종목에 대해 2~3문장의 행동 가능한 시나리오를 작성하세요.
포함할 내용: 핵심 리스크, 가격 기반 행동 트리거, 시간 전망.
반드시 JSON 형식으로 응답: {"held": {"종목코드": "시나리오..."}, "entry": {"종목코드": "시나리오..."}}"""


class PortfolioScenarioStage(BaseStage):
    """Stage 9: Portfolio buy/sell scenario generator."""

    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s9_portfolio_scenarios"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return (
            "s7_red_team" in context
            or "s6_signal_generation" in context
        )

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        if not self.config.PORTFOLIO_SCENARIOS_ENABLED:
            return StageResult(
                stage_name=self.name,
                status="skipped",
                data={"reason": "Portfolio scenarios disabled"},
            )

        # Fetch portfolio state from DB
        holdings = await repo.get_portfolio_state(market=market)
        holdings_map = {h["symbol"]: h for h in holdings}

        # Get final signals (prefer S7 over S6)
        s7 = context.get("s7_red_team")
        s6 = context.get("s6_signal_generation")
        source = s7 if s7 and s7.status == "success" else s6
        per_symbol = source.data.get("per_symbol", {}) if source else {}

        symbol_names = context.get("symbol_names", {})

        # Get current prices from S1
        s1 = context.get("s1_data_collection")

        held_scenarios: dict[str, dict] = {}
        entry_scenarios: dict[str, dict] = {}

        # Generate scenarios for HELD stocks
        for symbol, holding in holdings_map.items():
            signal = per_symbol.get(symbol, {})
            current_price = _get_current_price(s1, symbol)
            if current_price is None:
                continue

            name = symbol_names.get(symbol, symbol)
            scenario = _build_hold_scenario(
                symbol=symbol,
                name=name,
                holding=holding,
                signal=signal,
                current_price=current_price,
                config=self.config,
            )
            held_scenarios[symbol] = scenario

            logger.info(
                "[S9] HELD %s: P&L=%+.1f%%, signal=%s",
                symbol, scenario["pnl_pct"], scenario.get("final_signal", "N/A"),
            )

        # Generate entry scenarios for BUY signals on NON-held stocks
        for symbol, signal in per_symbol.items():
            if signal.get("final_signal") in ("BUY",) and symbol not in holdings_map:
                current_price = _get_current_price(s1, symbol)
                if current_price is None:
                    continue

                name = symbol_names.get(symbol, symbol)
                scenario = _build_entry_scenario(
                    symbol=symbol,
                    name=name,
                    signal=signal,
                    current_price=current_price,
                    config=self.config,
                )
                entry_scenarios[symbol] = scenario

                logger.info(
                    "[S9] ENTRY %s: price=%.0f, conf=%.0f%%",
                    symbol, current_price, scenario.get("confidence", 0) * 100,
                )

        # Optional LLM enrichment
        if (self.config.LLM_SCENARIO_ENABLED
                and self.config.LLM_API_KEY
                and (held_scenarios or entry_scenarios)):
            try:
                llm_result = await self._generate_llm_scenarios(
                    held_scenarios, entry_scenarios, symbol_names, context,
                )
                if llm_result:
                    for symbol, text in llm_result.get("held", {}).items():
                        if symbol in held_scenarios:
                            held_scenarios[symbol]["scenario_llm"] = text
                    for symbol, text in llm_result.get("entry", {}).items():
                        if symbol in entry_scenarios:
                            entry_scenarios[symbol]["scenario_llm"] = text
                    logger.info("[S9] LLM scenarios generated")
            except Exception as e:
                logger.error("[S9] LLM scenario generation failed: %s", e)

        # Store scenarios to DB
        try:
            scenario_rows = []
            for symbol, s in held_scenarios.items():
                scenario_rows.append({
                    "run_id": context.get("run_id", ""),
                    "symbol": symbol,
                    "market": market,
                    "scenario_date": context.get("date", ""),
                    "scenario_type": "held",
                    "current_price": s.get("current_price"),
                    "entry_price": s.get("entry_price"),
                    "pnl_pct": s.get("pnl_pct"),
                    "scenarios_json": json.dumps(s.get("scenarios", []), ensure_ascii=False),
                    "scenario_rule": s.get("scenario_rule"),
                    "scenario_llm": s.get("scenario_llm"),
                    "target_prices_json": json.dumps(s.get("target_prices", {})),
                })
            for symbol, s in entry_scenarios.items():
                scenario_rows.append({
                    "run_id": context.get("run_id", ""),
                    "symbol": symbol,
                    "market": market,
                    "scenario_date": context.get("date", ""),
                    "scenario_type": "entry",
                    "current_price": s.get("current_price"),
                    "entry_price": None,
                    "pnl_pct": None,
                    "scenarios_json": json.dumps(s.get("scenarios", []), ensure_ascii=False),
                    "scenario_rule": s.get("scenario_rule"),
                    "scenario_llm": s.get("scenario_llm"),
                    "target_prices_json": json.dumps(s.get("target_prices", {})),
                })
            if scenario_rows:
                await repo.insert_portfolio_scenarios(scenario_rows)
        except Exception as e:
            logger.error("[S9] Failed to store scenarios: %s", e)

        logger.info(
            "[S9] Scenarios: %d held, %d entry opportunities",
            len(held_scenarios), len(entry_scenarios),
        )

        return StageResult(
            stage_name=self.name,
            status="success",
            data={
                "held_scenarios": held_scenarios,
                "entry_scenarios": entry_scenarios,
                "holdings_count": len(holdings),
            },
        )

    async def _generate_llm_scenarios(
        self,
        held: dict, entry: dict,
        symbol_names: dict, context: dict,
    ) -> dict | None:
        """Batch LLM call for scenario generation."""
        lines = ["## 보유 종목"]
        for symbol, s in held.items():
            name = symbol_names.get(symbol, symbol)
            lines.append(
                f"[{name}({symbol})] 진입가: {s.get('entry_price', 0):,.0f}, "
                f"현재가: {s.get('current_price', 0):,.0f}, "
                f"수익률: {s.get('pnl_pct', 0):+.1f}%, "
                f"Signal: {s.get('final_signal', 'N/A')}"
            )
        lines.append("\n## 신규 매수 후보")
        for symbol, s in entry.items():
            name = symbol_names.get(symbol, symbol)
            lines.append(
                f"[{name}({symbol})] 현재가: {s.get('current_price', 0):,.0f}, "
                f"Score: {s.get('raw_score', 0):+.1f}, "
                f"Conf: {s.get('confidence', 1.0):.0%}"
            )

        prompt = (
            f"Market: {context.get('market')}, Date: {context.get('date')}\n\n"
            + "\n".join(lines)
            + "\n\n각 종목에 대해 2~3문장 시나리오를 작성하세요."
        )

        provider = self.config.LLM_PROVIDER

        if provider == "anthropic":
            return await self._call_anthropic(prompt)
        elif provider == "openai":
            return await self._call_openai(prompt)
        return None

    async def _call_anthropic(self, prompt: str) -> dict | None:
        import asyncio

        config = self.config

        def _call():
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
                response = client.messages.create(
                    model=config.LLM_MODEL,
                    max_tokens=4000,
                    system=SCENARIO_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text
                return json.loads(text)
            except json.JSONDecodeError:
                logger.warning("[S9] LLM response not valid JSON")
                return None
            except Exception as e:
                logger.error("[S9] Anthropic API failed: %s", e)
                return None

        return await asyncio.to_thread(_call)

    async def _call_openai(self, prompt: str) -> dict | None:
        import asyncio

        config = self.config

        def _call():
            try:
                import openai

                client = openai.OpenAI(api_key=config.LLM_API_KEY)
                response = client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": SCENARIO_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=4000,
                    response_format={"type": "json_object"},
                )
                text = response.choices[0].message.content
                return json.loads(text)
            except json.JSONDecodeError:
                return None
            except Exception as e:
                logger.error("[S9] OpenAI API failed: %s", e)
                return None

        return await asyncio.to_thread(_call)


def _get_current_price(s1, symbol: str) -> float | None:
    """Extract latest close price from S1 data collection result."""
    if not s1 or not s1.data:
        return None
    ohlcv_data = s1.data.get("ohlcv_data", {})
    df = ohlcv_data.get(symbol)
    if df is not None and not df.empty:
        return float(df.iloc[-1]["close"])
    return None


def _build_hold_scenario(
    symbol: str,
    name: str,
    holding: dict,
    signal: dict,
    current_price: float,
    config: Settings,
) -> dict:
    """Generate sell/hold/accumulate scenarios for a held position."""
    entry_price = holding.get("entry_price") or current_price
    pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0

    rsi = signal.get("rsi_value")
    final_signal = signal.get("final_signal", "HOLD")
    confidence = signal.get("confidence", 1.0)

    stop_loss_pct = abs(config.BACKTEST_STOP_LOSS_PCT)
    stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
    target_10 = entry_price * 1.10
    target_20 = entry_price * 1.20

    scenarios = []

    # Scenario A: Profit-taking
    if pnl_pct > 15:
        scenarios.append({
            "type": "profit_take",
            "condition": f"수익률 {pnl_pct:+.1f}% - 부분 익절 구간",
            "action": "50% 물량 매도 후 잔여 트레일링 스탑",
        })
    elif pnl_pct > 10:
        scenarios.append({
            "type": "trailing_stop",
            "condition": f"수익률 {pnl_pct:+.1f}% - 트레일링 스탑 설정 권고",
            "action": f"손절가를 매입가(₩{entry_price:,.0f}) 이상으로 상향",
        })

    # Scenario B: Stop-loss
    if pnl_pct < -stop_loss_pct:
        scenarios.append({
            "type": "stop_loss",
            "condition": f"손절 라인({-stop_loss_pct:.0f}%) 하회, 현재 {pnl_pct:+.1f}%",
            "action": "즉시 전량 매도 검토",
        })
    elif pnl_pct < 0:
        distance = abs(pnl_pct - (-stop_loss_pct))
        scenarios.append({
            "type": "stop_approach",
            "condition": f"손실 {pnl_pct:+.1f}%, 손절까지 {distance:.1f}%p",
            "action": f"₩{stop_loss_price:,.0f} 이탈 시 매도",
        })

    # Scenario C: Signal-based
    if final_signal == "SELL":
        scenarios.append({
            "type": "signal_sell",
            "condition": "파이프라인 SELL 시그널 발생",
            "action": "시그널 기반 매도 검토",
        })
    elif final_signal == "BUY" and pnl_pct > -3:
        scenarios.append({
            "type": "accumulate",
            "condition": f"보유 중 추가 BUY 시그널 (확신도: {confidence:.0%})",
            "action": "추가 매수 검토 (비중 확대)",
        })

    # Scenario D: RSI warning
    if rsi is not None and rsi > 65:
        scenarios.append({
            "type": "overbought_warning",
            "condition": f"RSI {rsi:.0f} 과매수 접근",
            "action": "단기 조정 대비 트레일링 스탑 설정",
        })
    elif rsi is not None and rsi < 25:
        scenarios.append({
            "type": "oversold_bounce",
            "condition": f"RSI {rsi:.0f} 극심한 과매도 - 반등 가능성",
            "action": "손절보다 추가 매수 기회 검토",
        })

    # Build Korean summary
    scenario_rule = _format_hold_summary_kr(name, scenarios, pnl_pct, current_price, entry_price)

    return {
        "symbol": symbol,
        "name": name,
        "entry_price": entry_price,
        "current_price": current_price,
        "pnl_pct": round(pnl_pct, 2),
        "final_signal": final_signal,
        "confidence": confidence,
        "scenarios": scenarios,
        "target_prices": {
            "stop_loss": round(stop_loss_price),
            "target_10pct": round(target_10),
            "target_20pct": round(target_20),
        },
        "scenario_rule": scenario_rule,
        "scenario_llm": None,
    }


def _build_entry_scenario(
    symbol: str,
    name: str,
    signal: dict,
    current_price: float,
    config: Settings,
) -> dict:
    """Generate entry scenario for a BUY signal on a non-held stock."""
    raw_score = signal.get("raw_score", 0)
    confidence = signal.get("confidence", 1.0)

    stop_loss_pct = abs(config.BACKTEST_STOP_LOSS_PCT)
    stop_loss_price = current_price * (1 - stop_loss_pct / 100)
    target_price = current_price * 1.10

    risk = current_price - stop_loss_price
    reward = target_price - current_price
    rr_ratio = reward / risk if risk > 0 else 0

    position_rec = signal.get("position_recommendation", {})
    recommended_amount = position_rec.get("recommended_amount", 0)

    scenarios = [{
        "type": "new_entry",
        "condition": f"BUY 시그널 (score: {raw_score:+.1f}, 확신도: {confidence:.0%})",
        "action": f"진입가 ₩{current_price:,.0f}, 손절 ₩{stop_loss_price:,.0f}",
    }]

    scenario_rule = _format_entry_summary_kr(
        name, current_price, stop_loss_price, target_price,
        confidence, rr_ratio, recommended_amount,
    )

    return {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "final_signal": "BUY",
        "raw_score": raw_score,
        "confidence": confidence,
        "scenarios": scenarios,
        "target_prices": {
            "entry": round(current_price),
            "stop_loss": round(stop_loss_price),
            "target_10pct": round(target_price),
        },
        "rr_ratio": round(rr_ratio, 2),
        "recommended_amount": recommended_amount,
        "scenario_rule": scenario_rule,
        "scenario_llm": None,
    }


def _format_hold_summary_kr(
    name: str, scenarios: list, pnl_pct: float,
    current_price: float, entry_price: float,
) -> str:
    """Format Korean summary for held position."""
    if pnl_pct > 15:
        return (
            f"{name}: 수익률 {pnl_pct:+.1f}%로 부분 익절 구간. "
            f"50% 매도 후 트레일링 스탑 권고."
        )
    elif pnl_pct > 5:
        return (
            f"{name}: 수익 {pnl_pct:+.1f}% 양호. "
            f"목표가 ₩{entry_price * 1.1:,.0f} 도달 시 부분 익절, 추세 유지 시 홀딩."
        )
    elif pnl_pct > -3:
        return (
            f"{name}: 손익 {pnl_pct:+.1f}%로 보합 구간. "
            f"시그널 방향 확인 후 대응. 손절 라인 준수."
        )
    elif pnl_pct > -5:
        return (
            f"{name}: 손실 {pnl_pct:+.1f}%로 손절 라인 근접. "
            f"추가 하락 시 전량 매도 필요."
        )
    else:
        return (
            f"{name}: 손실 {pnl_pct:+.1f}%로 손절 라인 하회. "
            f"즉시 전량 매도 검토."
        )


def _format_entry_summary_kr(
    name: str, current: float, stop: float, target: float,
    confidence: float, rr_ratio: float, amount: float,
) -> str:
    """Format Korean summary for entry opportunity."""
    amount_str = f", 추천 투자금 ₩{amount:,.0f}" if amount > 0 else ""
    return (
        f"{name}: 진입가 ₩{current:,.0f}, 손절 ₩{stop:,.0f}, "
        f"목표 ₩{target:,.0f} (R:R {rr_ratio:.1f}:1, 확신도 {confidence:.0%})"
        f"{amount_str}"
    )
