"""Profile JSON schema definition and LLM tool definitions."""

from __future__ import annotations

# Tool schema for LLM structured output (Anthropic tool_use)
PROFILE_EXTRACTION_TOOL = {
    "name": "save_figure_profile",
    "description": "주어진 정치 인물의 구조화된 인격 프로파일을 저장합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "core_values": {
                "type": "array",
                "items": {"type": "string"},
                "description": "핵심 가치관/신념 (5-10개)",
            },
            "personality_traits": {
                "type": "object",
                "properties": {
                    "negotiation_style": {"type": "string", "description": "협상 스타일 (1-2문장)"},
                    "decision_pattern": {"type": "string", "description": "의사결정 패턴 (1-2문장)"},
                    "communication_style": {"type": "string", "description": "소통/발언 스타일 (1-2문장)"},
                    "risk_appetite": {"type": "string", "description": "리스크 성향 (1-2문장)"},
                },
                "required": ["negotiation_style", "decision_pattern",
                             "communication_style", "risk_appetite"],
            },
            "political_positions": {
                "type": "object",
                "description": "주요 정책 분야별 입장 (key: 분야, value: 입장 설명)",
                "additionalProperties": {"type": "string"},
            },
            "key_relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": ["ally", "rival", "neutral", "complex"]},
                        "strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                        "notes": {"type": "string"},
                    },
                    "required": ["name", "type"],
                },
                "description": "주요 인간관계 (10-20명)",
            },
            "behavioral_patterns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["pattern", "description"],
                },
                "description": "반복되는 행동 패턴 (5-10개)",
            },
            "historical_precedents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string"},
                        "action": {"type": "string"},
                        "outcome": {"type": "string"},
                        "date": {"type": "string"},
                    },
                    "required": ["event", "action", "outcome"],
                },
                "description": "행동 예측에 참고할 과거 사례 (10-20개)",
            },
            "market_sensitivities": {
                "type": "object",
                "description": "시장 영향 키워드 (key: 정책/이벤트 키워드)",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "sectors": {"type": "array", "items": {"type": "string"}},
                        "direction": {"type": "string", "enum": ["positive", "negative", "mixed"]},
                        "magnitude": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                },
            },
        },
        "required": ["core_values", "personality_traits", "political_positions",
                     "key_relationships", "behavioral_patterns",
                     "historical_precedents", "market_sensitivities"],
    },
}
