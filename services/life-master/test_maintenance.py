"""Integration tests for Life-Master maintenance rounds R1-R100."""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

os.environ["DB_PATH"] = ":memory:"


async def run_tests():
    from app.database.connection import set_db_path, close_db
    from app.database.schema import init_db

    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    set_db_path(db_path)
    await init_db()

    from app.database import repositories as repo
    from app.services.streak import calculate_streak
    from app.services.optimizer import generate_schedule
    from app.utils.time_helpers import today_str, today_day_name, week_range, month_range, days_ago, days_from_now, DAY_NAMES

    passed = 0
    failed = 0

    def ok(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
        else:
            failed += 1
            print(f"  FAIL: {name}")

    # ── Time helpers ──
    ok("today_str format", len(today_str()) == 10)
    ok("today_day_name valid", today_day_name() in DAY_NAMES)
    ok("week_range returns tuple", len(week_range()) == 2)
    ok("month_range returns tuple", len(month_range()) == 2)
    ok("days_ago", len(days_ago(7)) == 10)
    ok("days_from_now", len(days_from_now(7)) == 10)

    # ── Routines CRUD ──
    r1 = await repo.create_routine({"name": "Morning Run", "category": "HEALTH", "time_slot": "MORNING", "duration_min": 30, "priority": 5})
    ok("create routine", r1 is not None and r1["name"] == "Morning Run")
    ok("routine repeat_days is list", isinstance(r1["repeat_days"], list))

    r2 = await repo.create_routine({"name": "Reading", "category": "STUDY", "time_slot": "EVENING", "duration_min": 45})
    ok("create second routine", r2 is not None)

    routines = await repo.get_routines()
    ok("list routines", len(routines) >= 2)

    r_get = await repo.get_routine(r1["id"])
    ok("get routine by id", r_get is not None and r_get["id"] == r1["id"])

    r_updated = await repo.update_routine(r1["id"], {"description": "Daily run"})
    ok("update routine", r_updated["description"] == "Daily run")

    # ── Routine delete/restore ──
    del_ok = await repo.delete_routine(r2["id"])
    ok("soft delete routine", del_ok)

    inactive = await repo.get_routines(active_only=False)
    ok("inactive visible", any(r["id"] == r2["id"] for r in inactive))

    restored = await repo.restore_routine(r2["id"])
    ok("restore routine", restored is not None and restored["is_active"] == 1)

    # ── Routine logs ──
    today = today_str()
    log = await repo.check_routine(r1["id"], today, "DONE", "Great run")
    ok("check routine", log is not None and log["status"] == "DONE")

    # UPSERT — same date should update
    log2 = await repo.check_routine(r1["id"], today, "SKIPPED")
    ok("upsert log", log2["status"] == "SKIPPED")

    uncheck = await repo.uncheck_routine(r1["id"], today)
    ok("uncheck routine", uncheck)

    # Re-check for today routines
    await repo.check_routine(r1["id"], today, "DONE")

    # ── Routine logs with routine_id filter ──
    logs = await repo.get_routine_logs(routine_id=r1["id"])
    ok("get routine logs", len(logs) >= 1)

    # R1: falsy check fix — routine_id=0 should still add filter
    logs_zero = await repo.get_routine_logs(routine_id=0)
    ok("routine_id=0 returns empty (not all)", len(logs_zero) == 0)

    # ── Routine stats ──
    stats = await repo.get_routine_stats(r1["id"], days_ago(30), today)
    ok("routine stats", stats["total_logs"] >= 1)
    ok("stats has daily_breakdown", "daily_breakdown" in stats)

    # ── Routine heatmap ──
    heatmap = await repo.get_routine_heatmap(r1["id"], days_ago(30), today)
    ok("routine heatmap", isinstance(heatmap, list))

    # ── Search ──
    search_r = await repo.search_routines("Morning")
    ok("search routines", len(search_r) >= 1)

    # R34: LIKE wildcard escaping
    search_wild = await repo.search_routines("100%")
    ok("search with % returns empty", len(search_wild) == 0)

    # ── Duplicate ──
    dup = await repo.duplicate_routine(r1["id"])
    ok("duplicate routine", dup is not None and "(copy)" in dup["name"])
    ok("duplicate has sort_order", "sort_order" in dup)

    # ── Bulk operations ──
    # R6: empty list should not crash
    count = await repo.bulk_set_active([], 0)
    ok("bulk_set_active empty list", count == 0)

    count = await repo.bulk_set_active([r1["id"]], 0)
    ok("bulk_set_active", count == 1)
    await repo.bulk_set_active([r1["id"]], 1)  # Restore

    # ── Bulk check ──
    items = [{"routine_id": r1["id"], "status": "DONE", "note": "bulk"}]
    bulk_results = await repo.bulk_check_routines(items, today)
    ok("bulk check routines", len(bulk_results) >= 1)

    # R61: bulk check with nonexistent routine_id
    items_bad = [{"routine_id": 99999, "status": "DONE"}]
    bad_results = await repo.bulk_check_routines(items_bad, today)
    ok("bulk check skips missing routines", len(bad_results) == 0)

    # ── Habits CRUD ──
    h1 = await repo.create_habit({"name": "Water intake", "target_type": "DAILY", "target_value": 8, "unit": "cups"})
    ok("create habit", h1 is not None)

    h_get = await repo.get_habit(h1["id"])
    ok("get habit", h_get is not None)

    h_upd = await repo.update_habit(h1["id"], {"target_value": 10})
    ok("update habit", h_upd["target_value"] == 10)

    # ── Habit logs ──
    hl = await repo.log_habit(h1["id"], today, 5)
    ok("log habit", hl is not None and hl["value"] == 5)

    # UPSERT
    hl2 = await repo.log_habit(h1["id"], today, 8)
    ok("upsert habit log", hl2["value"] == 8)

    # Increment
    hl3 = await repo.increment_habit(h1["id"], today, 2)
    ok("increment habit", hl3["value"] == 10)

    # Negative increment clamped to 0
    hl4 = await repo.increment_habit(h1["id"], today, -20)
    ok("increment clamp to 0", hl4["value"] == 0)

    # All logs for date
    all_logs = await repo.get_all_habit_logs_for_date(today)
    ok("all habit logs for date", len(all_logs) >= 1)

    # R56: delete habit log with ownership check
    await repo.log_habit(h1["id"], today, 5)
    h_logs = await repo.get_habit_logs(h1["id"])
    if h_logs:
        del_ok = await repo.delete_habit_log(h_logs[0]["id"], habit_id=h1["id"])
        ok("delete habit log with ownership", del_ok)
        del_wrong = await repo.delete_habit_log(99999, habit_id=h1["id"])
        ok("delete wrong log returns false", not del_wrong)

    # ── Habit delete/restore ──
    del_h = await repo.delete_habit(h1["id"])
    ok("soft delete habit", del_h)
    rest_h = await repo.restore_habit(h1["id"])
    ok("restore habit", rest_h is not None)

    # ── Streak calculation ──
    # Re-log for streak test
    from datetime import date as d, timedelta
    for i in range(5):
        await repo.log_habit(h1["id"], (d.today() - timedelta(days=i)).isoformat(), 10)
    logs = await repo.get_habit_logs(h1["id"])
    streak = calculate_streak(logs, 10)
    ok("current streak >= 5", streak["current_streak"] >= 5)
    ok("longest streak >= 5", streak["longest_streak"] >= 5)
    ok("weekly rate > 0", streak["weekly_rate"] > 0)

    # Empty logs
    empty_streak = calculate_streak([], 1)
    ok("empty streak", empty_streak["current_streak"] == 0)

    # Logs below target
    below_streak = calculate_streak([{"date": today, "value": 0.5}], 1)
    ok("below target streak", below_streak["current_streak"] == 0)

    # ── Goals CRUD ──
    g1 = await repo.create_goal({"title": "Learn Python", "category": "SKILL", "deadline": days_from_now(30)})
    ok("create goal", g1 is not None)

    g_get = await repo.get_goal(g1["id"])
    ok("get goal", g_get is not None)

    g_upd = await repo.update_goal(g1["id"], {"description": "Master Python"})
    ok("update goal", g_upd["description"] == "Master Python")

    # Progress
    g_prog = await repo.update_goal_progress(g1["id"], 0.5)
    ok("update progress", g_prog["progress"] == 0.5)

    # Progress auto-achieve
    g_achieve = await repo.update_goal_progress(g1["id"], 1.0)
    ok("auto achieve at 1.0", g_achieve["status"] == "ACHIEVED")

    # R64: reactivate
    g_react = await repo.reactivate_goal(g1["id"])
    ok("reactivate goal", g_react is not None and g_react["status"] == "ACTIVE")

    # R65: pause
    g_pause = await repo.pause_goal(g1["id"])
    ok("pause goal", g_pause is not None and g_pause["status"] == "PAUSED")

    # R65: can't pause already paused
    g_pause2 = await repo.pause_goal(g1["id"])
    ok("can't pause paused", g_pause2 is None)

    # R63: abandon from paused
    g_abandon = await repo.abandon_goal(g1["id"])
    ok("abandon goal", g_abandon is not None and g_abandon["status"] == "ABANDONED")

    # R63: can't abandon already abandoned
    g_abandon2 = await repo.abandon_goal(g1["id"])
    ok("can't re-abandon", g_abandon2 is None)

    # R64: reactivate from abandoned
    g_react2 = await repo.reactivate_goal(g1["id"])
    ok("reactivate from abandoned", g_react2 is not None)

    # ── Goals with milestone counts ──
    goals_list = await repo.get_goals_with_milestone_counts()
    ok("goals with milestones", len(goals_list) >= 1)

    # ── Milestones CRUD ──
    m1 = await repo.create_milestone(g1["id"], {"title": "Read docs"})
    ok("create milestone", m1 is not None)

    m2 = await repo.create_milestone(g1["id"], {"title": "Build project"})
    ok("create second milestone", m2 is not None)

    # R51: complete milestone
    mc = await repo.complete_milestone(m1["id"], g1["id"])
    ok("complete milestone", mc is not None and mc["is_completed"] == 1)

    # Check goal progress synced
    g_after = await repo.get_goal(g1["id"])
    ok("progress synced after milestone", g_after["progress"] == 0.5)

    # R51: uncomplete
    mu = await repo.uncomplete_milestone(m1["id"], g1["id"])
    ok("uncomplete milestone", mu is not None and mu["is_completed"] == 0)

    # R51: complete nonexistent milestone
    mc_bad = await repo.complete_milestone(99999, g1["id"])
    ok("complete nonexistent returns None", mc_bad is None)

    # R52: update milestone with is_completed
    m_upd = await repo.update_milestone(m1["id"], {"is_completed": 1})
    ok("update milestone complete", m_upd is not None and m_upd["is_completed"] == 1)

    # Bulk milestones
    bulk_ms = await repo.create_milestones_bulk(g1["id"], [{"title": "M3"}, {"title": "M4"}])
    ok("bulk create milestones", len(bulk_ms) == 2)

    # Delete milestone
    del_m = await repo.delete_milestone(m1["id"], g1["id"])
    ok("delete milestone", del_m)

    # ── Schedule blocks ──
    sb = await repo.create_schedule_block({
        "date": today, "start_time": "09:00", "end_time": "10:00",
        "title": "Meeting", "source": "MANUAL", "priority": 4
    })
    ok("create schedule block", sb is not None)
    ok("block has duration_min", sb["duration_min"] == 60)

    # R7: negative duration clamped
    sb_neg = await repo.create_schedule_block({
        "date": today, "start_time": "23:00", "end_time": "23:30",
        "title": "Late block", "source": "MANUAL"
    })
    ok("late block duration", sb_neg["duration_min"] == 30)

    # Copy block
    sb_copy = await repo.copy_schedule_block(sb["id"], days_from_now(1))
    ok("copy block", sb_copy is not None and sb_copy["date"] == days_from_now(1))
    ok("copy preserves routine_id", "routine_id" in sb_copy)

    # Update block
    sb_upd = await repo.update_schedule_block(sb["id"], {"title": "Updated Meeting"})
    ok("update block", sb_upd["title"] == "Updated Meeting")

    # Week schedule
    week_blocks = await repo.get_schedule_blocks(today, days_from_now(6))
    ok("week schedule", isinstance(week_blocks, list))

    # Month schedule
    from datetime import date as dd
    t = dd.today()
    month_blocks = await repo.get_month_schedule(t.year, t.month)
    ok("month schedule", isinstance(month_blocks, list))

    # Conflict detection
    conflicts = await repo.detect_conflicts(today, "09:00", "10:00")
    ok("detect conflicts", len(conflicts) >= 1)

    # R4: exclude_id=0 fix
    conflicts_exc = await repo.detect_conflicts(today, "09:00", "10:00", exclude_id=0)
    ok("exclude_id=0 still works", isinstance(conflicts_exc, list))

    # Delete block
    del_sb = await repo.delete_schedule_block(sb["id"])
    ok("delete block", del_sb)

    # ── Generated blocks / optimizer ──
    await repo.update_routine(r1["id"], {"time_slot": "MORNING"})
    blocks = generate_schedule(
        [{"id": r1["id"], "name": "Morning Run", "time_slot": "MORNING", "duration_min": 30, "priority": 5}],
        [],
        day_start=6, day_end=23, slot_interval=30, break_min=10,
    )
    ok("generate schedule", len(blocks) >= 1)
    ok("generated block has source", blocks[0]["source"] == "GENERATED")

    # slot_interval=0 fix
    blocks_zero = generate_schedule([], [], slot_interval=0)
    ok("slot_interval=0 no crash", isinstance(blocks_zero, list))

    # ── Templates ──
    tmpl = await repo.create_template({
        "name": "Weekday", "day_of_week": "mon",
        "blocks": [{"start_time": "09:00", "end_time": "10:00", "title": "Work"}]
    })
    ok("create template", tmpl is not None)

    tmpls = await repo.get_templates()
    ok("list templates", len(tmpls) >= 1)

    applied = await repo.apply_template(tmpl["id"], today)
    ok("apply template", len(applied) >= 1)
    ok("applied block source", applied[0]["source"] == "TEMPLATE")

    del_t = await repo.delete_template(tmpl["id"])
    ok("delete template", del_t)

    # ── Dashboard ──
    dashboard = await repo.get_dashboard_data(today, today_day_name())
    ok("dashboard data", "routines_total" in dashboard)
    ok("dashboard has overdue_goals key", "overdue_goals" in dashboard)
    ok("dashboard has upcoming_deadlines", "upcoming_deadlines" in dashboard)

    # ── Reports ──
    start, end = week_range()
    weekly = await repo.get_weekly_report(start, end)
    ok("weekly report", "routine_summary" in weekly)

    monthly = await repo.get_monthly_report(t.year, t.month)
    ok("monthly report", "routine_summary" in monthly)

    # ── Global search ──
    search = await repo.global_search("Morning")
    ok("global search", len(search) >= 1)

    # ── Export ──
    export = await repo.export_all()
    ok("export has routines", "routines" in export)
    ok("export has milestones", "milestones" in export)
    ok("export has schema_version", "schema_version" in export)

    # ── DB Info ──
    info = await repo.get_db_info()
    ok("db info", info["schema_version"] == 3)
    ok("table counts", len(info["table_counts"]) == 8)

    # ── Cleanup ──
    cleanup = await repo.cleanup_old_logs(0)
    ok("cleanup runs", isinstance(cleanup, dict))

    # ── Schema validation ──
    from pydantic import ValidationError
    from app.models.schemas import (
        RoutineCreate, RoutineUpdate, HabitCreate, GoalCreate,
        ScheduleBlockCreate, ScheduleBlockUpdate, ScheduleTemplateCreate,
        BulkActiveRequest, BulkCheckRequest, BulkCheckItem,
        RoutineCheckRequest, HabitLogRequest, MilestoneCreate, MilestoneUpdate,
        HabitIncrementRequest, ScheduleGenerateRequest, ScheduleCopyRequest,
    )

    # Valid creation
    rc = RoutineCreate(name="Test")
    ok("routine create valid", rc.name == "Test")

    # Invalid date
    try:
        RoutineCheckRequest(date="not-a-date")
        ok("invalid date rejected", False)
    except ValidationError:
        ok("invalid date rejected", True)

    try:
        HabitLogRequest(date="2026-13-45")
        ok("invalid habit date rejected", False)
    except ValidationError:
        ok("invalid habit date rejected", True)

    try:
        GoalCreate(title="Test", deadline="bad")
        ok("invalid deadline rejected", False)
    except ValidationError:
        ok("invalid deadline rejected", True)

    try:
        ScheduleBlockCreate(date="bad", start_time="09:00", end_time="10:00", title="T")
        ok("invalid block date rejected", False)
    except ValidationError:
        ok("invalid block date rejected", True)

    # Time range validation
    try:
        ScheduleBlockCreate(date="2026-01-01", start_time="10:00", end_time="09:00", title="T")
        ok("end before start rejected", False)
    except ValidationError:
        ok("end before start rejected", True)

    # ScheduleBlockUpdate time validation
    try:
        ScheduleBlockUpdate(start_time="10:00", end_time="09:00")
        ok("update end before start rejected", False)
    except ValidationError:
        ok("update end before start rejected", True)

    # is_active bounds
    try:
        RoutineUpdate(is_active=5)
        ok("is_active > 1 rejected", False)
    except ValidationError:
        ok("is_active > 1 rejected", True)

    # Template day validation
    try:
        ScheduleTemplateCreate(name="Test", day_of_week="invalid", blocks=[{"x": 1}])
        ok("invalid day rejected", False)
    except ValidationError:
        ok("invalid day rejected", True)

    # BulkActiveRequest min_length
    try:
        BulkActiveRequest(routine_ids=[], is_active=1)
        ok("empty bulk rejected", False)
    except ValidationError:
        ok("empty bulk rejected", True)

    # min_length on names
    try:
        RoutineCreate(name="")
        ok("empty name rejected", False)
    except ValidationError:
        ok("empty name rejected", True)

    try:
        HabitCreate(name="")
        ok("empty habit name rejected", False)
    except ValidationError:
        ok("empty habit name rejected", True)

    try:
        GoalCreate(title="")
        ok("empty goal title rejected", False)
    except ValidationError:
        ok("empty goal title rejected", True)

    # MilestoneUpdate is_completed bounds
    try:
        MilestoneUpdate(is_completed=5)
        ok("milestone is_completed > 1 rejected", False)
    except ValidationError:
        ok("milestone is_completed > 1 rejected", True)

    # Increment date validation
    try:
        HabitIncrementRequest(date="bad")
        ok("invalid increment date rejected", False)
    except ValidationError:
        ok("invalid increment date rejected", True)

    # Schedule generate date validation
    try:
        ScheduleGenerateRequest(date="bad")
        ok("invalid generate date rejected", False)
    except ValidationError:
        ok("invalid generate date rejected", True)

    # Copy date validation
    try:
        ScheduleCopyRequest(block_id=1, target_date="bad")
        ok("invalid copy date rejected", False)
    except ValidationError:
        ok("invalid copy date rejected", True)

    # Milestone target_date validation
    try:
        MilestoneCreate(title="Test", target_date="bad")
        ok("invalid milestone date rejected", False)
    except ValidationError:
        ok("invalid milestone date rejected", True)

    # ── R101-R130 tests ──

    # R106: progress revert on milestone uncomplete
    g_rev = await repo.create_goal({"title": "Revert test", "category": "SKILL"})
    m_rev1 = await repo.create_milestone(g_rev["id"], {"title": "Step 1"})
    m_rev2 = await repo.create_milestone(g_rev["id"], {"title": "Step 2"})
    await repo.complete_milestone(m_rev1["id"], g_rev["id"])
    await repo.complete_milestone(m_rev2["id"], g_rev["id"])
    g_check = await repo.get_goal(g_rev["id"])
    ok("R106: auto-achieved at 100%", g_check["status"] == "ACHIEVED")
    await repo.uncomplete_milestone(m_rev1["id"], g_rev["id"])
    g_check2 = await repo.get_goal(g_rev["id"])
    ok("R106: status reverted to ACTIVE", g_check2["status"] == "ACTIVE")
    ok("R106: progress is 0.5", g_check2["progress"] == 0.5)

    # R105: GoalUpdate no longer has status field
    from app.models.schemas import GoalUpdate
    gu = GoalUpdate(title="Updated")
    ok("R105: GoalUpdate has no status", not hasattr(gu, 'status') or 'status' not in gu.model_fields)

    # R119: period report alias works
    pr = await repo.get_weekly_report(days_ago(7), today)
    ok("R119: weekly_report alias works", "routine_summary" in pr)

    # R111: Update name min_length
    try:
        RoutineUpdate(name="")
        ok("R111: empty update name rejected", False)
    except ValidationError:
        ok("R111: empty update name rejected", True)

    # R113: validate_date_str
    from app.utils.time_helpers import validate_date_str
    ok("R113: valid date passes", validate_date_str("2026-01-01") == "2026-01-01")
    ok("R113: None passes", validate_date_str(None) is None)
    try:
        validate_date_str("bad")
        ok("R113: invalid date raises", False)
    except ValueError:
        ok("R113: invalid date raises", True)

    await close_db()

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
