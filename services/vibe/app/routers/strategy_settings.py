"""Strategy Settings Router — /settings/strategy endpoints.

View and adjust VIBE strategy parameters with change history.
Parameters are stored in runtime_config with 'strategy.' prefix.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.database import repositories as repo

logger = logging.getLogger("vibe.routers.strategy_settings")

router = APIRouter(prefix="/settings/strategy", tags=["strategy-settings"])

# ── Parameter Definitions ──────────────────────────────────────────────
# Each param: key, default, label, description, category, min, max, step

STRATEGY_PARAMS = [
    # Hard Limits
    {
        "key": "hard_limit_rsi_hold",
        "default": 65,
        "label": "RSI 강제 HOLD 기준",
        "description": "RSI가 이 값 이상이면 BUY→HOLD 강제 전환 (과매수 보호)",
        "category": "hard_limit",
        "min": 50, "max": 90, "step": 1, "type": "int",
    },
    {
        "key": "hard_limit_disparity_hold",
        "default": 105,
        "label": "이격도 강제 HOLD 기준 (%)",
        "description": "20일 이격도가 이 값 이상이면 BUY→HOLD 강제 전환",
        "category": "hard_limit",
        "min": 100, "max": 120, "step": 1, "type": "int",
    },
    {
        "key": "hard_limit_kr_rsi_buy_block",
        "default": 50,
        "label": "KR RSI 매수 차단 기준",
        "description": "한국 종목 RSI가 이 값 이상이면 BUY 시그널 차단",
        "category": "hard_limit",
        "min": 30, "max": 70, "step": 1, "type": "int",
    },
    {
        "key": "hard_limit_us_rsi_buy_block",
        "default": 55,
        "label": "US RSI 매수 차단 기준",
        "description": "미국 종목 RSI가 이 값 이상이면 BUY 시그널 차단",
        "category": "hard_limit",
        "min": 30, "max": 70, "step": 1, "type": "int",
    },
    # Stance Thresholds
    {
        "key": "stance_very_defensive_risk",
        "default": 75,
        "label": "매우 보수적 리스크 기준",
        "description": "리스크 점수가 이 값 이상이면 '매우 보수적' 스탠스",
        "category": "stance",
        "min": 60, "max": 90, "step": 1, "type": "int",
    },
    {
        "key": "stance_cautious_risk",
        "default": 60,
        "label": "신중 접근 리스크 기준",
        "description": "리스크 점수가 이 값 이상이면 '신중 접근' 스탠스",
        "category": "stance",
        "min": 40, "max": 80, "step": 1, "type": "int",
    },
    {
        "key": "stance_aggressive_max_risk",
        "default": 30,
        "label": "적극 매수 리스크 상한",
        "description": "리스크 점수가 이 값 이하 + 봄/여름장세일 때 '적극 매수'",
        "category": "stance",
        "min": 10, "max": 50, "step": 1, "type": "int",
    },
    {
        "key": "stance_moderate_max_risk",
        "default": 45,
        "label": "완만한 매수 리스크 상한",
        "description": "리스크 점수가 이 값 이하이면 '완만한 매수' 스탠스",
        "category": "stance",
        "min": 25, "max": 60, "step": 1, "type": "int",
    },
    # Position Management
    {
        "key": "stop_loss_pct",
        "default": -7.0,
        "label": "손절 기준 (%)",
        "description": "P&L이 이 값 이하이면 손절 매도 권장",
        "category": "position",
        "min": -20.0, "max": -3.0, "step": 0.5, "type": "float",
    },
    {
        "key": "take_profit_pct",
        "default": 15.0,
        "label": "익절 기준 (%)",
        "description": "P&L이 이 값 이상이면 익절 매도 권장",
        "category": "position",
        "min": 5.0, "max": 30.0, "step": 0.5, "type": "float",
    },
    {
        "key": "partial_profit_pct",
        "default": 10.0,
        "label": "부분 익절 기준 (%)",
        "description": "P&L이 이 값 이상이면 부분 익절 권장 (30-50%)",
        "category": "position",
        "min": 5.0, "max": 20.0, "step": 0.5, "type": "float",
    },
    {
        "key": "max_single_position_pct",
        "default": 10.0,
        "label": "단일 종목 최대 비중 (%)",
        "description": "한 종목에 투자할 수 있는 최대 포트폴리오 비중",
        "category": "position",
        "min": 3.0, "max": 25.0, "step": 1.0, "type": "float",
    },
    # Cash Ratios
    {
        "key": "cash_ratio_panic",
        "default": 50,
        "label": "패닉 시 현금 비중 (%)",
        "description": "Initial Panic 시 권장 현금 비중",
        "category": "cash",
        "min": 30, "max": 70, "step": 5, "type": "int",
    },
    {
        "key": "cash_ratio_high_risk",
        "default": 40,
        "label": "고위험 시 현금 비중 (%)",
        "description": "리스크 ≥ 75 시 권장 현금 비중",
        "category": "cash",
        "min": 20, "max": 60, "step": 5, "type": "int",
    },
    {
        "key": "cash_ratio_low_risk",
        "default": 10,
        "label": "저위험 시 현금 비중 (%)",
        "description": "리스크 ≤ 30 + 봄/여름장세 시 권장 현금 비중",
        "category": "cash",
        "min": 0, "max": 30, "step": 5, "type": "int",
    },
]

PARAM_MAP = {p["key"]: p for p in STRATEGY_PARAMS}

CATEGORY_LABELS = {
    "hard_limit": {"label": "Hard Limit (안전장치)", "icon": "🛡️", "color": "#ef4444",
                    "description": "과매수/과열 상태에서 시그널을 강제 차단하는 안전장치"},
    "stance": {"label": "스탠스 기준값", "icon": "🎯", "color": "#f59e0b",
               "description": "리스크 점수에 따른 투자 스탠스(공격/중립/방어) 결정 기준"},
    "position": {"label": "포지션 관리", "icon": "💼", "color": "#3b82f6",
                 "description": "손절/익절/비중 관리 기준값"},
    "cash": {"label": "현금 비중", "icon": "💰", "color": "#22c55e",
             "description": "시장 상황별 권장 현금 비중"},
}


def _parse_value(raw: str, param_type: str):
    """Parse stored string value to proper type."""
    try:
        if param_type == "float":
            return float(raw)
        return int(float(raw))
    except (ValueError, TypeError):
        return None


@router.get("")
async def get_strategy_settings():
    """Get all strategy parameters with current values and change history."""
    rt_cfg = await repo.get_runtime_config()

    params_with_values = []
    for p in STRATEGY_PARAMS:
        stored_key = f"strategy.{p['key']}"
        stored = rt_cfg.get(stored_key)
        parsed = _parse_value(stored, p["type"]) if stored else None
        current_value = parsed if parsed is not None else p["default"]
        is_modified = stored is not None and parsed is not None

        params_with_values.append({
            **p,
            "current_value": current_value,
            "is_modified": is_modified,
        })

    # Change log
    change_log_raw = rt_cfg.get("strategy._changelog", "[]")
    try:
        change_log = json.loads(change_log_raw)
    except (json.JSONDecodeError, TypeError):
        change_log = []

    return {
        "params": params_with_values,
        "categories": CATEGORY_LABELS,
        "change_log": change_log[-30:],  # Last 30 changes
        "modified_count": sum(1 for p in params_with_values if p["is_modified"]),
    }


@router.put("")
async def update_strategy_settings(updates: dict):
    """Update strategy parameter values. Body: {key: value, ...}"""
    changes = updates.get("changes", {})
    if not changes:
        return {"status": "ok", "message": "No changes"}

    rt_cfg = await repo.get_runtime_config()

    # Load existing changelog
    change_log_raw = rt_cfg.get("strategy._changelog", "[]")
    try:
        change_log = json.loads(change_log_raw)
    except (json.JSONDecodeError, TypeError):
        change_log = []

    applied = []
    for key, new_value in changes.items():
        param = PARAM_MAP.get(key)
        if not param:
            continue

        # Coerce to number and validate range
        try:
            new_value = float(new_value)
            if param["type"] == "int":
                new_value = int(new_value)
        except (TypeError, ValueError):
            continue
        if new_value < param["min"] or new_value > param["max"]:
            continue

        stored_key = f"strategy.{key}"
        old_stored = rt_cfg.get(stored_key)
        old_value = _parse_value(old_stored, param["type"]) if old_stored else param["default"]

        if old_value == new_value:
            continue

        await repo.upsert_runtime_config(stored_key, str(new_value))

        change_entry = {
            "key": key,
            "label": param["label"],
            "old_value": old_value,
            "new_value": new_value,
            "changed_at": datetime.now().isoformat(timespec="seconds"),
        }
        change_log.append(change_entry)
        applied.append(change_entry)

    # Save changelog (keep last 100)
    change_log = change_log[-100:]
    await repo.upsert_runtime_config("strategy._changelog", json.dumps(change_log, ensure_ascii=False))

    return {
        "status": "ok",
        "applied": applied,
        "applied_count": len(applied),
    }


@router.post("/reset")
async def reset_strategy_param(body: dict):
    """Reset a single parameter to its default value."""
    key = body.get("key")
    if not key or not isinstance(key, str):
        raise HTTPException(status_code=400, detail="Missing or invalid 'key' field.")
    param = PARAM_MAP.get(key)
    if not param:
        raise HTTPException(status_code=404, detail=f"Unknown strategy parameter: {key}")

    stored_key = f"strategy.{key}"
    rt_cfg = await repo.get_runtime_config()
    old_stored = rt_cfg.get(stored_key)

    if old_stored is None:
        return {"status": "ok", "message": "Already at default"}

    old_value = _parse_value(old_stored, param["type"])

    # Delete the override so get_strategy_settings falls back to default
    from app.database.connection import get_db
    db = await get_db()
    await db.execute("DELETE FROM runtime_config WHERE key = ?", (stored_key,))
    await db.commit()

    # Log the reset
    change_log_raw = rt_cfg.get("strategy._changelog", "[]")
    try:
        change_log = json.loads(change_log_raw)
    except (json.JSONDecodeError, TypeError):
        change_log = []

    change_log.append({
        "key": key,
        "label": param["label"],
        "old_value": old_value,
        "new_value": param["default"],
        "changed_at": datetime.now().isoformat(timespec="seconds"),
        "reset": True,
    })
    change_log = change_log[-100:]
    await repo.upsert_runtime_config("strategy._changelog", json.dumps(change_log, ensure_ascii=False))

    return {"status": "ok", "message": f"{param['label']} reset to default ({param['default']})"}
