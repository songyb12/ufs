"""Notification Schedule Settings Router — /notifications endpoints.

Allows users to configure which days/hours Discord notifications are sent.
Settings are stored in runtime_config as JSON under key 'notification_schedule'.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import repositories as repo

logger = logging.getLogger("vibe.routers.notification_settings")

router = APIRouter(prefix="/notifications", tags=["notifications"])

CONFIG_KEY = "notification_schedule"

# Default schedule: weekdays only, all hours
DEFAULT_SCHEDULE = {
    "enabled": True,
    "days": {
        "mon": True,
        "tue": True,
        "wed": True,
        "thu": True,
        "fri": True,
        "sat": False,
        "sun": False,
    },
    "quiet_hours": {
        "enabled": False,
        "start": "23:00",  # KST
        "end": "07:00",    # KST
    },
    "channels": {
        "pipeline_kr": True,
        "pipeline_us": True,
        "price_alerts": True,
        "weekly_report": True,
    },
}


class NotificationSchedule(BaseModel):
    enabled: bool = True
    days: dict[str, bool] = DEFAULT_SCHEDULE["days"]
    quiet_hours: dict = DEFAULT_SCHEDULE["quiet_hours"]
    channels: dict[str, bool] = DEFAULT_SCHEDULE["channels"]


async def _get_schedule() -> dict:
    """Get notification schedule from DB, return default if not set."""
    config = await repo.get_runtime_config()
    raw = config.get(CONFIG_KEY)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid notification_schedule JSON, returning default")
    return DEFAULT_SCHEDULE.copy()


async def should_notify(channel: str = "pipeline_kr") -> bool:
    """Check if notifications should be sent right now.

    Called by scheduler before sending Discord messages.
    Returns True if notification should proceed.
    """
    schedule = await _get_schedule()

    # Master switch
    if not schedule.get("enabled", True):
        return False

    now_utc = datetime.now(timezone.utc)
    # Convert to KST (UTC+9)
    kst_hour = (now_utc.hour + 9) % 24
    kst_weekday = now_utc.weekday()  # 0=Mon ... 6=Sun
    # If UTC hour + 9 >= 24, we're in the next day KST
    if now_utc.hour + 9 >= 24:
        kst_weekday = (kst_weekday + 1) % 7

    day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    current_day = day_names[kst_weekday]

    # Check day enabled
    days = schedule.get("days", {})
    if not days.get(current_day, True):
        logger.info("Notification suppressed: %s is disabled", current_day)
        return False

    # Check quiet hours
    quiet = schedule.get("quiet_hours", {})
    if quiet.get("enabled", False):
        try:
            start_h, start_m = map(int, quiet["start"].split(":"))
            end_h, end_m = map(int, quiet["end"].split(":"))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            now_min = kst_hour * 60 + now_utc.minute

            if start_min <= end_min:
                # Same day range (e.g., 09:00 ~ 18:00)
                if start_min <= now_min < end_min:
                    logger.info("Notification suppressed: quiet hours %s~%s", quiet["start"], quiet["end"])
                    return False
            else:
                # Overnight range (e.g., 23:00 ~ 07:00)
                if now_min >= start_min or now_min < end_min:
                    logger.info("Notification suppressed: quiet hours %s~%s", quiet["start"], quiet["end"])
                    return False
        except (ValueError, KeyError) as exc:
            logger.warning("Invalid quiet hours format, skipping check: %s", exc)

    # Check channel enabled
    channels = schedule.get("channels", {})
    if not channels.get(channel, True):
        logger.info("Notification suppressed: channel '%s' is disabled", channel)
        return False

    return True


@router.get("/schedule")
async def get_notification_schedule():
    """Get current notification schedule settings."""
    schedule = await _get_schedule()
    return schedule


@router.put("/schedule")
async def update_notification_schedule(body: NotificationSchedule):
    """Update notification schedule settings."""
    try:
        data = body.model_dump()
        await repo.upsert_runtime_config(CONFIG_KEY, json.dumps(data, ensure_ascii=False))
        logger.info("Notification schedule updated: %s", data)
        return {"status": "ok", "schedule": data}
    except Exception as e:
        logger.error("Failed to update notification schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update notification schedule. Check server logs.")


@router.get("/test")
async def test_notification_check():
    """Test if notifications would be sent right now."""
    channels = ["pipeline_kr", "pipeline_us", "price_alerts", "weekly_report"]
    results = {}
    for ch in channels:
        results[ch] = await should_notify(ch)
    return {
        "would_notify": results,
        "schedule": await _get_schedule(),
    }
