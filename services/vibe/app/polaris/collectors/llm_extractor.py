"""LLM Extractor — Build initial figure profiles using Claude's knowledge.

Uses Anthropic tool_use (structured output) to extract a comprehensive
personality profile from the LLM's training data.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.config import settings
from app.polaris.profile.schema import PROFILE_EXTRACTION_TOOL

logger = logging.getLogger("vibe.polaris.collectors.llm_extractor")

EXTRACTION_SYSTEM_PROMPT = """당신은 정치 인물 프로파일링 전문가입니다.

주어진 인물에 대해 **객관적이고 포괄적인 인격 프로파일**을 구축합니다.
반드시 save_figure_profile 도구를 사용하여 구조화된 데이터로 응답하세요.

## 프로파일 작성 원칙

1. **객관성**: 주관적 평가 대신 관찰 가능한 행동 패턴을 기술
2. **구체성**: "강경하다" 대신 "관세를 협상 도구로 활용, 최대 압박 후 양보"
3. **시장 연관성**: 정책/행동이 금융시장에 미치는 영향을 구체적으로 기술
4. **역사적 근거**: 과거 사례를 기반으로 패턴 도출
5. **관계 맵핑**: 주요 인물과의 관계를 구체적으로 기술

## 작성 범위
- core_values: 5-10개의 핵심 가치관
- personality_traits: 4가지 성향 상세 기술
- political_positions: 최소 5개 정책 분야
- key_relationships: 10-20명의 주요 인물 관계
- behavioral_patterns: 5-10개의 반복 패턴
- historical_precedents: 10-20개의 과거 사례 (특히 시장 영향이 컸던 것)
- market_sensitivities: 5-10개의 시장 민감 키워드"""


async def extract_initial_profile(
    figure_name: str,
    figure_role: str = "",
    figure_country: str = "",
) -> dict:
    """Extract a structured profile from LLM knowledge.

    Returns:
        dict with keys: status, profile_data, metadata
    """
    if not settings.LLM_API_KEY:
        return {"status": "error", "message": "LLM API 키가 설정되지 않았습니다."}

    try:
        import anthropic
    except ImportError:
        return {"status": "error", "message": "anthropic 패키지가 설치되지 않았습니다."}

    client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
    model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL

    role_desc = f" ({figure_role})" if figure_role else ""
    country_desc = f", {figure_country}" if figure_country else ""

    user_message = (
        f"{figure_name}{role_desc}{country_desc}에 대한 포괄적인 인격 프로파일을 구축해주세요.\n\n"
        f"이 프로파일은 이 인물의 **다음 행동을 예측**하는 데 사용됩니다.\n"
        f"특히 금융시장에 영향을 미칠 수 있는 정책 결정과 행동 패턴에 집중해주세요.\n\n"
        f"반드시 save_figure_profile 도구를 호출하여 응답하세요."
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[PROFILE_EXTRACTION_TOOL],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "save_figure_profile":
                return {
                    "status": "ok",
                    "profile_data": block.input,
                    "metadata": {
                        "model": model,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    },
                }

        text_parts = [b.text for b in response.content if hasattr(b, "text")]
        return {
            "status": "error",
            "message": "LLM이 tool_use로 응답하지 않았습니다.",
            "raw_text": "\n".join(text_parts),
        }

    except Exception as e:
        logger.error("LLM profile extraction failed for %s: %s", figure_name, e, exc_info=True)
        return {"status": "error", "message": str(e)}


async def extract_profile_update(
    figure_name: str,
    current_profile: dict,
    new_event_summary: str,
) -> dict:
    """Ask LLM whether an event warrants a profile update.

    Returns:
        dict with keys: should_update (bool), updated_fields (dict), changelog (str)
    """
    if not settings.LLM_API_KEY:
        return {"should_update": False, "reason": "LLM API 키 없음"}

    try:
        import anthropic
    except ImportError:
        return {"should_update": False, "reason": "anthropic 패키지 없음"}

    client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
    model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL

    update_tool = {
        "name": "update_profile",
        "description": "프로파일 업데이트가 필요한 경우 변경사항을 저장합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "should_update": {"type": "boolean"},
                "changelog": {"type": "string"},
                "updated_fields": {"type": "object"},
            },
            "required": ["should_update", "changelog"],
        },
    }

    profile_summary = json.dumps(current_profile, ensure_ascii=False, indent=2)
    if len(profile_summary) > 6000:
        profile_summary = profile_summary[:6000] + "\n... (truncated)"

    user_message = (
        f"인물: {figure_name}\n\n"
        f"## 현재 프로파일\n```json\n{profile_summary}\n```\n\n"
        f"## 새 이벤트\n{new_event_summary}\n\n"
        f"이 이벤트가 기존 프로파일의 수정을 필요로 하는지 판단해주세요.\n"
        f"반드시 update_profile 도구를 호출하여 응답하세요."
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system="당신은 정치 인물 프로파일 업데이트 분석가입니다. 객관적으로 판단하세요.",
            messages=[{"role": "user", "content": user_message}],
            tools=[update_tool],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "update_profile":
                return block.input

        return {"should_update": False, "reason": "LLM 응답 파싱 실패"}

    except Exception as e:
        logger.error("Profile update check failed: %s", e, exc_info=True)
        return {"should_update": False, "reason": str(e)}
