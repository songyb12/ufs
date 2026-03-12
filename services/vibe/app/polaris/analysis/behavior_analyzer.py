"""Agentic Behavior Analyzer — Multi-step prediction with DB tool loop.

Phase 3 upgrade: The analyzer can query the POLARIS DB to retrieve
historical events, past predictions, and profile data before making
predictions. This gives the LLM more context for better predictions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.config import settings
from app.polaris import repository as polaris_repo

logger = logging.getLogger("vibe.polaris.analysis.behavior_analyzer")

PREDICTION_SYSTEM_PROMPT = """당신은 정치 인물 행동 예측 전문가입니다.

주어진 인물의 인격 프로파일을 기반으로 **다음에 취할 가능성이 높은 행동**을 예측합니다.

## 예측 원칙
1. **프로파일 기반**: 과거 행동 패턴과 가치관에서 근거를 찾을 것
2. **구체성**: "강경할 것이다" 대신 "관세 25% → 35% 인상 가능성" 수준으로 기술
3. **시장 영향**: 각 예측에 대해 영향받을 섹터와 방향성 명시
4. **신뢰도**: 0.0~1.0 (과거 유사 패턴 빈도 기반)
5. **시간대**: short (1-2주), medium (1-3개월), long (3개월+)

## 도구 사용
- 예측 전에 get_figure_events, get_past_predictions 도구를 활용하여
  최근 이벤트와 과거 예측 적중률을 확인하세요.
- 충분한 정보를 수집한 후 save_predictions 도구로 예측을 저장하세요.

## 응답 형식
최소 3개, 최대 7개의 예측을 제시하세요."""

# Tools available to the analyzer agent
AGENT_TOOLS = [
    {
        "name": "get_figure_events",
        "description": "인물의 최근 이벤트 목록을 조회합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "조회할 이벤트 수 (기본 20)",
                    "default": 20,
                },
                "min_significance": {
                    "type": "integer",
                    "description": "최소 중요도 (1-5, 기본 2)",
                    "default": 2,
                },
            },
        },
    },
    {
        "name": "get_past_predictions",
        "description": "이 인물에 대한 과거 예측과 실제 결과를 조회합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "조회할 예측 수 (기본 10)",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "save_predictions",
        "description": "분석한 행동 예측을 구조화된 형식으로 저장합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "predictions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["action", "policy", "statement", "market_impact"],
                            },
                            "prediction": {"type": "string"},
                            "reasoning": {"type": "string"},
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                            "timeframe": {
                                "type": "string",
                                "enum": ["short", "medium", "long"],
                            },
                            "market_impact": {
                                "type": "object",
                                "properties": {
                                    "sectors": {"type": "array", "items": {"type": "string"}},
                                    "direction": {"type": "string", "enum": ["positive", "negative", "mixed"]},
                                    "magnitude": {"type": "string", "enum": ["high", "medium", "low"]},
                                    "description": {"type": "string"},
                                },
                            },
                        },
                        "required": ["type", "prediction", "reasoning", "confidence", "timeframe"],
                    },
                },
            },
            "required": ["predictions"],
        },
    },
]

MAX_TOOL_ROUNDS = 5  # Maximum agentic loop iterations


async def _handle_tool_call(
    tool_name: str,
    tool_input: dict,
    figure_id: str,
) -> str:
    """Execute a tool call and return the result as a string."""
    if tool_name == "get_figure_events":
        events = await polaris_repo.get_events(
            figure_id,
            limit=tool_input.get("limit", 20),
            min_significance=tool_input.get("min_significance", 2),
        )
        if not events:
            return "최근 등록된 이벤트가 없습니다."
        return json.dumps(events, ensure_ascii=False, indent=2)

    elif tool_name == "get_past_predictions":
        preds = await polaris_repo.get_predictions(
            figure_id,
            limit=tool_input.get("limit", 10),
        )
        if not preds:
            return "과거 예측 기록이 없습니다."

        # Add accuracy stats
        total = len(preds)
        confirmed = sum(1 for p in preds if p.get("status") == "confirmed")
        wrong = sum(1 for p in preds if p.get("status") == "wrong")
        pending = sum(1 for p in preds if p.get("status") == "pending")

        stats = (
            f"과거 예측 {total}건: 적중 {confirmed}, 오류 {wrong}, 대기 {pending}\n"
            f"적중률: {confirmed/max(confirmed+wrong,1)*100:.0f}%\n\n"
        )
        return stats + json.dumps(preds[:10], ensure_ascii=False, indent=2)

    return f"알 수 없는 도구: {tool_name}"


async def run_prediction(
    figure_name: str,
    profile_data: dict,
    topic: str = "",
    extra_context: str = "",
    figure_id: str = "",
) -> dict:
    """Generate behavior predictions using agentic tool loop.

    The LLM can query DB for historical events and past predictions
    before generating new predictions.
    """
    if not settings.LLM_API_KEY:
        return {"status": "error", "message": "LLM API 키가 설정되지 않았습니다."}

    try:
        import anthropic
    except ImportError:
        return {"status": "error", "message": "anthropic 패키지가 설치되지 않았습니다."}

    client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
    model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL

    # Build initial user message
    profile_str = json.dumps(profile_data, ensure_ascii=False, indent=2)
    if len(profile_str) > 8000:
        profile_str = profile_str[:8000] + "\n... (truncated)"

    parts = [
        f"## 인물: {figure_name}",
        f"\n## 인격 프로파일\n```json\n{profile_str}\n```",
    ]

    if topic:
        parts.append(f"\n## 분석 초점\n{topic}")
    if extra_context:
        parts.append(f"\n## 추가 컨텍스트\n{extra_context}")

    parts.append(
        "\n먼저 get_figure_events와 get_past_predictions 도구로 최근 데이터를 확인한 후, "
        "save_predictions 도구로 예측을 저장해주세요."
    )

    messages = [{"role": "user", "content": "\n".join(parts)}]

    try:
        for round_num in range(MAX_TOOL_ROUNDS):
            response = await client.messages.create(
                model=model,
                max_tokens=4096,
                system=PREDICTION_SYSTEM_PROMPT,
                messages=messages,
                tools=AGENT_TOOLS,
            )

            # Check for save_predictions (terminal tool)
            for block in response.content:
                if block.type == "tool_use" and block.name == "save_predictions":
                    return {
                        "status": "ok",
                        "predictions": block.input.get("predictions", []),
                        "metadata": {
                            "model": model,
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "topic": topic or "(general)",
                            "agent_rounds": round_num + 1,
                        },
                    }

            # Handle intermediate tool calls
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                # No tool calls — LLM responded with text only
                text_parts = [b.text for b in response.content if hasattr(b, "text")]
                return {
                    "status": "error",
                    "message": "LLM이 tool_use로 응답하지 않았습니다.",
                    "raw_text": "\n".join(text_parts),
                }

            # Build assistant message + tool results
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tc in tool_calls:
                result_str = await _handle_tool_call(tc.name, tc.input, figure_id)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})

        # Exhausted rounds
        return {
            "status": "error",
            "message": f"에이전트가 {MAX_TOOL_ROUNDS}회 반복 후에도 예측을 완료하지 못했습니다.",
        }

    except Exception as e:
        logger.error("Prediction failed for %s: %s", figure_name, e, exc_info=True)
        return {"status": "error", "message": str(e)}
