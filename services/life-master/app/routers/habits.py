"""Habit tracking endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.database import repositories as repo
from app.models.schemas import (
    HabitCreate,
    HabitIncrementRequest,
    HabitLogRequest,
    HabitLogResponse,
    HabitOverviewItem,
    HabitResponse,
    HabitUpdate,
    StreakResponse,
)
from app.services.streak import calculate_streak
from app.utils.time_helpers import days_ago, today_str, validate_date_str

logger = logging.getLogger("life-master.routers.habits")

router = APIRouter(prefix="/habits", tags=["habits"])


@router.get("", response_model=list[HabitResponse])
async def list_habits(active_only: bool = True):
    return await repo.get_habits(active_only=active_only)


@router.post("", response_model=HabitResponse)
async def create_habit(body: HabitCreate):
    result = await repo.create_habit(body.model_dump())
    logger.info("Habit created: %s", body.name)
    return result


@router.get("/overview", response_model=list[HabitOverviewItem])
async def habits_overview():
    """Full dashboard: all active habits with streaks, recent logs, and today's value."""
    habits = await repo.get_habits(active_only=True)
    today = today_str()
    today_logs = await repo.get_all_habit_logs_for_date(today)
    today_map = {log["habit_id"]: log["value"] for log in today_logs}

    overview = []
    for habit in habits:
        logs = await repo.get_habit_logs(habit["id"])
        streak_data = calculate_streak(logs, habit.get("target_value", 1))
        recent = logs[:7]
        overview.append({
            "habit": habit,
            "streak": {"habit_id": habit["id"], **streak_data},
            "recent_logs": recent,
            "today_value": today_map.get(habit["id"], 0),
        })
    return overview


@router.get("/search")
async def search_habits(q: str = Query(min_length=1)):
    return await repo.search_habits(q)


@router.get("/{habit_id}", response_model=HabitResponse)
async def get_habit(habit_id: int):
    result = await repo.get_habit(habit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Habit not found")
    return result


@router.put("/{habit_id}", response_model=HabitResponse)
async def update_habit(habit_id: int, body: HabitUpdate):
    existing = await repo.get_habit(habit_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Habit not found")
    result = await repo.update_habit(habit_id, body.model_dump(exclude_unset=True))
    return result


@router.delete("/{habit_id}")
async def delete_habit(habit_id: int):
    ok = await repo.delete_habit(habit_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Habit not found")
    logger.info("Habit soft-deleted: %d", habit_id)
    return {"deleted": habit_id}


@router.patch("/{habit_id}/restore", response_model=HabitResponse)
async def restore_habit(habit_id: int):
    result = await repo.restore_habit(habit_id)
    if not result:
        raise HTTPException(status_code=404, detail="Habit not found or already active")
    logger.info("Habit restored: %d", habit_id)
    return result


@router.post("/{habit_id}/log", response_model=HabitLogResponse)
async def log_habit(habit_id: int, body: HabitLogRequest | None = None):
    """Log a habit value. Body is optional — defaults to value=1 for today."""
    existing = await repo.get_habit(habit_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Habit not found")
    if body is None:
        log_date = today_str()
        value = 1
    else:
        log_date = body.date or today_str()
        value = body.value
    result = await repo.log_habit(habit_id, log_date, value)
    logger.info("Habit %d logged: %.1f on %s", habit_id, value, log_date)
    return result


@router.patch("/{habit_id}/increment", response_model=HabitLogResponse)
async def increment_habit(habit_id: int, body: HabitIncrementRequest | None = None):
    """Add/subtract value. Body optional — defaults to +1 today."""
    existing = await repo.get_habit(habit_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Habit not found")
    delta = body.delta if body else 1
    log_date = (body.date if body else None) or today_str()
    result = await repo.increment_habit(habit_id, log_date, delta)
    logger.info("Habit %d incremented by %.1f on %s", habit_id, delta, log_date)
    return result


@router.get("/{habit_id}/streak", response_model=StreakResponse)
async def habit_streak(habit_id: int):
    habit = await repo.get_habit(habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    logs = await repo.get_habit_logs(habit_id)
    streak_data = calculate_streak(logs, habit.get("target_value", 1))
    return {"habit_id": habit_id, **streak_data}


@router.get("/{habit_id}/logs", response_model=list[HabitLogResponse])
async def habit_logs(
    habit_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
):
    habit = await repo.get_habit(habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return await repo.get_habit_logs(habit_id, date_from=date_from, date_to=date_to)


@router.delete("/{habit_id}/logs/{log_id}")
async def delete_habit_log(habit_id: int, log_id: int):
    ok = await repo.delete_habit_log(log_id, habit_id=habit_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"deleted": log_id}


@router.get("/{habit_id}/heatmap")
async def habit_heatmap(
    habit_id: int,
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    try:
        validate_date_str(date_from)
        validate_date_str(date_to)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format, use YYYY-MM-DD")
    habit = await repo.get_habit(habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    if not date_from:
        date_from = days_ago(90)
    if not date_to:
        date_to = today_str()
    return await repo.get_habit_heatmap(habit_id, date_from, date_to)


@router.get("/{habit_id}/trend")
async def habit_trend(
    habit_id: int,
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    try:
        validate_date_str(date_from)
        validate_date_str(date_to)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format, use YYYY-MM-DD")
    if not date_from:
        date_from = days_ago(30)
    if not date_to:
        date_to = today_str()
    habit = await repo.get_habit(habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return await repo.get_habit_trend(habit_id, date_from, date_to)
