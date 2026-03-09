"""Data access layer — pure async SQL functions."""

import json
from datetime import date, datetime, timezone

from app.database.connection import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_routine(row: dict) -> dict:
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
    q += " ORDER BY priority DESC, name"
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
        """INSERT INTO routines (name, category, time_slot, duration_min, priority, repeat_days)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data.get("category", "GENERAL"),
            data.get("time_slot", "FLEXIBLE"),
            data.get("duration_min", 30),
            data.get("priority", 3),
            json.dumps(data.get("repeat_days", ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])),
        ),
    )
    await db.commit()
    return await get_routine(cursor.lastrowid)


async def update_routine(routine_id: int, data: dict) -> dict | None:
    db = await get_db()
    fields = []
    params = []
    for key in ("name", "category", "time_slot", "duration_min", "priority", "is_active", "sort_order"):
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


# ── Routine Logs ──────────────────────────────────────────


async def get_routine_logs(
    routine_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    db = await get_db()
    q = "SELECT * FROM routine_logs WHERE 1=1"
    params: list = []
    if routine_id:
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
        (routine_id, log_date, status, now if status == "DONE" else None, note),
    )
    await db.commit()
    cursor = await db.execute(
        "SELECT * FROM routine_logs WHERE routine_id = ? AND date = ?",
        (routine_id, log_date),
    )
    row = await cursor.fetchone()
    return dict(row)


async def get_today_routines(today: str, day_name: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT r.*, rl.status as log_status, rl.note as log_note
           FROM routines r
           LEFT JOIN routine_logs rl ON r.id = rl.routine_id AND rl.date = ?
           WHERE r.is_active = 1 AND r.repeat_days LIKE ?
           ORDER BY
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
    if routine_id:
        q_base += " AND routine_id = ?"
        params.append(routine_id)

    cursor = await db.execute(q_base, params)
    total = (await cursor.fetchone())["cnt"]

    cursor2 = await db.execute(
        q_base.replace("COUNT(*) as cnt", "status, COUNT(*) as cnt") + " GROUP BY status",
        params,
    )
    status_counts = {row["status"]: row["cnt"] for row in await cursor2.fetchall()}

    return {
        "total_logs": total,
        "done": status_counts.get("DONE", 0),
        "skipped": status_counts.get("SKIPPED", 0),
        "partial": status_counts.get("PARTIAL", 0),
        "completion_rate": round(status_counts.get("DONE", 0) / total, 3) if total > 0 else 0,
        "date_from": date_from,
        "date_to": date_to,
    }


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
        """INSERT INTO habits (name, target_type, target_value, unit, color)
           VALUES (?, ?, ?, ?, ?)""",
        (
            data["name"],
            data.get("target_type", "DAILY"),
            data.get("target_value", 1),
            data.get("unit", "회"),
            data.get("color", "#6366f1"),
        ),
    )
    await db.commit()
    return await get_habit(cursor.lastrowid)


async def update_habit(habit_id: int, data: dict) -> dict | None:
    db = await get_db()
    fields = []
    params = []
    for key in ("name", "target_type", "target_value", "unit", "color", "is_active"):
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
    q += " ORDER BY CASE status WHEN 'ACTIVE' THEN 0 WHEN 'ACHIEVED' THEN 1 ELSE 2 END, deadline NULLS LAST, created_at DESC"
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_goal(goal_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_goal(data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO goals (title, description, category, deadline, status, progress)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            data["title"],
            data.get("description"),
            data.get("category", "GENERAL"),
            data.get("deadline"),
            data.get("status", "ACTIVE"),
            data.get("progress", 0.0),
        ),
    )
    await db.commit()
    return await get_goal(cursor.lastrowid)


async def update_goal(goal_id: int, data: dict) -> dict | None:
    db = await get_db()
    fields = []
    params = []
    for key in ("title", "description", "category", "deadline", "status", "progress"):
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
        (min(progress, 1.0), _now(), goal_id),
    )
    await db.commit()
    return await get_goal(goal_id)


# ── Milestones ────────────────────────────────────────────


async def get_milestones(goal_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM milestones WHERE goal_id = ? ORDER BY sort_order, target_date NULLS LAST",
        (goal_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def create_milestone(goal_id: int, data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO milestones (goal_id, title, target_date, sort_order)
           VALUES (?, ?, ?, ?)""",
        (goal_id, data["title"], data.get("target_date"), data.get("sort_order", 0)),
    )
    await db.commit()
    cursor2 = await db.execute("SELECT * FROM milestones WHERE id = ?", (cursor.lastrowid,))
    row = await cursor2.fetchone()
    return dict(row)


