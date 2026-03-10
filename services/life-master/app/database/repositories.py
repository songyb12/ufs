"""Data access layer — pure async SQL functions."""

import json
from datetime import date, datetime, timedelta, timezone

from app.database.connection import get_db


def _escape_like(s: str) -> str:
    """Escape LIKE wildcards for literal matching."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _now() -> str:
    """Return current UTC time in SQLite-compatible format (no timezone suffix)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _parse_routine(row) -> dict:
    """Parse routine row, converting repeat_days JSON string to list."""
    d = dict(row)
    if isinstance(d.get("repeat_days"), str):
        try:
            d["repeat_days"] = json.loads(d["repeat_days"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


# ── Routines ──────────────────────────────────────────────


async def get_routines(
    category: str | None = None,
    time_slot: str | None = None,
    active_only: bool = True,
) -> list[dict]:
    db = await get_db()
    q = "SELECT * FROM routines WHERE 1=1"
    params: list = []
    if active_only:
        q += " AND is_active = 1"
    if category:
        q += " AND category = ?"
        params.append(category)
    if time_slot:
        q += " AND time_slot = ?"
        params.append(time_slot)
    q += " ORDER BY sort_order, priority DESC, name"
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [_parse_routine(r) for r in rows]


async def get_routine(routine_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM routines WHERE id = ?", (routine_id,))
    row = await cursor.fetchone()
    return _parse_routine(row) if row else None


async def create_routine(data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO routines (name, description, category, time_slot, duration_min, priority, repeat_days, sort_order, color, icon)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data.get("description"),
            data.get("category", "GENERAL"),
            data.get("time_slot", "FLEXIBLE"),
            data.get("duration_min", 30),
            data.get("priority", 3),
            json.dumps(data.get("repeat_days", ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])),
            data.get("sort_order", 0),
            data.get("color", "#6366f1"),
            data.get("icon"),
        ),
    )
    await db.commit()
    return await get_routine(cursor.lastrowid)


async def update_routine(routine_id: int, data: dict) -> dict | None:
    db = await get_db()
    fields = []
    params = []
    for key in ("name", "description", "category", "time_slot", "duration_min", "priority", "is_active", "sort_order", "color", "icon"):
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if "repeat_days" in data:
        fields.append("repeat_days = ?")
        params.append(json.dumps(data["repeat_days"]))
    if not fields:
        return await get_routine(routine_id)
    fields.append("updated_at = ?")
    params.append(_now())
    params.append(routine_id)
    await db.execute(
        f"UPDATE routines SET {', '.join(fields)} WHERE id = ?", params
    )
    await db.commit()
    return await get_routine(routine_id)


async def delete_routine(routine_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE routines SET is_active = 0, updated_at = ? WHERE id = ? AND is_active = 1",
        (_now(), routine_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def restore_routine(routine_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE routines SET is_active = 1, updated_at = ? WHERE id = ? AND is_active = 0",
        (_now(), routine_id),
    )
    await db.commit()
    return await get_routine(routine_id) if cursor.rowcount > 0 else None


async def bulk_set_active(routine_ids: list[int], is_active: int) -> int:
    if not routine_ids:
        return 0
    db = await get_db()
    placeholders = ",".join("?" for _ in routine_ids)
    cursor = await db.execute(
        f"UPDATE routines SET is_active = ?, updated_at = ? WHERE id IN ({placeholders})",
        [is_active, _now()] + routine_ids,
    )
    await db.commit()
    return cursor.rowcount


async def search_routines(keyword: str) -> list[dict]:
    db = await get_db()
    escaped = _escape_like(keyword)
    cursor = await db.execute(
        "SELECT * FROM routines WHERE (name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\') ORDER BY is_active DESC, name",
        (f"%{escaped}%", f"%{escaped}%"),
    )
    rows = await cursor.fetchall()
    return [_parse_routine(r) for r in rows]


# ── Routine Logs ──────────────────────────────────────────


async def get_routine_logs(
    routine_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    db = await get_db()
    q = "SELECT * FROM routine_logs WHERE 1=1"
    params: list = []
    if routine_id is not None:
        q += " AND routine_id = ?"
        params.append(routine_id)
    if date_from:
        q += " AND date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND date <= ?"
        params.append(date_to)
    q += " ORDER BY date DESC, routine_id"
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def check_routine(routine_id: int, log_date: str, status: str, note: str | None = None) -> dict:
    db = await get_db()
    now = _now()
    await db.execute(
        """INSERT INTO routine_logs (routine_id, date, status, completed_at, note)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(routine_id, date) DO UPDATE SET
             status = excluded.status,
             completed_at = excluded.completed_at,
             note = excluded.note""",
        (routine_id, log_date, str(status), now if str(status) == "DONE" else None, note),
    )
    await db.commit()
    cursor = await db.execute(
        "SELECT * FROM routine_logs WHERE routine_id = ? AND date = ?",
        (routine_id, log_date),
    )
    row = await cursor.fetchone()
    return dict(row)


async def uncheck_routine(routine_id: int, log_date: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM routine_logs WHERE routine_id = ? AND date = ?",
        (routine_id, log_date),
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_routine_log(log_id: int, routine_id: int | None = None) -> bool:
    db = await get_db()
    if routine_id is not None:
        cursor = await db.execute(
            "DELETE FROM routine_logs WHERE id = ? AND routine_id = ?", (log_id, routine_id)
        )
    else:
        cursor = await db.execute("DELETE FROM routine_logs WHERE id = ?", (log_id,))
    await db.commit()
    return cursor.rowcount > 0


async def get_today_routines(today: str, day_name: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT r.*, rl.status as log_status, rl.note as log_note
           FROM routines r
           LEFT JOIN routine_logs rl ON r.id = rl.routine_id AND rl.date = ?
           WHERE r.is_active = 1 AND r.repeat_days LIKE ?
           ORDER BY
             r.sort_order,
             CASE r.time_slot
               WHEN 'MORNING' THEN 1
               WHEN 'AFTERNOON' THEN 2
               WHEN 'EVENING' THEN 3
               ELSE 4
             END,
             r.priority DESC""",
        (today, f'%"{day_name}"%'),
    )
    rows = await cursor.fetchall()
    return [_parse_routine(r) for r in rows]


async def get_routine_stats(routine_id: int | None, date_from: str, date_to: str) -> dict:
    db = await get_db()
    q_base = "SELECT COUNT(*) as cnt FROM routine_logs WHERE date >= ? AND date <= ?"
    params: list = [date_from, date_to]
    if routine_id is not None:
        q_base += " AND routine_id = ?"
        params.append(routine_id)

    cursor = await db.execute(q_base, params)
    total = (await cursor.fetchone())["cnt"]

    cursor2 = await db.execute(
        q_base.replace("COUNT(*) as cnt", "status, COUNT(*) as cnt") + " GROUP BY status",
        params,
    )
    status_counts = {row["status"]: row["cnt"] for row in await cursor2.fetchall()}

    # Daily breakdown
    cursor3 = await db.execute(
        q_base.replace("COUNT(*) as cnt", "date, status, COUNT(*) as cnt") + " GROUP BY date, status ORDER BY date",
        params,
    )
    daily_raw = [dict(r) for r in await cursor3.fetchall()]
    daily_map: dict[str, dict] = {}
    for row in daily_raw:
        d = row["date"]
        if d not in daily_map:
            daily_map[d] = {"date": d, "done": 0, "skipped": 0, "partial": 0}
        status_key = (row["status"] or "").lower()
        if status_key in ("done", "skipped", "partial"):
            daily_map[d][status_key] = row["cnt"]
    daily_breakdown = sorted(daily_map.values(), key=lambda x: x["date"])

    return {
        "total_logs": total,
        "done": status_counts.get("DONE", 0),
        "skipped": status_counts.get("SKIPPED", 0),
        "partial": status_counts.get("PARTIAL", 0),
        "completion_rate": round(status_counts.get("DONE", 0) / total, 3) if total > 0 else 0,
        "date_from": date_from,
        "date_to": date_to,
        "daily_breakdown": daily_breakdown,
    }


async def get_routine_heatmap(routine_id: int | None, date_from: str, date_to: str) -> list[dict]:
    db = await get_db()
    q = "SELECT date, COUNT(*) as total, SUM(CASE WHEN status = 'DONE' THEN 1 ELSE 0 END) as done FROM routine_logs WHERE date >= ? AND date <= ?"
    params: list = [date_from, date_to]
    if routine_id is not None:
        q += " AND routine_id = ?"
        params.append(routine_id)
    q += " GROUP BY date ORDER BY date"
    cursor = await db.execute(q, params)
    return [dict(r) for r in await cursor.fetchall()]


async def get_routine_category_stats(date_from: str, date_to: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT r.category, COUNT(rl.id) as total, SUM(CASE WHEN rl.status = 'DONE' THEN 1 ELSE 0 END) as done
           FROM routines r
           JOIN routine_logs rl ON r.id = rl.routine_id
           WHERE rl.date >= ? AND rl.date <= ?
           GROUP BY r.category""",
        (date_from, date_to),
    )
    return [dict(r) for r in await cursor.fetchall()]


# ── Habits ────────────────────────────────────────────────


async def get_habits(active_only: bool = True) -> list[dict]:
    db = await get_db()
    q = "SELECT * FROM habits"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY name"
    cursor = await db.execute(q)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_habit(habit_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM habits WHERE id = ?", (habit_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_habit(data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO habits (name, description, target_type, target_value, unit, color, icon)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data.get("description"),
            data.get("target_type", "DAILY"),
            data.get("target_value", 1),
            data.get("unit", "회"),
            data.get("color", "#6366f1"),
            data.get("icon"),
        ),
    )
    await db.commit()
    return await get_habit(cursor.lastrowid)


async def update_habit(habit_id: int, data: dict) -> dict | None:
    db = await get_db()
    fields = []
    params = []
    for key in ("name", "description", "target_type", "target_value", "unit", "color", "icon", "is_active"):
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        return await get_habit(habit_id)
    fields.append("updated_at = ?")
    params.append(_now())
    params.append(habit_id)
    await db.execute(f"UPDATE habits SET {', '.join(fields)} WHERE id = ?", params)
    await db.commit()
    return await get_habit(habit_id)


async def delete_habit(habit_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE habits SET is_active = 0, updated_at = ? WHERE id = ? AND is_active = 1",
        (_now(), habit_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def restore_habit(habit_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE habits SET is_active = 1, updated_at = ? WHERE id = ? AND is_active = 0",
        (_now(), habit_id),
    )
    await db.commit()
    return await get_habit(habit_id) if cursor.rowcount > 0 else None


async def log_habit(habit_id: int, log_date: str, value: float) -> dict:
    db = await get_db()
    await db.execute(
        """INSERT INTO habit_logs (habit_id, date, value)
           VALUES (?, ?, ?)
           ON CONFLICT(habit_id, date) DO UPDATE SET value = excluded.value""",
        (habit_id, log_date, value),
    )
    await db.commit()
    cursor = await db.execute(
        "SELECT * FROM habit_logs WHERE habit_id = ? AND date = ?",
        (habit_id, log_date),
    )
    row = await cursor.fetchone()
    return dict(row)


async def get_habit_logs(
    habit_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    db = await get_db()
    q = "SELECT * FROM habit_logs WHERE habit_id = ?"
    params: list = [habit_id]
    if date_from:
        q += " AND date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND date <= ?"
        params.append(date_to)
    q += " ORDER BY date DESC"
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_all_habit_logs_for_date(log_date: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM habit_logs WHERE date = ? ORDER BY habit_id", (log_date,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def delete_habit_log(log_id: int, habit_id: int | None = None) -> bool:
    db = await get_db()
    if habit_id is not None:
        cursor = await db.execute(
            "DELETE FROM habit_logs WHERE id = ? AND habit_id = ?", (log_id, habit_id)
        )
    else:
        cursor = await db.execute("DELETE FROM habit_logs WHERE id = ?", (log_id,))
    await db.commit()
    return cursor.rowcount > 0


async def get_habit_heatmap(habit_id: int, date_from: str, date_to: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT date, value FROM habit_logs WHERE habit_id = ? AND date >= ? AND date <= ? ORDER BY date",
        (habit_id, date_from, date_to),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_habit_trend(habit_id: int, date_from: str, date_to: str) -> list[dict]:
    """Daily achievement rate for the period."""
    db = await get_db()
    habit = await get_habit(habit_id)
    if not habit:
        return []
    target = habit.get("target_value", 1)
    cursor = await db.execute(
        "SELECT date, value FROM habit_logs WHERE habit_id = ? AND date >= ? AND date <= ? ORDER BY date",
        (habit_id, date_from, date_to),
    )
    result = []
    for r in await cursor.fetchall():
        d = dict(r)
        d["achieved"] = 1 if d["value"] >= target else 0
        d["rate"] = round(d["value"] / target, 3) if target > 0 else 0
        result.append(d)
    return result


async def search_habits(keyword: str) -> list[dict]:
    db = await get_db()
    escaped = _escape_like(keyword)
    cursor = await db.execute(
        "SELECT * FROM habits WHERE (name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\') ORDER BY is_active DESC, name",
        (f"%{escaped}%", f"%{escaped}%"),
    )
    return [dict(r) for r in await cursor.fetchall()]


# ── Goals ─────────────────────────────────────────────────


async def get_goals(
    status: str | None = None,
    category: str | None = None,
) -> list[dict]:
    db = await get_db()
    q = "SELECT * FROM goals WHERE 1=1"
    params: list = []
    if status:
        q += " AND status = ?"
        params.append(status)
    if category:
        q += " AND category = ?"
        params.append(category)
    q += " ORDER BY CASE status WHEN 'ACTIVE' THEN 0 WHEN 'PAUSED' THEN 1 WHEN 'ACHIEVED' THEN 2 ELSE 3 END, priority DESC, deadline NULLS LAST, created_at DESC"
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_goals_with_milestone_counts(status: str | None = None, category: str | None = None) -> list[dict]:
    db = await get_db()
    q = """SELECT g.*,
           COALESCE(ms.total, 0) as milestone_total,
           COALESCE(ms.done, 0) as milestone_done
           FROM goals g
           LEFT JOIN (
               SELECT goal_id, COUNT(*) as total, COALESCE(SUM(is_completed), 0) as done
               FROM milestones GROUP BY goal_id
           ) ms ON g.id = ms.goal_id
           WHERE 1=1"""
    params: list = []
    if status:
        q += " AND g.status = ?"
        params.append(status)
    if category:
        q += " AND g.category = ?"
        params.append(category)
    q += " ORDER BY CASE g.status WHEN 'ACTIVE' THEN 0 WHEN 'PAUSED' THEN 1 WHEN 'ACHIEVED' THEN 2 ELSE 3 END, g.priority DESC, g.deadline NULLS LAST"
    cursor = await db.execute(q, params)
    return [dict(r) for r in await cursor.fetchall()]


async def get_goal(goal_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_goal(data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO goals (title, description, category, deadline, status, progress, priority, color)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["title"],
            data.get("description"),
            data.get("category", "GENERAL"),
            data.get("deadline"),
            data.get("status", "ACTIVE"),
            data.get("progress", 0.0),
            data.get("priority", 3),
            data.get("color", "#6366f1"),
        ),
    )
    await db.commit()
    return await get_goal(cursor.lastrowid)


async def update_goal(goal_id: int, data: dict) -> dict | None:
    db = await get_db()
    fields = []
    params = []
    for key in ("title", "description", "category", "deadline", "status", "progress", "priority", "color"):
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        return await get_goal(goal_id)
    fields.append("updated_at = ?")
    params.append(_now())
    params.append(goal_id)
    await db.execute(f"UPDATE goals SET {', '.join(fields)} WHERE id = ?", params)
    await db.commit()
    return await get_goal(goal_id)


async def update_goal_progress(goal_id: int, progress: float) -> dict | None:
    db = await get_db()
    status_update = ""
    if progress >= 1.0:
        status_update = ", status = 'ACHIEVED'"
    await db.execute(
        f"UPDATE goals SET progress = ?, updated_at = ?{status_update} WHERE id = ?",
        (max(0.0, min(progress, 1.0)), _now(), goal_id),
    )
    await db.commit()
    return await get_goal(goal_id)


async def abandon_goal(goal_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE goals SET status = 'ABANDONED', updated_at = ? WHERE id = ? AND status IN ('ACTIVE', 'PAUSED')",
        (_now(), goal_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    return await get_goal(goal_id)


async def reactivate_goal(goal_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE goals SET status = 'ACTIVE', updated_at = ? WHERE id = ? AND status != 'ACTIVE'",
        (_now(), goal_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    return await get_goal(goal_id)


async def pause_goal(goal_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE goals SET status = 'PAUSED', updated_at = ? WHERE id = ? AND status = 'ACTIVE'",
        (_now(), goal_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    return await get_goal(goal_id)


async def get_upcoming_deadlines(limit: int = 5) -> list[dict]:
    db = await get_db()
    today = date.today().isoformat()
    cursor = await db.execute(
        """SELECT id, title, deadline, status, progress, category
           FROM goals WHERE status = 'ACTIVE' AND deadline IS NOT NULL AND deadline >= ?
           ORDER BY deadline LIMIT ?""",
        (today, limit),
    )
    result = []
    for r in await cursor.fetchall():
        d = dict(r)
        d["days_remaining"] = (date.fromisoformat(d["deadline"]) - date.today()).days
        result.append(d)
    return result


async def get_overdue_goals() -> list[dict]:
    db = await get_db()
    today = date.today().isoformat()
    cursor = await db.execute(
        "SELECT * FROM goals WHERE status = 'ACTIVE' AND deadline IS NOT NULL AND deadline < ?",
        (today,),
    )
    return [dict(r) for r in await cursor.fetchall()]


# ── Milestones ────────────────────────────────────────────


async def get_milestones(goal_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM milestones WHERE goal_id = ? ORDER BY sort_order, target_date NULLS LAST",
        (goal_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_milestone(milestone_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_milestone(goal_id: int, data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO milestones (goal_id, title, target_date, sort_order)
           VALUES (?, ?, ?, ?)""",
        (goal_id, data["title"], data.get("target_date"), data.get("sort_order", 0)),
    )
    await db.commit()
    return await get_milestone(cursor.lastrowid)


async def create_milestones_bulk(goal_id: int, items: list[dict]) -> list[dict]:
    results = []
    for item in items:
        results.append(await create_milestone(goal_id, item))
    return results


async def update_milestone(milestone_id: int, data: dict) -> dict | None:
    db = await get_db()
    fields = []
    params = []
    for key in ("title", "target_date", "sort_order", "is_completed"):
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if "is_completed" in data:
        if data["is_completed"]:
            fields.append("completed_at = ?")
            params.append(_now())
        else:
            fields.append("completed_at = ?")
            params.append(None)
    if not fields:
        return await get_milestone(milestone_id)
    params.append(milestone_id)
    cursor = await db.execute(f"UPDATE milestones SET {', '.join(fields)} WHERE id = ?", params)
    await db.commit()
    if cursor.rowcount == 0:
        return None
    result = await get_milestone(milestone_id)
    if "is_completed" in data and result:
        # Get goal_id to sync progress
        goal_id = result.get("goal_id")
        if goal_id:
            await _sync_goal_progress(goal_id)
            result = await get_milestone(milestone_id)
    return result


async def delete_milestone(milestone_id: int, goal_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM milestones WHERE id = ? AND goal_id = ?",
        (milestone_id, goal_id),
    )
    await db.commit()
    if cursor.rowcount > 0:
        await _sync_goal_progress(goal_id)
        return True
    return False


async def complete_milestone(milestone_id: int, goal_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE milestones SET is_completed = 1, completed_at = ? WHERE id = ? AND goal_id = ?",
        (_now(), milestone_id, goal_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    await _sync_goal_progress(goal_id)
    return await get_milestone(milestone_id)


async def uncomplete_milestone(milestone_id: int, goal_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE milestones SET is_completed = 0, completed_at = NULL WHERE id = ? AND goal_id = ?",
        (milestone_id, goal_id),
    )
    await db.commit()
    if cursor.rowcount == 0:
        return None
    await _sync_goal_progress(goal_id)
    return await get_milestone(milestone_id)


async def _sync_goal_progress(goal_id: int) -> None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) as total, COALESCE(SUM(is_completed), 0) as done FROM milestones WHERE goal_id = ?",
        (goal_id,),
    )
    row = await cursor.fetchone()
    if row and row["total"] > 0:
        done = row["done"] or 0
        new_progress = done / row["total"]
        await update_goal_progress(goal_id, new_progress)


# ── Schedule Blocks ───────────────────────────────────────


async def get_schedule_blocks(
    date_val: str,
    date_end: str | None = None,
) -> list[dict]:
    db = await get_db()
    if date_end:
        cursor = await db.execute(
            "SELECT * FROM schedule_blocks WHERE date >= ? AND date <= ? ORDER BY date, start_time",
            (date_val, date_end),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM schedule_blocks WHERE date = ? ORDER BY start_time",
            (date_val,),
        )
    rows = await cursor.fetchall()
    return [_enrich_block(r) for r in rows]


def _enrich_block(row) -> dict:
    d = dict(row)
    try:
        sh, sm = d["start_time"].split(":")
        eh, em = d["end_time"].split(":")
        duration = (int(eh) * 60 + int(em)) - (int(sh) * 60 + int(sm))
        d["duration_min"] = max(0, duration)
    except (ValueError, KeyError):
        d["duration_min"] = 0
    return d


async def create_schedule_block(data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO schedule_blocks (date, start_time, end_time, title, source, routine_id, priority, is_locked, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["date"],
            data["start_time"],
            data["end_time"],
            data["title"],
            data.get("source", "MANUAL"),
            data.get("routine_id"),
            data.get("priority", 3),
            data.get("is_locked", 0),
            data.get("note"),
        ),
    )
    await db.commit()
    cursor2 = await db.execute("SELECT * FROM schedule_blocks WHERE id = ?", (cursor.lastrowid,))
    row = await cursor2.fetchone()
    return _enrich_block(row)


async def update_schedule_block(block_id: int, data: dict) -> dict | None:
    db = await get_db()
    fields = []
    params = []
    for key in ("date", "start_time", "end_time", "title", "priority", "is_locked", "note"):
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        cursor = await db.execute("SELECT * FROM schedule_blocks WHERE id = ?", (block_id,))
        row = await cursor.fetchone()
        return _enrich_block(row) if row else None
    params.append(block_id)
    await db.execute(f"UPDATE schedule_blocks SET {', '.join(fields)} WHERE id = ?", params)
    await db.commit()
    cursor = await db.execute("SELECT * FROM schedule_blocks WHERE id = ?", (block_id,))
    row = await cursor.fetchone()
    return _enrich_block(row) if row else None


async def delete_schedule_block(block_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM schedule_blocks WHERE id = ?", (block_id,))
    await db.commit()
    return cursor.rowcount > 0


async def delete_generated_blocks(date_val: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM schedule_blocks WHERE date = ? AND source = 'GENERATED'",
        (date_val,),
    )
    await db.commit()
    return cursor.rowcount


async def copy_schedule_block(block_id: int, target_date: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM schedule_blocks WHERE id = ?", (block_id,))
    row = await cursor.fetchone()
    if not row:
        return None
    original = dict(row)
    data = {
        "date": target_date,
        "start_time": original["start_time"],
        "end_time": original["end_time"],
        "title": original["title"],
        "source": "MANUAL",
        "routine_id": original.get("routine_id"),
        "priority": original["priority"],
        "is_locked": 0,
        "note": original.get("note"),
    }
    return await create_schedule_block(data)


async def get_month_schedule(year: int, month: int) -> list[dict]:
    db = await get_db()
    date_from = f"{year:04d}-{month:02d}-01"
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    date_to = last_day.isoformat()
    cursor = await db.execute(
        "SELECT * FROM schedule_blocks WHERE date >= ? AND date <= ? ORDER BY date, start_time",
        (date_from, date_to),
    )
    return [_enrich_block(r) for r in await cursor.fetchall()]


# ── Schedule Templates ────────────────────────────────────


async def get_templates(day_of_week: str | None = None) -> list[dict]:
    db = await get_db()
    if day_of_week:
        cursor = await db.execute(
            "SELECT * FROM schedule_templates WHERE day_of_week = ? AND is_active = 1 ORDER BY name",
            (day_of_week,),
        )
    else:
        cursor = await db.execute("SELECT * FROM schedule_templates WHERE is_active = 1 ORDER BY day_of_week, name")
    return [dict(r) for r in await cursor.fetchall()]


async def create_template(data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO schedule_templates (name, day_of_week, blocks_json) VALUES (?, ?, ?)",
        (data["name"], data["day_of_week"], json.dumps(data.get("blocks", []))),
    )
    await db.commit()
    cursor2 = await db.execute("SELECT * FROM schedule_templates WHERE id = ?", (cursor.lastrowid,))
    return dict(await cursor2.fetchone())


async def apply_template(template_id: int, target_date: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM schedule_templates WHERE id = ?", (template_id,))
    row = await cursor.fetchone()
    if not row:
        return []
    blocks = json.loads(row["blocks_json"])
    saved = []
    for b in blocks:
        block_data = {**b, "date": target_date, "source": "TEMPLATE"}
        saved.append(await create_schedule_block(block_data))
    return saved


async def delete_template(template_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM schedule_templates WHERE id = ?", (template_id,))
    await db.commit()
    return cursor.rowcount > 0


# ── Conflict Detection ───────────────────────────────────


async def detect_conflicts(date_val: str, start_time: str, end_time: str, exclude_id: int | None = None) -> list[dict]:
    db = await get_db()
    q = """SELECT * FROM schedule_blocks
           WHERE date = ? AND start_time < ? AND end_time > ?"""
    params: list = [date_val, end_time, start_time]
    if exclude_id is not None:
        q += " AND id != ?"
        params.append(exclude_id)
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Duplicate / Clone ─────────────────────────────────────


async def duplicate_routine(routine_id: int) -> dict | None:
    original = await get_routine(routine_id)
    if not original:
        return None
    data = {
        "name": f"{original['name']} (copy)",
        "description": original.get("description"),
        "category": original["category"],
        "time_slot": original["time_slot"],
        "duration_min": original["duration_min"],
        "priority": original["priority"],
        "repeat_days": original["repeat_days"] if isinstance(original["repeat_days"], list) else json.loads(original["repeat_days"]),
        "sort_order": original.get("sort_order", 0),
        "color": original.get("color", "#6366f1"),
        "icon": original.get("icon"),
    }
    return await create_routine(data)


# ── Habit Increment ───────────────────────────────────────


async def increment_habit(habit_id: int, log_date: str, delta: float) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "SELECT value FROM habit_logs WHERE habit_id = ? AND date = ?",
        (habit_id, log_date),
    )
    row = await cursor.fetchone()
    new_value = max(0, (row["value"] if row else 0) + delta)
    return await log_habit(habit_id, log_date, new_value)


# ── Bulk Check ────────────────────────────────────────────


async def bulk_check_routines(items: list[dict], log_date: str) -> list[dict]:
    results = []
    for item in items:
        routine = await get_routine(item["routine_id"])
        if not routine:
            continue
        result = await check_routine(item["routine_id"], log_date, item["status"], item.get("note"))
        results.append(result)
    return results


# ── Data Retention ────────────────────────────────────────


async def cleanup_old_logs(retention_days: int) -> dict:
    db = await get_db()
    cutoff = (date.today() - timedelta(days=retention_days)).isoformat()

    c1 = await db.execute("DELETE FROM routine_logs WHERE date < ?", (cutoff,))
    c2 = await db.execute("DELETE FROM habit_logs WHERE date < ?", (cutoff,))
    c3 = await db.execute("DELETE FROM schedule_blocks WHERE date < ? AND is_locked = 0", (cutoff,))
    await db.commit()
    return {
        "cutoff_date": cutoff,
        "routine_logs_deleted": c1.rowcount,
        "habit_logs_deleted": c2.rowcount,
        "schedule_blocks_deleted": c3.rowcount,
    }


# ── Dashboard Aggregates ─────────────────────────────────


async def get_dashboard_data(today: str, day_name: str) -> dict:
    db = await get_db()

    today_rts = await get_today_routines(today, day_name)
    done_count = sum(1 for r in today_rts if r.get("log_status") == "DONE")
    remaining = len(today_rts) - done_count

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM habits WHERE is_active = 1")
    habits_total = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        "SELECT COUNT(DISTINCT habit_id) as cnt FROM habit_logs WHERE date = ?", (today,)
    )
    habits_logged = (await cursor.fetchone())["cnt"]

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM goals WHERE status = 'ACTIVE'")
    active_goals = (await cursor.fetchone())["cnt"]

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM schedule_blocks WHERE date = ?", (today,))
    block_count = (await cursor.fetchone())["cnt"]

    upcoming = await get_upcoming_deadlines(5)
    overdue = await get_overdue_goals()

    return {
        "date": today,
        "routines_total": len(today_rts),
        "routines_done": done_count,
        "routines_remaining": remaining,
        "routines_completion": round(done_count / len(today_rts), 3) if today_rts else 0,
        "habits_logged_today": habits_logged,
        "habits_total": habits_total,
        "active_goals": active_goals,
        "schedule_blocks": block_count,
        "upcoming_deadlines": upcoming,
        "overdue_goals": [{"id": g["id"], "title": g["title"], "deadline": g["deadline"]} for g in overdue],
    }


# ── Weekly / Monthly Report ──────────────────────────────


async def get_weekly_report(date_from: str, date_to: str) -> dict:
    db = await get_db()

    cursor = await db.execute(
        "SELECT status, COUNT(*) as cnt FROM routine_logs WHERE date >= ? AND date <= ? GROUP BY status",
        (date_from, date_to),
    )
    routine_stats = {row["status"]: row["cnt"] for row in await cursor.fetchall()}

    cursor = await db.execute(
        """SELECT h.name, COUNT(hl.id) as log_count, COALESCE(SUM(hl.value), 0) as total_value
           FROM habits h
           LEFT JOIN habit_logs hl ON h.id = hl.habit_id AND hl.date >= ? AND hl.date <= ?
           WHERE h.is_active = 1
           GROUP BY h.id""",
        (date_from, date_to),
    )
    habit_stats = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        "SELECT id, title, status, progress FROM goals WHERE updated_at >= ? AND updated_at < ?",
        (date_from, date_to + " 23:59:59"),
    )
    goal_updates = [dict(r) for r in await cursor.fetchall()]

    return {
        "date_from": date_from,
        "date_to": date_to,
        "routine_summary": {
            "done": routine_stats.get("DONE", 0),
            "skipped": routine_stats.get("SKIPPED", 0),
            "partial": routine_stats.get("PARTIAL", 0),
        },
        "habit_stats": habit_stats,
        "goal_updates": goal_updates,
    }


async def get_monthly_report(year: int, month: int) -> dict:
    date_from = f"{year:04d}-{month:02d}-01"
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    date_to = last_day.isoformat()
    return await get_weekly_report(date_from, date_to)


# ── Export / Import ───────────────────────────────────────


async def export_all() -> dict:
    db = await get_db()

    routines = [_parse_routine(r) for r in await (await db.execute("SELECT * FROM routines")).fetchall()]
    habits = [dict(r) for r in await (await db.execute("SELECT * FROM habits")).fetchall()]
    goals = [dict(r) for r in await (await db.execute("SELECT * FROM goals")).fetchall()]
    milestones = [dict(r) for r in await (await db.execute("SELECT * FROM milestones")).fetchall()]
    routine_logs = [dict(r) for r in await (await db.execute("SELECT * FROM routine_logs")).fetchall()]
    habit_logs = [dict(r) for r in await (await db.execute("SELECT * FROM habit_logs")).fetchall()]

    cursor = await db.execute("SELECT value FROM schema_meta WHERE key = 'version'")
    row = await cursor.fetchone()
    schema_ver = row["value"] if row else "0"

    return {
        "exported_at": _now(),
        "schema_version": schema_ver,
        "routines": routines,
        "habits": habits,
        "goals": goals,
        "milestones": milestones,
        "routine_logs": routine_logs,
        "habit_logs": habit_logs,
    }


# ── Admin / DB Info ───────────────────────────────────────


async def get_db_info() -> dict:
    db = await get_db()
    tables = ["routines", "routine_logs", "habits", "habit_logs", "goals", "milestones", "schedule_blocks", "schedule_templates"]
    counts = {}
    for table in tables:
        cursor = await db.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        counts[table] = (await cursor.fetchone())["cnt"]
    cursor = await db.execute("SELECT value FROM schema_meta WHERE key = 'version'")
    row = await cursor.fetchone()
    version = int(row["value"]) if row else 0
    return {"schema_version": version, "table_counts": counts}


# ── Search ────────────────────────────────────────────────


async def global_search(keyword: str) -> list[dict]:
    results = []
    routines = await search_routines(keyword)
    for r in routines:
        results.append({"type": "routine", "id": r["id"], "name": r["name"], "category": r.get("category"), "is_active": r["is_active"]})
    habits = await search_habits(keyword)
    for h in habits:
        results.append({"type": "habit", "id": h["id"], "name": h["name"], "category": None, "is_active": h["is_active"]})
    db = await get_db()
    escaped = _escape_like(keyword)
    cursor = await db.execute(
        "SELECT * FROM goals WHERE (title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\') ORDER BY status, title",
        (f"%{escaped}%", f"%{escaped}%"),
    )
    for g in await cursor.fetchall():
        g = dict(g)
        results.append({"type": "goal", "id": g["id"], "name": g["title"], "category": g.get("category"), "is_active": 1 if g["status"] == "ACTIVE" else 0})
    return results
