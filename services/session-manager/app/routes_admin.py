"""
app/routes_admin.py — Admin API routes (/admin/*)
"""

import asyncio
import os
import sys
import time

from fastapi import APIRouter, Depends, HTTPException

import app.state as _state
from app.auth import verify_admin_key
from app.pipeline_store import get_resumable_runs, mark_interrupted

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def admin_status(_: None = Depends(verify_admin_key)):
    """서버 상태 및 재시작 안전 여부 반환"""
    active = sum(1 for p in _state.pipelines.values() if p.status == "running")
    return {
        "active_pipelines": active,
        "resumable_runs": get_resumable_runs(),
        "safe_to_restart": active == 0,
        "shutting_down": _state._shutting_down,
    }


@router.post("/restart")
async def admin_restart(_: None = Depends(verify_admin_key)):
    """실행 중인 파이프라인 완료 대기 후 프로세스 재시작 (os.execv)"""
    _state._shutting_down = True

    # 실행 중인 파이프라인이 완료될 때까지 폴링 (최대 5분)
    deadline = time.time() + 300
    while time.time() < deadline:
        running = [p for p in _state.pipelines.values() if p.status == "running"]
        if not running:
            break
        await asyncio.sleep(2)

    # 아직 실행 중인 파이프라인은 interrupted로 마킹 후 강제 종료
    for p in list(_state.pipelines.values()):
        if p.status == "running":
            mark_interrupted(p.id)
            await p.stop()

    # 프로세스 재시작 (비동기로 짧게 지연하여 응답 반환 후 실행)
    async def _do_restart():
        await asyncio.sleep(0.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    asyncio.create_task(_do_restart())
    return {"status": "restarting", "message": "0.5초 후 프로세스 재시작"}


@router.post("/resume/{run_id}")
async def admin_resume(run_id: str, _: None = Depends(verify_admin_key)):
    """중단된 파이프라인의 체크포인트 조회 및 재개 힌트 반환"""
    runs = get_resumable_runs()
    matched = next((r for r in runs if r["id"] == run_id), None)
    if matched is None:
        raise HTTPException(status_code=404, detail=f"재개 가능한 run_id 없음: {run_id}")
    next_stage = matched["current_stage"] + 1
    return {
        "id": matched["id"],
        "session_id": matched["session_id"],
        "current_stage": matched["current_stage"],
        "stage_outputs": matched["stage_outputs"],
        "updated_at": matched.get("updated_at"),
        "resume_hint": (
            f"세션 {matched['session_id']}에서 "
            f"스테이지 {next_stage}부터 새 파이프라인을 시작하세요"
        ),
    }
