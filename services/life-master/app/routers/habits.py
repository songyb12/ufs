"""Habit tracking endpoints."""

import logging

from fastapi import APIRouter, HTTPException

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
from app.utils.time_helpers import today_str

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


@router.get("/overview")
async def habits_overview():
    """Full dashboard: all active habits with streaks and recent logs."""
    habits = await repo.get_habits(active_only=True)
    overview = []
    for habit in habits:
        logs = await repo.get_habit_logs(habit["id"])
        streak_data = calculate_streak(logs, habit.get("target_value", 1))
        recent = logs[:7]
        overview.append({
            "habit": habit,
            "streak": {"habit_id": habit["id"], **streak_data},
            "recent_logs": recent,
        })
    return overview


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


@router.post("/{habit_id}/log", response_model=HabitLogResponse)
async def log_habit(habit_id: int, body: HabitLogRequest):
    existing = await repo.get_habit(habit_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Habit not found")
    log_date = body.date or today_str()
    result = await repo.log_habit(habit_id, log_date, body.value)
    logger.info("Habit %d logged: %.1f on %s", habit_id, body.value, log_date)
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
    return await repo.get_habit_logs(habit_id, date_from=date_from, date_to=date_to)


@router.patch("/{habit_id}/increment", response_model=HabitLogResponse)
async def increment_habit(habit_id: int, body: HabitIncrementRequest):
    """Add/subtract value to today's habit log. Useful for counters (e.g., water cups)."""
    existing = await repo.get_habit(habit_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Habit not found")
    log_date = body.date or today_str()
    result = await repo.increment_habit(habit_id, log_date, body.delta)
    logger.info("Habit %d incremented by %.1f on %s", habit_id, body.delta, log_date)
    return result