async def complete_milestone(milestone_id: int, goal_id: int) -> dict | None:
    db = await get_db()
    await db.execute(
        "UPDATE milestones SET is_completed = 1, completed_at = ? WHERE id = ? AND goal_id = ?",
        (_now(), milestone_id, goal_id),
    )
    await db.commit()
    # Auto-update goal progress based on milestone completion
    cursor = await db.execute(
        "SELECT COUNT(*) as total, SUM(is_completed) as done FROM milestones WHERE goal_id = ?",
        (goal_id,),
    )
    row = await cursor.fetchone()
    if row and row["total"] > 0:
        new_progress = row["done"] / row["total"]
        await update_goal_progress(goal_id, new_progress)
    cursor2 = await db.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,))
    ms = await cursor2.fetchone()
    return dict(ms) if ms else None


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
    return [dict(r) for r in rows]


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
    return dict(row)


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
        return dict(row) if row else None
    params.append(block_id)
    await db.execute(f"UPDATE schedule_blocks SET {', '.join(fields)} WHERE id = ?", params)
    await db.commit()
    cursor = await db.execute("SELECT * FROM schedule_blocks WHERE id = ?", (block_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


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


# ── Duplicate / Clone ─────────────────────────────────────


async def duplicate_routine(routine_id: int) -> dict | None:
    original = await get_routine(routine_id)
    if not original:
        return None
    data = {
        "name": f"{original['name']} (복사)",
        "category": original["category"],
        "time_slot": original["time_slot"],
        "duration_min": original["duration_min"],
        "priority": original["priority"],
        "repeat_days": json.loads(original["repeat_days"]) if isinstance(original["repeat_days"], str) else original["repeat_days"],
    }
    return await create_routine(data)


# ── Habit Increment ───────────────────────────────────────


async def increment_habit(habit_id: int, log_date: str, delta: float) -> dict:
    db = await get_db()
    # Get current value
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
        result = await check_routine(item["routine_id"], log_date, item["status"], item.get("note"))
        results.append(result)
    return results


# ── Goal Soft Delete ──────────────────────────────────────


async def abandon_goal(goal_id: int) -> dict | None:
    db = await get_db()
    await db.execute(
        "UPDATE goals SET status = 'ABANDONED', updated_at = ? WHERE id = ?",
        (_now(), goal_id),
    )
    await db.commit()
    return await get_goal(goal_id)


async def reactivate_goal(goal_id: int) -> dict | None:
    db = await get_db()
    await db.execute(
        "UPDATE goals SET status = 'ACTIVE', updated_at = ? WHERE id = ?",
        (_now(), goal_id),
    )
    await db.commit()
    return await get_goal(goal_id)


# ── Schedule Conflict Detection ───────────────────────────


async def detect_conflicts(date_val: str, start_time: str, end_time: str, exclude_id: int | None = None) -> list[dict]:
    db = await get_db()
    q = """SELECT * FROM schedule_blocks
           WHERE date = ? AND start_time < ? AND end_time > ?"""
    params: list = [date_val, end_time, start_time]
    if exclude_id:
        q += " AND id != ?"
        params.append(exclude_id)
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── Data Retention ────────────────────────────────────────


async def cleanup_old_logs(retention_days: int) -> dict:
    db = await get_db()
    cutoff = (date.today() - __import__("datetime").timedelta(days=retention_days)).isoformat()

    c1 = await db.execute("DELETE FROM routine_logs WHERE date < ?", (cutoff,))
    c2 = await db.execute("DELETE FROM habit_logs WHERE date < ?", (cutoff,))
    c3 = await db.execute("DELETE FROM schedule_blocks WHERE date < ?", (cutoff,))
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

    # Routines today
    today_rts = await get_today_routines(today, day_name)
    done_count = sum(1 for r in today_rts if r.get("log_status") == "DONE")

    # Habits
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM habits WHERE is_active = 1")
    habits_total = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        "SELECT COUNT(DISTINCT habit_id) as cnt FROM habit_logs WHERE date = ?", (today,)
    )
    habits_logged = (await cursor.fetchone())["cnt"]

    # Goals
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM goals WHERE status = 'ACTIVE'")
    active_goals = (await cursor.fetchone())["cnt"]

    # Schedule blocks
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM schedule_blocks WHERE date = ?", (today,))
    block_count = (await cursor.fetchone())["cnt"]

    return {
        "date": today,
        "routines_total": len(today_rts),
        "routines_done": done_count,
        "routines_completion": round(done_count / len(today_rts), 3) if today_rts else 0,
        "habits_logged_today": habits_logged,
        "habits_total": habits_total,
        "active_goals": active_goals,
        "schedule_blocks": block_count,
    }


# ── Weekly Report ─────────────────────────────────────────


async def get_weekly_report(date_from: str, date_to: str) -> dict:
    db = await get_db()

    # Routine stats
    cursor = await db.execute(
        "SELECT status, COUNT(*) as cnt FROM routine_logs WHERE date >= ? AND date <= ? GROUP BY status",
        (date_from, date_to),
    )
    routine_stats = {row["status"]: row["cnt"] for row in await cursor.fetchall()}

    # Habit stats
    cursor = await db.execute(
        """SELECT h.name, COUNT(hl.id) as log_count, SUM(hl.value) as total_value
           FROM habits h
           LEFT JOIN habit_logs hl ON h.id = hl.habit_id AND hl.date >= ? AND hl.date <= ?
           WHERE h.is_active = 1
           GROUP BY h.id""",
        (date_from, date_to),
    )
    habit_stats = [dict(r) for r in await cursor.fetchall()]

    # Goal changes
    cursor = await db.execute(
        "SELECT id, title, status, progress FROM goals WHERE updated_at >= ? AND updated_at <= ?",
        (date_from, date_to + "T23:59:59"),
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
