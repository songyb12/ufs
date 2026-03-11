"""Agentic Portfolio Review — Multi-step LLM analysis with tool use.

The LLM autonomously decides which data to gather by calling tools,
then synthesizes a comprehensive Korean portfolio review report.

Architecture:
  User: "포트폴리오 리뷰해줘"
    → Agent loop (max 5 iterations)
    → Available tools: portfolio, signals, macro, guru, sectors, performance, events
    → Final: structured Korean report
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.database import repositories as repo

logger = logging.getLogger("vibe.briefing.agent_review")

MAX_ITERATIONS = 5

# ---------------------------------------------------------------------------
# Tool definitions for the agent
# ---------------------------------------------------------------------------

AGENT_TOOLS = [
    {
        "name": "get_portfolio_positions",
        "description": "Get all current portfolio holdings with entry prices, position sizes, and sectors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "portfolio_id": {"type": "integer", "description": "Portfolio group ID (default: 1)", "default": 1},
            },
        },
    },
    {
        "name": "get_signals_for_symbol",
        "description": "Get the latest trading signal for a specific stock symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock symbol (e.g., '005930' or 'AAPL')"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_all_latest_signals",
        "description": "Get latest trading signals for all watched stocks. Use this for a broad market overview.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "enum": ["KR", "US"], "description": "Market filter"},
            },
        },
    },
    {
        "name": "get_macro_snapshot",
        "description": "Get current macro indicators: VIX, DXY, USD/KRW, yields, oil, gold.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_performance_summary",
        "description": "Get signal performance statistics: hit rates, average returns at T+5 and T+20.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "enum": ["KR", "US"], "description": "Market filter"},
            },
        },
    },
    {
        "name": "get_upcoming_events",
        "description": "Get upcoming economic events and earnings for the next 7 days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "enum": ["KR", "US"], "description": "Market filter"},
            },
        },
    },
    {
        "name": "get_exit_history",
        "description": "Get recent position exit history with P&L.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of recent exits to retrieve", "default": 10},
            },
        },
    },
    {
        "name": "get_sentiment",
        "description": "Get market sentiment data: Fear & Greed index, put/call ratio.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

AGENT_SYSTEM_PROMPT = """당신은 VIBE 투자 분석 시스템의 포트폴리오 리뷰 에이전트입니다.

사용자의 포트폴리오를 심층 분석하여 한국어 리포트를 작성합니다.
필요한 데이터를 도구(tool)를 통해 수집한 후, 종합적인 분석을 제공하세요.

리포트 구조:
1. 포트폴리오 현황 요약 (보유 종목, 총 투자금, 섹터 분포)
2. 개별 종목 분석 (시그널, 수익률, 리스크)
3. 매크로 환경 평가 (현재 시장 상태가 포트폴리오에 미치는 영향)
4. 리스크 플래그 (주의가 필요한 포지션)
5. 액션 아이템 (구체적 행동 제안)

규칙:
- 투자 조언이 아닌 객관적 데이터 기반 해설
- 핵심 수치를 반드시 포함
- 한국어로 작성"""


# ---------------------------------------------------------------------------
# Tool execution dispatcher
# ---------------------------------------------------------------------------

async def _execute_tool(name: str, arguments: dict) -> str:
    """Execute an agent tool and return JSON result."""
    try:
        if name == "get_portfolio_positions":
            portfolio_id = arguments.get("portfolio_id", 1)
            positions = await repo.get_portfolio_state(portfolio_id=portfolio_id)
            return json.dumps(positions[:20], ensure_ascii=False, default=str)

        elif name == "get_signals_for_symbol":
            symbol = arguments["symbol"]
            signals = await repo.get_latest_signals()
            match = [s for s in signals if s["symbol"] == symbol]
            if match:
                return json.dumps(match[0], ensure_ascii=False, default=str)
            return json.dumps({"error": f"No signal found for {symbol}"})

        elif name == "get_all_latest_signals":
            market = arguments.get("market")
            signals = await repo.get_latest_signals(market=market)
            return json.dumps(signals[:30], ensure_ascii=False, default=str)

        elif name == "get_macro_snapshot":
            macro = await repo.get_latest_macro()
            return json.dumps(macro or {}, ensure_ascii=False, default=str)

        elif name == "get_performance_summary":
            market = arguments.get("market")
            perf = await repo.get_performance_summary(market=market)
            return json.dumps(perf, ensure_ascii=False, default=str)

        elif name == "get_upcoming_events":
            market = arguments.get("market")
            events = await repo.get_upcoming_events(market=market, days_ahead=7) if market else []
            # If no market specified, get both
            if not market:
                events_kr = await repo.get_upcoming_events(market="KR", days_ahead=7)
                events_us = await repo.get_upcoming_events(market="US", days_ahead=7)
                events = events_kr + events_us
            return json.dumps(events[:15], ensure_ascii=False, default=str)

        elif name == "get_exit_history":
            limit = arguments.get("limit", 10)
            exits = await repo.get_exit_history(limit=limit)
            return json.dumps(exits, ensure_ascii=False, default=str)

        elif name == "get_sentiment":
            sentiment = await repo.get_latest_sentiment()
            return json.dumps(sentiment or {}, ensure_ascii=False, default=str)

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as e:
        logger.error("Agent tool '%s' failed: %s", name, e, exc_info=True)
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

async def run_portfolio_review(
    request: str = "포트폴리오를 종합 리뷰해주세요.",
    portfolio_id: int = 1,
) -> dict[str, Any]:
    """Run the agentic portfolio review loop.

    The LLM autonomously calls tools to gather data, then synthesizes a report.
    """
    if not settings.LLM_API_KEY:
        return {
            "status": "error",
            "message": "LLM API 키가 설정되지 않았습니다.",
        }

    try:
        import anthropic
    except ImportError:
        return {"status": "error", "message": "anthropic 패키지가 설치되지 않았습니다."}

    client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
    model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL

    # Initial message
    messages = [
        {"role": "user", "content": request},
    ]

    tool_calls_log: list[dict] = []

    for iteration in range(MAX_ITERATIONS):
        logger.info("[Agent] Iteration %d/%d", iteration + 1, MAX_ITERATIONS)

        response = await client.messages.create(
            model=model,
            max_tokens=3000,
            system=AGENT_SYSTEM_PROMPT,
            messages=messages,
            tools=AGENT_TOOLS,
        )

        # Check if the model wants to use tools
        if response.stop_reason == "tool_use":
            # Process all tool calls in this response
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_args = block.input
                    logger.info("[Agent] Calling tool: %s(%s)", tool_name, json.dumps(tool_args, ensure_ascii=False))

                    result = await _execute_tool(tool_name, tool_args)
                    tool_calls_log.append({
                        "iteration": iteration + 1,
                        "tool": tool_name,
                        "args": tool_args,
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Add assistant response and tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            # Agent is done — extract final text
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            return {
                "status": "ok",
                "review": final_text,
                "iterations": iteration + 1,
                "tool_calls": tool_calls_log,
                "metadata": {
                    "model": model,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            }
        else:
            logger.warning("[Agent] Unexpected stop_reason: %s", response.stop_reason)
            break

    # Max iterations reached — extract whatever text we have
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text

    return {
        "status": "ok",
        "review": final_text or "리뷰 생성 중 최대 반복 횟수에 도달했습니다.",
        "iterations": MAX_ITERATIONS,
        "tool_calls": tool_calls_log,
        "metadata": {
            "model": model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "max_iterations_reached": True,
        },
    }
