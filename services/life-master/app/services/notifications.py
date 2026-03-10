"""Notification service — Pushover (Apple Watch) and ntfy.sh support."""

import logging
from enum import StrEnum

import httpx

from app.config import settings

logger = logging.getLogger("life-master.notifications")

PUSHOVER_API = "https://api.pushover.net/1/messages.json"


class NotificationPriority(StrEnum):
    LOW = "-1"
    NORMAL = "0"
    HIGH = "1"
    URGENT = "2"  # Requires acknowledgement (Pushover)


class NotificationProvider(StrEnum):
    PUSHOVER = "pushover"
    NTFY = "ntfy"


async def send_notification(
    title: str,
    message: str,
    priority: str = NotificationPriority.NORMAL,
    url: str | None = None,
    url_title: str | None = None,
    sound: str | None = None,
) -> dict:
    """Send a notification via the configured provider.

    Returns {"ok": True/False, "provider": str, "detail": str}
    """
    if not settings.NOTIFICATION_ENABLED:
        return {"ok": False, "provider": "none", "detail": "Notifications disabled"}

    provider = settings.NOTIFICATION_PROVIDER.lower()
    if provider == "pushover":
        return await _send_pushover(title, message, priority, url, url_title, sound)
    elif provider == "ntfy":
        return await _send_ntfy(title, message, priority, url)
    else:
        return {"ok": False, "provider": provider, "detail": f"Unknown provider: {provider}"}


async def _send_pushover(
    title: str,
    message: str,
    priority: str,
    url: str | None,
    url_title: str | None,
    sound: str | None,
) -> dict:
    if not settings.PUSHOVER_USER_KEY or not settings.PUSHOVER_APP_TOKEN:
        return {"ok": False, "provider": "pushover", "detail": "Missing PUSHOVER_USER_KEY or PUSHOVER_APP_TOKEN"}

    payload: dict = {
        "token": settings.PUSHOVER_APP_TOKEN,
        "user": settings.PUSHOVER_USER_KEY,
        "title": title[:250],
        "message": message[:1024],
        "priority": int(priority),
    }
    if url:
        payload["url"] = url[:512]
    if url_title:
        payload["url_title"] = url_title[:100]
    if sound:
        payload["sound"] = sound
    # Urgent priority requires retry/expire params
    if int(priority) == 2:
        payload["retry"] = 60
        payload["expire"] = 3600

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(PUSHOVER_API, data=payload)
            if resp.status_code == 200:
                logger.info("Pushover notification sent: %s", title)
                return {"ok": True, "provider": "pushover", "detail": "sent"}
            else:
                detail = resp.text[:200]
                logger.warning("Pushover failed (%d): %s", resp.status_code, detail)
                return {"ok": False, "provider": "pushover", "detail": detail}
    except httpx.HTTPError as e:
        logger.error("Pushover HTTP error: %s", e)
        return {"ok": False, "provider": "pushover", "detail": str(e)}


async def _send_ntfy(
    title: str,
    message: str,
    priority: str,
    url: str | None,
) -> dict:
    if not settings.NTFY_TOPIC:
        return {"ok": False, "provider": "ntfy", "detail": "Missing NTFY_TOPIC"}

    # Map Pushover priority to ntfy (1-5 scale)
    priority_map = {"-1": "2", "0": "3", "1": "4", "2": "5"}
    ntfy_priority = priority_map.get(str(priority), "3")

    ntfy_url = f"{settings.NTFY_SERVER.rstrip('/')}/{settings.NTFY_TOPIC}"
    headers: dict = {
        "Title": title[:250],
        "Priority": ntfy_priority,
    }
    if url:
        headers["Click"] = url

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(ntfy_url, content=message[:4096], headers=headers)
            if resp.status_code == 200:
                logger.info("ntfy notification sent: %s", title)
                return {"ok": True, "provider": "ntfy", "detail": "sent"}
            else:
                detail = resp.text[:200]
                logger.warning("ntfy failed (%d): %s", resp.status_code, detail)
                return {"ok": False, "provider": "ntfy", "detail": detail}
    except httpx.HTTPError as e:
        logger.error("ntfy HTTP error: %s", e)
        return {"ok": False, "provider": "ntfy", "detail": str(e)}


# ── Trigger helpers ──────────────────────────────────────


async def notify_routine_reminder(routine_name: str, time_slot: str) -> dict:
    """Send a routine reminder notification."""
    title = "루틴 알림"
    message = f"'{routine_name}' ({time_slot}) 수행 시간입니다!"
    return await send_notification(title, message, NotificationPriority.NORMAL, sound="pushover")


async def notify_habit_reminder(habit_name: str, target_value: float, unit: str) -> dict:
    """Send a habit reminder."""
    title = "습관 알림"
    message = f"오늘 '{habit_name}' 기록을 잊지 마세요! (목표: {target_value}{unit})"
    return await send_notification(title, message, NotificationPriority.NORMAL)


async def notify_goal_deadline(goal_title: str, days_remaining: int) -> dict:
    """Send a goal deadline approaching notification."""
    if days_remaining <= 0:
        title = "목표 마감 경과!"
        message = f"'{goal_title}' 마감일이 지났습니다. 확인이 필요합니다."
        priority = NotificationPriority.HIGH
    elif days_remaining <= 3:
        title = "목표 마감 임박"
        message = f"'{goal_title}' 마감까지 {days_remaining}일 남았습니다!"
        priority = NotificationPriority.HIGH
    else:
        title = "목표 마감 알림"
        message = f"'{goal_title}' 마감까지 {days_remaining}일 남았습니다."
        priority = NotificationPriority.NORMAL
    return await send_notification(title, message, priority)


async def notify_streak_warning(habit_name: str, current_streak: int) -> dict:
    """Warn that a streak is about to break."""
    title = "스트릭 위험!"
    message = f"'{habit_name}' {current_streak}일 연속 기록이 끊길 위기입니다! 오늘 기록해주세요."
    return await send_notification(title, message, NotificationPriority.HIGH, sound="siren")


async def notify_daily_summary(
    routines_done: int,
    routines_total: int,
    habits_logged: int,
    habits_total: int,
) -> dict:
    """Send end-of-day summary."""
    title = "오늘의 요약"
    lines = [
        f"루틴: {routines_done}/{routines_total} 완료",
        f"습관: {habits_logged}/{habits_total} 기록",
    ]
    rate = round(routines_done / routines_total * 100) if routines_total else 0
    if rate == 100:
        lines.append("완벽한 하루였습니다! 💪")
    elif rate >= 80:
        lines.append("좋은 하루였습니다!")
    message = "\n".join(lines)
    return await send_notification(title, message, NotificationPriority.LOW)
