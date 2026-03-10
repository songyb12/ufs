"""Notification management endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.database import repositories as repo
from app.models.schemas import (
    NotificationConfigResponse,
    NotificationLogResponse,
    NotificationRuleCreate,
    NotificationRuleResponse,
    NotificationRuleUpdate,
    NotificationTestRequest,
)
from app.services.notifications import (
    notify_daily_summary,
    notify_goal_deadline,
    notify_habit_reminder,
    notify_routine_reminder,
    notify_streak_warning,
    send_notification,
)
from app.utils.time_helpers import today_day_name, today_str

logger = logging.getLogger("life-master.routers.notifications")

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/config", response_model=NotificationConfigResponse)
async def get_config():
    """Get current notification configuration status."""
    rules_count = await repo.get_notification_rules_count()
    return {
        "enabled": settings.NOTIFICATION_ENABLED,
        "provider": settings.NOTIFICATION_PROVIDER,
        "pushover_configured": bool(settings.PUSHOVER_USER_KEY and settings.PUSHOVER_APP_TOKEN),
        "ntfy_configured": bool(settings.NTFY_TOPIC),
        "ntfy_server": settings.NTFY_SERVER,
        "rules_count": rules_count,
    }


@router.post("/test")
async def test_notification(body: NotificationTestRequest | None = None):
    """Send a test notification to verify configuration."""
    if body is None:
        title = "테스트 알림"
        message = "Life-Master 알림 테스트입니다."
        priority = "0"
    else:
        title = body.title
        message = body.message
        priority = body.priority

    result = await send_notification(title, message, priority)

    # Log it
    await repo.create_notification_log({
        "rule_id": None,
        "trigger_type": "TEST",
        "title": title,
        "message": message,
        "provider": result.get("provider", "unknown"),
        "success": result.get("ok", False),
        "detail": result.get("detail"),
    })

    return result


# ── Rules CRUD ───────────────────────────────────────────


@router.get("/rules", response_model=list[NotificationRuleResponse])
async def list_rules(active_only: bool = False):
    return await repo.get_notification_rules(active_only=active_only)


@router.post("/rules", response_model=NotificationRuleResponse)
async def create_rule(body: NotificationRuleCreate):
    result = await repo.create_notification_rule(body.model_dump())
    logger.info("Notification rule created: %s", body.name)
    return result


@router.get("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def get_rule(rule_id: int):
    result = await repo.get_notification_rule(rule_id)
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.put("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def update_rule(rule_id: int, body: NotificationRuleUpdate):
    result = await repo.update_notification_rule(rule_id, body.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int):
    ok = await repo.delete_notification_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": rule_id}


# ── Trigger endpoints ────────────────────────────────────


@router.post("/trigger/routine-reminders")
async def trigger_routine_reminders():
    """Trigger all active routine reminder notifications for now."""
    day_name = today_day_name()
    rules = await repo.get_active_rules_for_trigger("ROUTINE_REMINDER", day_name)
    results = []
    for rule in rules:
        target_id = rule.get("target_id")
        if target_id:
            routine = await repo.get_routine(target_id)
            if routine and routine.get("is_active"):
                result = await notify_routine_reminder(routine["name"], routine.get("time_slot", "FLEXIBLE"))
                await _log_and_update(rule, "루틴 알림", routine["name"], result)
                results.append({"rule_id": rule["id"], "routine": routine["name"], **result})
    return {"triggered": len(results), "results": results}


@router.post("/trigger/habit-reminders")
async def trigger_habit_reminders():
    """Trigger habit reminder notifications."""
    day_name = today_day_name()
    rules = await repo.get_active_rules_for_trigger("HABIT_REMINDER", day_name)
    results = []
    for rule in rules:
        target_id = rule.get("target_id")
        if target_id:
            habit = await repo.get_habit(target_id)
            if habit and habit.get("is_active"):
                result = await notify_habit_reminder(habit["name"], habit.get("target_value", 1), habit.get("unit", "회"))
                await _log_and_update(rule, "습관 알림", habit["name"], result)
                results.append({"rule_id": rule["id"], "habit": habit["name"], **result})
    return {"triggered": len(results), "results": results}


@router.post("/trigger/goal-deadlines")
async def trigger_goal_deadlines():
    """Check goal deadlines and send notifications."""
    from datetime import date as d

    rules = await repo.get_active_rules_for_trigger("GOAL_DEADLINE", today_day_name())
    results = []

    # Also auto-check all active goals with deadlines
    upcoming = await repo.get_upcoming_deadlines(20)
    overdue = await repo.get_overdue_goals()

    for goal in overdue:
        days_left = (d.fromisoformat(goal["deadline"]) - d.today()).days
        result = await notify_goal_deadline(goal["title"], days_left)
        await repo.create_notification_log({
            "rule_id": None,
            "trigger_type": "GOAL_DEADLINE",
            "title": "목표 마감 경과",
            "message": goal["title"],
            "provider": result.get("provider", "unknown"),
            "success": result.get("ok", False),
            "detail": result.get("detail"),
        })
        results.append({"goal": goal["title"], "days": days_left, **result})

    for goal in upcoming:
        if goal.get("days_remaining", 999) <= 7:
            result = await notify_goal_deadline(goal["title"], goal["days_remaining"])
            await repo.create_notification_log({
                "rule_id": None,
                "trigger_type": "GOAL_DEADLINE",
                "title": "목표 마감 알림",
                "message": goal["title"],
                "provider": result.get("provider", "unknown"),
                "success": result.get("ok", False),
                "detail": result.get("detail"),
            })
            results.append({"goal": goal["title"], "days": goal["days_remaining"], **result})

    return {"triggered": len(results), "results": results}


@router.post("/trigger/streak-warnings")
async def trigger_streak_warnings():
    """Check habits with active streaks that haven't been logged today."""
    from app.services.streak import calculate_streak

    today = today_str()
    habits = await repo.get_habits(active_only=True)
    results = []

    for h in habits:
        logs = await repo.get_habit_logs(h["id"])
        streak_info = calculate_streak(logs, h.get("target_value", 1))
        if streak_info["current_streak"] >= 3:
            # Check if already logged today
            today_logs = [l for l in logs if l["date"] == today]
            if not today_logs:
                result = await notify_streak_warning(h["name"], streak_info["current_streak"])
                await repo.create_notification_log({
                    "rule_id": None,
                    "trigger_type": "STREAK_WARNING",
                    "title": "스트릭 위험",
                    "message": h["name"],
                    "provider": result.get("provider", "unknown"),
                    "success": result.get("ok", False),
                    "detail": result.get("detail"),
                })
                results.append({"habit": h["name"], "streak": streak_info["current_streak"], **result})

    return {"triggered": len(results), "results": results}


