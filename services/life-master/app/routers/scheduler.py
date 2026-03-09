"""Dynamic scheduler endpoints."""

import json
import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.database import repositories as repo
from app.models.schemas import (
    ScheduleBlockCreate,
    ScheduleBlockResponse,
    ScheduleBlockUpdate,
    ScheduleGenerateRequest,
)
from app.services.optimizer import generate_schedule
from app.utils.time_helpers import today_str, week_range

logger = logging.getLogger("life-master.routers.scheduler")

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/day", response_model=list[ScheduleBlockResponse])
async def day_schedule(date: str | None = None):
    target = date or today_str()
    return await repo.get_schedule_blocks(target)


@router.get("/week", response_model=list[ScheduleBlockResponse])
async def week_schedule(date: str | None = None):
    start, end = week_range(date)
    return await repo.get_schedule_blocks(start, end)


@router.post("/blocks", response_model=ScheduleBlockResponse)
async def create_block(body: ScheduleBlockCreate):
    # R7: Conflict detection
    conflicts = await repo.detect_conflicts(body.date, body.start_time, body.end_time)
    data = body.model_dump()
    data["source"] = "MANUAL"
    result = await repo.create_schedule_block(data)
    response = dict(result)
    if conflicts:
        response["_conflicts"] = [
            {"id": c["id"], "title": c["title"], "start_time": c["start_time"], "end_time": c["end_time"]}
            for c in conflicts
        ]
        response["_warning"] = f"{len(conflicts)} conflicting block(s) detected"
    logger.info("Block created: %s on %s", body.title, body.date)
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


@router.post("/generate")
async def generate_day_schedule(body: ScheduleGenerateRequest):
    """Auto-generate schedule from routines for a given date."""
    target_date = body.date or today_str()
    day_name = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][
        date.fromisoformat(target_date).weekday()
    ]

    # Get active routines for this day
    routines = await repo.get_routines(active_only=True)
    day_routines = []
    for r in routines:
        repeat = json.loads(r["repeat_days"]) if isinstance(r["repeat_days"], str) else r["repeat_days"]
        if day_name in repeat:
            day_routines.append(r)

    if not day_routines:
        return {"date": target_date, "generated": 0, "blocks": []}

    # Get locked blocks (plus manually created non-locked blocks to avoid overlap)
    existing = await repo.get_schedule_blocks(target_date)
    occupied = [b for b in existing if b.get("is_locked") or b.get("source") == "MANUAL"]

    # Clear previous generated blocks
    cleared = await repo.delete_generated_blocks(target_date)

    # Generate with break time support
    blocks = generate_schedule(
        day_routines,
        occupied,
        day_start=settings.DAY_START_HOUR,
        day_end=settings.DAY_END_HOUR,
        slot_interval=settings.SLOT_INTERVAL_MIN,
        break_min=body.break_min,
    )

    # Save
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
