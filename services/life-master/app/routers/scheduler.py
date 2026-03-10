"""Dynamic scheduler endpoints."""

import json
import logging
from datetime import date

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.database import repositories as repo
from app.models.schemas import (
    ScheduleBlockCreate,
    ScheduleBlockResponse,
    ScheduleBlockUpdate,
    ScheduleCopyRequest,
    ScheduleGenerateRequest,
    ScheduleTemplateCreate,
)
from app.services.optimizer import generate_schedule
from app.utils.time_helpers import today_str, week_range

logger = logging.getLogger("life-master.routers.scheduler")

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/today", response_model=list[ScheduleBlockResponse])
async def today_schedule():
    return await repo.get_schedule_blocks(today_str())


@router.get("/day", response_model=list[ScheduleBlockResponse])
async def day_schedule(date: str | None = None):
    target = date or today_str()
    return await repo.get_schedule_blocks(target)


@router.get("/week", response_model=list[ScheduleBlockResponse])
async def week_schedule(date: str | None = None):
    start, end = week_range(date)
    return await repo.get_schedule_blocks(start, end)


@router.get("/month")
async def month_schedule(year: int, month: int):
    return await repo.get_month_schedule(year, month)


@router.post("/blocks", response_model=ScheduleBlockResponse)
async def create_block(body: ScheduleBlockCreate):
    conflicts = await repo.detect_conflicts(body.date, body.start_time, body.end_time)
    data = body.model_dump()
    data["source"] = "MANUAL"
    result = await repo.create_schedule_block(data)
    logger.info("Block created: %s on %s", body.title, body.date)
    if conflicts:
        logger.warning("%d conflict(s) for block on %s %s-%s", len(conflicts), body.date, body.start_time, body.end_time)
    return result


@router.put("/blocks/{block_id}", response_model=ScheduleBlockResponse)
async def update_block(block_id: int, body: ScheduleBlockUpdate):
    result = await repo.update_schedule_block(block_id, body.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="Block not found")
    return result


@router.delete("/blocks/{block_id}")
async def delete_block(block_id: int):
    ok = await repo.delete_schedule_block(block_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Block not found")
    return {"deleted": block_id}


@router.post("/blocks/copy", response_model=ScheduleBlockResponse)
async def copy_block(body: ScheduleCopyRequest):
    result = await repo.copy_schedule_block(body.block_id, body.target_date)
    if not result:
        raise HTTPException(status_code=404, detail="Block not found")
    return result


@router.post("/generate")
async def generate_day_schedule(body: ScheduleGenerateRequest):
    """Auto-generate schedule from routines for a given date."""
    target_date = body.date or today_str()
    day_name = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][
        date.fromisoformat(target_date).weekday()
    ]

    routines = await repo.get_routines(active_only=True)
    day_routines = []
    for r in routines:
        repeat = r["repeat_days"] if isinstance(r["repeat_days"], list) else json.loads(r["repeat_days"])
        if day_name in repeat:
            day_routines.append(r)

    if not day_routines:
        return {"date": target_date, "generated": 0, "blocks": []}

    existing = await repo.get_schedule_blocks(target_date)
    occupied = [b for b in existing if b.get("is_locked") or b.get("source") == "MANUAL"]

    cleared = await repo.delete_generated_blocks(target_date)

    blocks = generate_schedule(
        day_routines,
        occupied,
        day_start=settings.DAY_START_HOUR,
        day_end=settings.DAY_END_HOUR,
        slot_interval=settings.SLOT_INTERVAL_MIN,
        break_min=body.break_min,
    )

    saved = []
    for block in blocks:
        block["date"] = target_date
        saved.append(await repo.create_schedule_block(block))

    logger.info(
        "Generated %d blocks for %s (cleared %d old)",
        len(saved), target_date, cleared,
    )
    return {
        "date": target_date,
        "generated": len(saved),
        "cleared": cleared,
        "blocks": saved,
    }


@router.get("/conflicts")
async def check_conflicts(date: str, start_time: str, end_time: str):
    """Check if a time range conflicts with existing blocks."""
    conflicts = await repo.detect_conflicts(date, start_time, end_time)
    return {
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "has_conflict": len(conflicts) > 0,
        "conflicts": conflicts,
    }


# ── Templates ─────────────────────────────────────────────


@router.get("/templates")
async def list_templates(day_of_week: str | None = None):
    return await repo.get_templates(day_of_week)


@router.post("/templates")
async def create_template(body: ScheduleTemplateCreate):
    data = {"name": body.name, "day_of_week": body.day_of_week, "blocks": body.blocks}
    result = await repo.create_template(data)
    logger.info("Template created: %s for %s", body.name, body.day_of_week)
    return result


@router.post("/templates/{template_id}/apply")
async def apply_template(template_id: int, target_date: str):
    blocks = await repo.apply_template(template_id, target_date)
    if not blocks:
        raise HTTPException(status_code=404, detail="Template not found or empty")
    return {"date": target_date, "applied": len(blocks), "blocks": blocks}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int):
    ok = await repo.delete_template(template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": template_id}