@router.post("/trigger/daily-summary")
async def trigger_daily_summary():
    """Send daily summary notification."""
    today = today_str()
    day_name = today_day_name()
    dashboard = await repo.get_dashboard_data(today, day_name)

    result = await notify_daily_summary(
        dashboard["routines_done"],
        dashboard["routines_total"],
        dashboard["habits_logged_today"],
        dashboard["habits_total"],
    )

    await repo.create_notification_log({
        "rule_id": None,
        "trigger_type": "DAILY_SUMMARY",
        "title": "오늘의 요약",
        "message": f"루틴 {dashboard['routines_done']}/{dashboard['routines_total']}, 습관 {dashboard['habits_logged_today']}/{dashboard['habits_total']}",
        "provider": result.get("provider", "unknown"),
        "success": result.get("ok", False),
        "detail": result.get("detail"),
    })

    return {**result, "summary": dashboard}


# ── Logs ─────────────────────────────────────────────────


@router.get("/logs", response_model=list[NotificationLogResponse])
async def list_logs(limit: int = Query(default=50, ge=1, le=500)):
    return await repo.get_notification_logs(limit=limit)


# ── Helpers ──────────────────────────────────────────────


async def _log_and_update(rule: dict, title: str, message: str, result: dict) -> None:
    await repo.create_notification_log({
        "rule_id": rule["id"],
        "trigger_type": rule["trigger_type"],
        "title": title,
        "message": message,
        "provider": result.get("provider", "unknown"),
        "success": result.get("ok", False),
        "detail": result.get("detail"),
    })
    if result.get("ok"):
        await repo.update_rule_last_sent(rule["id"])
