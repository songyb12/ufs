"""
app/pipeline_configs.py — Pipeline configuration templates (presets + user-saved).

Builtin configs: 읽기 전용 기본 프리셋 4종.
User configs: data/pipeline_configs.json에 저장/불러오기.
"""

import json
import os
from pathlib import Path
from typing import Optional

from app.models import DATA_DIR

_CONFIGS_FILE = DATA_DIR / "pipeline_configs.json"

# ─── Builtin presets (읽기 전용) ─────────────────────────────────────────────

BUILTIN_CONFIGS: dict[str, dict] = {
    "autonomous": {
        "name": "autonomous",
        "label": "완전 자율",
        "description": "인간 개입 없이 장시간 자율 실행. 코딩·분석 등 복잡한 태스크에 적합.",
        "builtin": True,
        "config": {
            "max_iterations": 15,
            "max_cycles": 20,
            "cycle_reflection": True,
            "cycle_checkpoint": False,
            "cycle_phases": ["탐색/분석", "구현", "테스트/검증", "정리/마무리"],
            "supervisor_model": "sonnet",
            "mode": "cli",
        },
    },
    "economy": {
        "name": "economy",
        "label": "비용 절약",
        "description": "API 추가 호출 최소화. 반성 비용 없이 빠르게 실행.",
        "builtin": True,
        "config": {
            "max_iterations": 25,
            "max_cycles": 8,
            "cycle_reflection": False,
            "cycle_checkpoint": False,
            "cycle_phases": ["구현", "검증"],
            "supervisor_model": "sonnet",
            "mode": "cli",
        },
    },
    "supervised": {
        "name": "supervised",
        "label": "야간 감시형",
        "description": "각 사이클 종료 후 사람이 승인해야 다음 진행. 중요 태스크·야간 실행에 적합.",
        "builtin": True,
        "config": {
            "max_iterations": 15,
            "max_cycles": 5,
            "cycle_reflection": True,
            "cycle_checkpoint": True,
            "cycle_phases": ["요구사항 분석", "핵심 구현", "테스트", "리뷰", "배포"],
            "supervisor_model": "sonnet",
            "mode": "cli",
        },
    },
    "sprint": {
        "name": "sprint",
        "label": "단거리 스프린트",
        "description": "짧고 빠르게. 간단한 버그 수정·소규모 기능 추가에 적합.",
        "builtin": True,
        "config": {
            "max_iterations": 10,
            "max_cycles": 3,
            "cycle_reflection": False,
            "cycle_checkpoint": False,
            "cycle_phases": ["구현", "검증", "마무리"],
            "supervisor_model": "sonnet",
            "mode": "cli",
        },
    },
}


# ─── User config 저장소 ────────────────────────────────────────────────────────

def _load_raw() -> dict[str, dict]:
    """data/pipeline_configs.json 읽기. 없거나 깨지면 빈 dict."""
    if not _CONFIGS_FILE.exists():
        return {}
    try:
        return json.loads(_CONFIGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(data: dict[str, dict]) -> None:
    """atomic write."""
    tmp = Path(str(_CONFIGS_FILE) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _CONFIGS_FILE)


def list_all_configs() -> list[dict]:
    """Builtin + user 전체 목록 반환. builtin이 먼저."""
    user = _load_raw()
    result = list(BUILTIN_CONFIGS.values())
    for name, cfg in user.items():
        if name not in BUILTIN_CONFIGS:
            result.append(cfg)
    return result


def get_config(name: str) -> Optional[dict]:
    """이름으로 단일 설정 조회. 없으면 None."""
    if name in BUILTIN_CONFIGS:
        return BUILTIN_CONFIGS[name]
    return _load_raw().get(name)


def save_user_config(name: str, label: str, description: str, config: dict) -> dict:
    """사용자 설정 저장 (덮어쓰기 허용). builtin 이름은 차단."""
    if name in BUILTIN_CONFIGS:
        raise ValueError(f"'{name}'은 builtin 프리셋 이름입니다. 다른 이름을 사용하세요.")
    entry = {
        "name": name,
        "label": label,
        "description": description,
        "builtin": False,
        "config": config,
    }
    data = _load_raw()
    data[name] = entry
    _save_raw(data)
    return entry


def delete_user_config(name: str) -> bool:
    """사용자 설정 삭제. builtin은 삭제 불가. 없으면 False."""
    if name in BUILTIN_CONFIGS:
        raise ValueError(f"'{name}'은 builtin 프리셋으로 삭제할 수 없습니다.")
    data = _load_raw()
    if name not in data:
        return False
    del data[name]
    _save_raw(data)
    return True
