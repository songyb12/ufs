"""Pydantic request/response schemas."""

from pydantic import BaseModel, Field

from app.models.enums import (
    BlockSource,
    GoalCategory,
    GoalStatus,
    HabitTargetType,
    LogStatus,
    RoutineCategory,
    TimeSlot,
)


# ── Routines ──────────────────────────────────────────────


class RoutineCreate(BaseModel):
    name: str = Field(max_length=200)
    category: RoutineCategory = RoutineCategory.GENERAL
    time_slot: TimeSlot = TimeSlot.FLEXIBLE
    duration_min: int = Field(default=30, ge=5, le=480)
    priority: int = Field(default=3, ge=1, le=5)
    repeat_days: list[str] = Field(
        default=["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    )


class RoutineUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    category: RoutineCategory | None = None
    time_slot: TimeSlot | None = None
    duration_min: int | None = Field(default=None, ge=5, le=480)
    priority: int | None = Field(default=None, ge=1, le=5)
    repeat_days: list[str] | None = None
    is_active: int | None = None


class RoutineResponse(BaseModel):
    id: int
    name: str
    category: str
    time_slot: str
    duration_min: int
    priority: int
    repeat_days: list[str] | str
    is_active: int
    created_at: str
    updated_at: str
    sort_order: int = 0


class RoutineCheckRequest(BaseModel):
    status: LogStatus = LogStatus.DONE
    note: str | None = None
    date: str | None = None


class RoutineLogResponse(BaseModel):
    id: int
    routine_id: int
    date: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    note: str | None = None
    created_at: str


class TodayRoutineResponse(BaseModel):
    id: int
    name: str
    category: str
    time_slot: str
    duration_min: int
    priority: int
    repeat_days: list[str] | str
    is_active: int
    created_at: str
    updated_at: str
    log_status: str | None = None
    log_note: str | None = None
    sort_order: int = 0


class RoutineStatsResponse(BaseModel):
    total_logs: int
    done: int
    skipped: int
    partial: int
    completion_rate: float
    date_from: str
    date_to: str


# ── Habits ────────────────────────────────────────────────


class HabitCreate(BaseModel):
    name: str = Field(max_length=200)
    target_type: HabitTargetType = HabitTargetType.DAILY
    target_value: float = Field(default=1, gt=0)
    unit: str = Field(default="회", max_length=20)
    color: str = Field(default="#6366f1", max_length=7)


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    target_type: HabitTargetType | None = None
    target_value: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=20)
    color: str | None = Field(default=None, max_length=7)
    is_active: int | None = None


class HabitResponse(BaseModel):
    id: int
    name: str
    target_type: str
    target_value: float
    unit: str
    color: str
    is_active: int
    created_at: str
    updated_at: str


class HabitLogRequest(BaseModel):
    value: float = Field(default=1, ge=0)
    date: str | None = None


class HabitLogResponse(BaseModel):
    id: int
    habit_id: int
    date: str
    value: float
    created_at: str


class StreakResponse(BaseModel):
    habit_id: int
    current_streak: int
    longest_streak: int
    weekly_rate: float
    monthly_rate: float
    total_logs: int


class HabitOverviewItem(BaseModel):
    habit: HabitResponse
    streak: StreakResponse
    recent_logs: list[HabitLogResponse]


# ── Goals ─────────────────────────────────────────────────


class GoalCreate(BaseModel):
    title: str = Field(max_length=300)
    description: str | None = None
    category: GoalCategory = GoalCategory.GENERAL
    deadline: str | None = None
    progress: float = Field(default=0.0, ge=0, le=1)


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    category: GoalCategory | None = None
    deadline: str | None = None
    status: GoalStatus | None = None


class GoalResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    category: str
    deadline: str | None = None
    status: str
    progress: float
    created_at: str
    updated_at: str


class GoalProgressUpdate(BaseModel):
    progress: float = Field(ge=0, le=1)


class MilestoneCreate(BaseModel):
    title: str = Field(max_length=300)
    target_date: str | None = None
    sort_order: int = 0


class MilestoneResponse(BaseModel):
    id: int
    goal_id: int
    title: str
    is_completed: int
    target_date: str | None = None
    completed_at: str | None = None
    sort_order: int
    created_at: str


# ── Schedule ──────────────────────────────────────────────


class ScheduleBlockCreate(BaseModel):
    date: str
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    title: str = Field(max_length=200)
    priority: int = Field(default=3, ge=1, le=5)
    is_locked: int = Field(default=0, ge=0, le=1)
    note: str | None = None


class ScheduleBlockUpdate(BaseModel):
    date: str | None = None
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    title: str | None = Field(default=None, max_length=200)
    priority: int | None = Field(default=None, ge=1, le=5)
    is_locked: int | None = Field(default=None, ge=0, le=1)
    note: str | None = None


class ScheduleBlockResponse(BaseModel):
    id: int
    date: str
    start_time: str
    end_time: str
    title: str
    source: str
    routine_id: int | None = None
    priority: int
    is_locked: int
    note: str | None = None
    created_at: str


class ScheduleGenerateRequest(BaseModel):
    date: str | None = None
    break_min: int = Field(default=0, ge=0, le=60)


# ── Bulk Operations ──────────────────────────────────────


class BulkCheckItem(BaseModel):
    routine_id: int
    status: LogStatus = LogStatus.DONE
    note: str | None = None


class BulkCheckRequest(BaseModel):
    date: str | None = None
    items: list[BulkCheckItem]


class BulkCheckResponse(BaseModel):
    date: str
    checked: int
    results: list[RoutineLogResponse]


# ── Habit Increment ──────────────────────────────────────


class HabitIncrementRequest(BaseModel):
    delta: float = Field(default=1, description="Amount to add (negative to subtract)")
    date: str | None = None


# ── Goal with Milestones ─────────────────────────────────


class GoalWithMilestones(BaseModel):
    id: int
    title: str
    description: str | None = None
    category: str
    deadline: str | None = None
    status: str
    progress: float
    created_at: str
    updated_at: str
    milestones: list[MilestoneResponse] = []
    milestone_total: int = 0
    milestone_done: int = 0


# ── Dashboard ────────────────────────────────────────────


class DashboardResponse(BaseModel):
    date: str
    routines_total: int
    routines_done: int
    routines_completion: float
    habits_logged_today: int
    habits_total: int
    active_goals: int
    schedule_blocks: int
    top_streaks: list[dict] = []
