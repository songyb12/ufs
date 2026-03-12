"""Event Detector — Classify news articles into structured events.

Uses LLM (Claude tool_use) to:
1. Assess significance (1-5) of a news article
2. Classify event type (policy, statement, personnel, diplomatic, military, economic)
3. Extract structured summary
4. Determine if profile update is needed
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings

logger = logging.getLogger("vibe.polaris.collectors.event_detector")

EVENT_TYPES = [
    "policy",       # 정책 발표/변경
    "statement",    # 공식 발언/트윗
    "personnel",    # 인사 변동
    "diplomatic",   # 외교 활동
    "military",     # 군사/안보 조치
    "economic",     # 경제 정책/조치
    "legal",        # 법적 이슈
    "election",     # 선거 관련
]

SIGNIFICANCE_SCALE = {
    1: "일상적 뉴스 (시장 영향 없음)",
    2: "주목할 만한 뉴스 (일부 섹터 영향 가능)",
    3: "중요 뉴스 (복수 섹터 영향)",
    4: "매우 중요한 뉴스 (시장 전반 영향)",
    5: "비상 (글로벌 시장 충격)",
}

EVENT_CLASSIFICATION_TOOL = {
    "name": "classify_event",
    "description": "뉴스 기사를 분석하여 이벤트로 분류합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_relevant": {
                "type": "boolean",
                "description": "이 인물의 행동/정책과 직접 관련이 있는지",
            },
            "event_type": {
                "type": "string",
                "enum": EVENT_TYPES,
                "description": "이벤트 유형",
            },
            "significance": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "중요도 (1-5)",
            },
            "summary": {
                "type": "string",
                "description": "이벤트 요약 (한국어, 2-3문장)",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "관련 카테고리 태그 (e.g., tariff, china, semiconductor)",
            },
            "market_relevance": {
                "type": "string",
                "description": "시장 영향 분석 (한국어, 1-2문장, 관련 섹터 명시)",
            },
            "profile_update_needed": {
                "type": "boolean",
                "description": "기존 프로파일 업데이트가 필요한 새로운 패턴인지",
            },
        },
        "required": ["is_relevant", "event_type", "significance",
                     "summary", "categories", "market_relevance",
                     "profile_update_needed"],
    },
}


async def classify_news_event(
    figure_name: str,
    article_title: str,
    article_description: str = "",
    article_source: str = "",
) -> dict:
    """Classify a single news article into a structured event.

    Returns:
        dict with is_relevant, event_type, significance, summary,
        categories, market_relevance, profile_update_needed
    """
    if not settings.LLM_API_KEY:
        # Fallback: rule-based classification
        return _rule_based_classify(figure_name, article_title, article_description)

    try:
        import anthropic
    except ImportError:
        return _rule_based_classify(figure_name, article_title, article_description)

    client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
    model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL

    source_note = f" (출처: {article_source})" if article_source else ""
    user_message = (
        f"인물: {figure_name}\n"
        f"제목: {article_title}{source_note}\n"
        f"내용: {article_description or '(없음)'}\n\n"
        f"이 뉴스를 분석하여 classify_event 도구로 분류해주세요."
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=(
                "정치 뉴스 이벤트 분류 전문가입니다. "
                "금융시장 영향 관점에서 뉴스를 분석합니다. "
                "반드시 classify_event 도구를 호출하여 응답하세요."
            ),
            messages=[{"role": "user", "content": user_message}],
            tools=[EVENT_CLASSIFICATION_TOOL],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "classify_event":
                return block.input

        return _rule_based_classify(figure_name, article_title, article_description)

    except Exception as e:
        logger.warning("LLM event classification failed: %s", e)
        return _rule_based_classify(figure_name, article_title, article_description)


async def classify_news_batch(
    figure_name: str,
    articles: list[dict],
    min_significance: int = 2,
) -> list[dict]:
    """Classify a batch of articles and filter by significance.

    Args:
        figure_name: The political figure's name.
        articles: List of article dicts with title, description, source.
        min_significance: Minimum significance to include.

    Returns:
        List of classified events, filtered and sorted by significance desc.
    """
    # Limit concurrent LLM calls to avoid rate limiting
    sem = asyncio.Semaphore(3)

    async def _classify_one(article: dict) -> dict | None:
        async with sem:
            result = await classify_news_event(
                figure_name=figure_name,
                article_title=article.get("title", ""),
                article_description=article.get("description", ""),
                article_source=article.get("source", ""),
            )
            if not result.get("is_relevant", False):
                return None
            if result.get("significance", 1) < min_significance:
                return None

            # Attach original article metadata
            result["article_title"] = article.get("title", "")
            result["article_url"] = article.get("url", "")
            result["article_published"] = article.get("published", "")
            return result

    tasks = [_classify_one(article) for article in articles]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    events = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Event classification error: %s", r)
            continue
        if r is not None:
            events.append(r)

    events.sort(key=lambda x: x.get("significance", 1), reverse=True)
    return events


def _rule_based_classify(
    figure_name: str,
    title: str,
    description: str = "",
) -> dict:
    """Fallback rule-based classification when LLM is unavailable."""
    text = (title + " " + description).lower()

    # Event type detection
    event_type = "statement"
    type_keywords = {
        "policy": ["policy", "executive order", "regulation", "law", "bill",
                    "정책", "행정명령", "규제", "법안"],
        "economic": ["tariff", "trade", "sanction", "economy", "inflation", "tax",
                     "관세", "무역", "제재", "경제", "인플레이션", "세금"],
        "diplomatic": ["summit", "diplomat", "alliance", "treaty", "ambassador",
                       "정상회담", "외교", "동맹", "조약"],
        "military": ["military", "defense", "war", "missile", "nato",
                     "군사", "국방", "전쟁", "미사일"],
        "personnel": ["appoint", "fired", "resign", "nominate", "cabinet",
                      "임명", "해임", "사임", "지명", "인사"],
        "legal": ["court", "lawsuit", "indictment", "trial", "legal",
                  "법원", "소송", "기소", "재판"],
        "election": ["election", "vote", "poll", "campaign", "ballot",
                     "선거", "투표", "여론조사", "캠페인"],
    }

    for etype, keywords in type_keywords.items():
        if any(kw in text for kw in keywords):
            event_type = etype
            break

    # Significance estimation
    significance = 2
    high_impact = ["tariff", "war", "sanction", "executive order", "관세", "전쟁", "제재"]
    critical_impact = ["nuclear", "invasion", "crash", "default", "핵", "침공", "폭락", "디폴트"]

    if any(kw in text for kw in critical_impact):
        significance = 5
    elif any(kw in text for kw in high_impact):
        significance = 3

    return {
        "is_relevant": True,
        "event_type": event_type,
        "significance": significance,
        "summary": title,
        "categories": [event_type],
        "market_relevance": "규칙 기반 분류 (LLM 미사용)",
        "profile_update_needed": significance >= 4,
    }
