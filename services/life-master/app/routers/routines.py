"""Routine management endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.database import repositories as repo
from app.models.schemas import (
    BulkActiveRequest,
    BulkCheckRequest,
    BulkCheckResponse,
    RoutineCheckRequest,
    RoutineCreate,
    RoutineLogResponse,
    RoutineResponse,
    RoutineStatsResponse,
    RoutineUpdate,
    TodayRoutineResponse,
)
from app.utils.time_helpers import days_ago, today_day_name, today_str

logger = logging.getLogger("life-master.routers.routines")

router = APIRouter(prefix="/routines", tags=["routines"])


@router.get("", response_model=list[RoutineResponse])
async def list_routines(
    category: str | None = None,
    time_slot: str | None = None,
    active_only: bool = True,
):
    return await repo.get_routines(category=category, time_slot=time_slot, active_only=active_only)


@router.post("", response_model=RoutineResponse)
async def create_routine(body: RoutineCreate):
    result = await repo.create_routine(body.model_dump())
    logger.info("Routine created: %s", body.name)
    return result


@router.get("/today", response_model=list[TodayRoutineResponse])
async def today_routines():
    return await repo.get_today_routines(today_str(), today_day_name())


@router.get("/stats", response_model=RoutineStatsResponse)
async def routine_stats(
    routine_id: int | None = None,
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    if not date_from:
        date_from = days_ago(30)
    if not date_to:
        date_to = today_str()
    return await repo.get_routine_stats(routine_id, date_from, date_to)


@router.get("/heatmap")
async def routine_heatmap(
    routine_id: int | None = None,
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    if not date_from:
        date_from = days_ago(90)
    if not date_to:
        date_to = today_str()
    return await repo.get_routine_heatmap(routine_id, date_from, date_to)


@router.get("/category-stats")
async def category_stats(
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    if not date_from:
        date_from = days_ago(30)
    if not date_to:
        date_to = today_str()
    return await repo.get_routine_category_stats(date_from, date_to)


@router.get("/search")
async def search_routines(q: str):
    return await repo.search_routines(q)


@router.post("/bulk-check", response_model=BulkCheckResponse)
async def bulk_check(body: BulkCheckRequest):
    log_date = body.date or today_str()
    items = [item.model_dump() for item in body.items]
    results = await repo.bulk_check_routines(items, log_date)
    return {"date": log_date, "checked": len(results), "results": results}


@router.post("/bulk-active")
async def bulk_set_active(body: BulkActiveRequest):
    count = await repo.bulk_set_active(body.routine_ids, body.is_active)
    return {"updated": count, "is_active": body.is_active}


@router.get("/{routine_id}", response_model=RoutineResponse)
async def get_routine(routine_id: int):
    result = await repo.get_routine(routine_id)
    if not result:
        raise HTTPException(status_code=404, detail="Routine not found")
    return result


@router.put("/{routine_id}", response_model=RoutineResponse)
async def update_routine(routine_id: int, body: RoutineUpdate):
    existing = await repo.get_routine(routine_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Routine not found")
    result = await repo.update_routine(routine_id, body.model_dump(exclude_unset=True))
    return result


@router.delete("/{routine_id}")
async def delete_routine(routine_id: int):
    ok = await repo.delete_routine(routine_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Routine not found")
    logger.info("Routine soft-deleted: %d", routine_id)
    return {"deleted": routine_id}


@router.patch("/{routine_id}/restore", response_model=RoutineResponse)
async def restore_routine(routine_id: int):
    result = await repo.restore_routine(routine_id)
    if not result:
        raise HTTPException(status_code=404, detail="Routine not found or already active")
    logger.info("Routine restored: %d", routine_id)
    return result


@router.post("/{routine_id}/check", response_model=RoutineLogResponse)
async def check_routine(routine_id: int, body: RoutineCheckRequest | None = None):
    """Check a routine. Body is optional — defaults to DONE for today."""
    existing = await repo.get_routine(routine_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Routine not found")
    if body is None:
        log_date = today_str()
        status = "DONE"
        note = None
    else:
        log_date = body.date or today_str()
        status = body.status
        note = body.note
    result = await repo.check_routine(routine_id, log_date, status, note)
    logger.info("Routine %d checked: %s on %s", routine_id, status, log_date)
    return result


@router.delete("/{routine_id}/check")
async def uncheck_routine(routine_id: int, date: str | None = None):
    log_date = date or today_str()
    ok = await repo.uncheck_routine(routine_id, log_date)
    if not ok:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"unchecked": routine_id, "date": log_date}


@router.get("/{routine_id}/logs", response_model=list[RoutineLogResponse])
async def routine_logs(
    routine_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
):
    return await repo.get_routine_logs(routine_id=routine_id, date_from=date_from, date_to=date_to)


@router.delete("/{routine_id}/logs/{log_id}")
async def delete_routine_log(routine_id: int, log_id: int):
    ok = await repo.delete_routine_log(log_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"deleted": log_id}


@router.post("/{routine_id}/duplicate", response_model=RoutineResponse)
async def duplicate_routine(routine_id: int):
    result = await repo.duplicate_routine(routine_id)
    if not result:
        raise HTTPException(status_code=404, detail="Routine not found")
    logger.info("Routine %d duplicated as %d", routine_id, result["id"])
    return result
