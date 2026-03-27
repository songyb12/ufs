"""Briefing generator — LLM-powered or rule-based fallback."""

import json
import logging
from datetime import datetime

from app.config import settings
from app.db import get_sync_db
from app.models import BriefingResponse, SignalLevel, SignalResult

logger = logging.getLogger("vibe2.briefing.generator")

# ---------------------------------------------------------------------------
# Tool-use schema for structured output
# ---------------------------------------------------------------------------

BRIEFING_TOOL = {
    "name": "create_briefing",
    "description": "구조화된 SOXL 투자 브리핑을 생성합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "1~2문장 한국어 시장 요약",
            },
            "action": {
                "type": "string",
                "description": "구체적 투자 행동 권고",
            },
            "risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "향후 1~2주 주요 리스크 이벤트 리스트",
            },
        },
        "required": ["summary", "action", "risks"],
    },
}

SYSTEM_PROMPT = (
    "당신은 SOXL 레버리지 ETF 투자 전문 애널리스트입니다. "
    "제공된 시그널 데이터를 바탕으로 한국어 투자 브리핑을 작성하세요. "
    "반드시 create_briefing 도구를 사용하여 응답하세요."
)


# ---------------------------------------------------------------------------
# LLM mode
# ---------------------------------------------------------------------------


def generate_briefing_llm(signal_result: SignalResult) -> BriefingResponse:
    """Generate briefing via Anthropic Claude API with tool_use structured output."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    signal_data = {
        "signal": signal_result.signal.value,
        "score": signal_result.score,
        "summary": signal_result.summary,
        "action": signal_result.action,
        "details": signal_result.details,
    }

    user_message = (
        "아래 SOXL 시그널 데이터를 분석하여 투자 브리핑을 작성해주세요.\n\n"
        f"```json\n{json.dumps(signal_data, ensure_ascii=False, indent=2, default=str)}\n```"
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[BRIEFING_TOOL],
            tool_choice={"type": "tool", "name": "create_briefing"},
            timeout=60.0,
        )
    except Exception as e:
        logger.error("LLM API call failed: %s", e)
        raise

    # Extract tool_use block
    for block in response.content:
        if block.type == "tool_use" and block.name == "create_briefing":
            args = block.input if isinstance(block.input, dict) else {}
            return BriefingResponse(
                date=datetime.now().strftime("%Y-%m-%d"),
                signal=signal_result,
                commentary=args.get("summary", ""),
                generated_at=datetime.now(),
            ), args.get("summary", ""), args.get("action", signal_result.action), args.get("risks", [])

    # Fallback if no tool_use block found
    logger.warning("No tool_use block in LLM response, falling back")
    raise ValueError("LLM did not return structured output")


# ---------------------------------------------------------------------------
# Fallback mode (rule-based)
# ---------------------------------------------------------------------------

_TEMPLATES = {
    SignalLevel.GREEN: {
        "summary": "SOXL 매수/홀드 유리한 환경입니다. 기술적 지표와 매크로 환경이 우호적입니다.",
        "action": "현 포지션 유지 또는 추가 매수 고려",
    },
    SignalLevel.YELLOW: {
        "summary": "SOXL 관망 구간입니다. 명확한 방향성이 나올 때까지 대기하세요.",
        "action": "신규 진입 자제, 기존 포지션 유지",
    },
    SignalLevel.RED: {
        "summary": "SOXL 리스크가 높은 구간입니다. 변동성과 레버리지 디케이에 주의하세요.",
        "action": "포지션 축소 또는 신규 진입 회피 권장",
    },
}


def generate_briefing_fallback(signal_result: SignalResult) -> BriefingResponse:
    """Generate briefing using rule-based templates (no LLM)."""
    template = _TEMPLATES.get(signal_result.signal, _TEMPLATES[SignalLevel.YELLOW])

    return BriefingResponse(
        date=datetime.now().strftime("%Y-%m-%d"),
        signal=signal_result,
        commentary=template["summary"],
        generated_at=datetime.now(),
    )


# ---------------------------------------------------------------------------
# Save to DB
# ---------------------------------------------------------------------------


def _save_briefing(briefing: BriefingResponse, mode: str) -> None:
    """Persist briefing to the briefings table."""
    conn = get_sync_db()
    try:
        conn.execute(
            """INSERT INTO briefings
               (briefing_date, signal_level, score, commentary, full_json, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (
                briefing.date,
                briefing.signal.signal.value,
                briefing.signal.score,
                briefing.commentary,
                json.dumps(
                    {
                        "signal": briefing.signal.model_dump(mode="json"),
                        "macro": briefing.macro.model_dump(mode="json") if briefing.macro else None,
                        "sentiment": briefing.sentiment.model_dump(mode="json") if briefing.sentiment else None,
                        "commentary": briefing.commentary,
                        "mode": mode,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            ),
        )
        conn.commit()
        logger.info("Briefing saved (mode=%s)", mode)
    except Exception as e:
        logger.error("Failed to save briefing: %s", e)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_briefing(signal_result: SignalResult) -> BriefingResponse:
    """Generate briefing — LLM if API key available, else fallback.

    Saves result to DB regardless of mode.
    """
    mode = "fallback"

    if settings.ANTHROPIC_API_KEY:
        try:
            result_tuple = generate_briefing_llm(signal_result)
            # Unpack: (BriefingResponse, summary, action, risks)
            briefing = result_tuple[0]
            # Override signal's action and risks with LLM output
            signal_result_copy = signal_result.model_copy(
                update={
                    "action": result_tuple[2],
                    "risks": result_tuple[3],
                }
            )
            briefing.signal = signal_result_copy
            mode = "llm"
            logger.info("Briefing generated via LLM")
        except Exception as e:
            logger.warning("LLM briefing failed, falling back: %s", e)
            briefing = generate_briefing_fallback(signal_result)
    else:
        logger.info("No API key, using fallback mode")
        briefing = generate_briefing_fallback(signal_result)

    _save_briefing(briefing, mode)
    return briefing
