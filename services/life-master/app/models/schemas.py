"""Pydantic request/response schemas."""

from datetime import date as date_type

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    BlockSource,
    GoalCategory,
    GoalStatus,
    HabitTargetType,
    LogStatus,
    RoutineCategory,
    TimeSlot,
)

VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


# ── Routines ──────────────────────────────────────────────


class RoutineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: RoutineCategory = RoutineCategory.GENERAL
    time_slot: TimeSlot = TimeSlot.FLEXIBLE
    duration_min: int = Field(default=30, ge=5, le=480)
    priority: int = Field(default=3, ge=1, le=5)
    repeat_days: list[str] = Field(
        default=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        min_length=1,
    )
    sort_order: int = 0
    color: str = Field(default="#6366f1", max_length=7)
    icon: str | None = None

    @field_validator("repeat_days")
    @classmethod
    def validate_days(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_DAYS
        if invalid:
            raise ValueError(f"Invalid day(s): {invalid}. Use: {VALID_DAYS}")
        return v


class RoutineUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    category: RoutineCategory | None = None
    time_slot: TimeSlot | None = None
    duration_min: int | None = Field(default=None, ge=5, le=480)
    priority: int | None = Field(default=None, ge=1, le=5)
    repeat_days: list[str] | None = None
    is_active: int | None = Field(default=None, ge=0, le=1)
    sort_order: int | None = None
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = None

    @field_validator("repeat_days")
    @classmethod
    def validate_days(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = set(v) - VALID_DAYS
            if invalid:
                raise ValueError(f"Invalid day(s): {invalid}. Use: {VALID_DAYS}")
        return v


class RoutineResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    category: str
    time_slot: str
    duration_min: int
    priority: int
    repeat_days: list[str] | str
    is_active: int
    sort_order: int = 0
    color: str = "#6366f1"
    icon: str | None = None
    created_at: str
    updated_at: str


class RoutineCheckRequest(BaseModel):
    status: LogStatus = LogStatus.DONE
    note: str | None = None
    date: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


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
    description: str | None = None
    category: str
    time_slot: str
    duration_min: int
    priority: int
    repeat_days: list[str] | str
    is_active: int
    sort_order: int = 0
    color: str = "#6366f1"
    icon: str | None = None
    created_at: str
    updated_at: str
    log_status: str | None = None
    log_note: str | None = None


class RoutineStatsResponse(BaseModel):
    total_logs: int
    done: int
    skipped: int
    partial: int
    completion_rate: float
    date_from: str
    date_to: str
    daily_breakdown: list[dict] = []


# ── Habits ────────────────────────────────────────────────


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    target_type: HabitTargetType = HabitTargetType.DAILY
    target_value: float = Field(default=1, gt=0)
    unit: str = Field(default="회", max_length=20)
    color: str = Field(default="#6366f1", max_length=7)
    icon: str | None = None


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    target_type: HabitTargetType | None = None
    target_value: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=20)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = None
    is_active: int | None = Field(default=None, ge=0, le=1)


class HabitResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    target_type: str
    target_value: float
    unit: str
    color: str
    icon: str | None = None
    is_active: int
    created_at: str
    updated_at: str


class HabitLogRequest(BaseModel):
    value: float = Field(default=1, ge=0)
    date: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


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
    today_value: float = 0


# ── Goals ─────────────────────────────────────────────────


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    category: GoalCategory = GoalCategory.GENERAL
    deadline: str | None = None
    progress: float = Field(default=0.0, ge=0, le=1)
    priority: int = Field(default=3, ge=1, le=5)
    color: str = Field(default="#6366f1", max_length=7)

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    category: GoalCategory | None = None
    deadline: str | None = None
    status: GoalStatus | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    color: str | None = Field(default=None, max_length=7)

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


class GoalResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    category: str
    deadline: str | None = None
    status: str
    progress: float
    priority: int = 3
    color: str = "#6366f1"
    created_at: str
    updated_at: str


class GoalProgressUpdate(BaseModel):
    progress: float = Field(ge=0, le=1)


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    target_date: str | None = None
    sort_order: int = 0

    @field_validator("target_date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    target_date: str | None = None
    sort_order: int | None = None
    is_completed: int | None = Field(default=None, ge=0, le=1)

    @field_validator("target_date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


class MilestoneResponse(BaseModel):
    id: int
    goal_id: int
    title: str
    is_completed: int
    target_date: str | None = None
    completed_at: str | None = None
    sort_order: int
    created_at: str


class GoalListItem(BaseModel):
    id: int
    title: str
    description: str | None = None
    category: str
    deadline: str | None = None
    status: str
    progress: float
    priority: int = 3
    color: str = "#6366f1"
    created_at: str
    updated_at: str
    milestone_total: int = 0
    milestone_done: int = 0


class GoalWithMilestones(BaseModel):
    id: int
    title: str
    description: str | None = None
    category: str
    deadline: str | None = None
    status: str
    progress: float
    priority: int = 3
    color: str = "#6366f1"
    created_at: str
    updated_at: str
    milestones: list[MilestoneResponse] = []
    milestone_total: int = 0
    milestone_done: int = 0
    days_remaining: int | None = None


# ── Schedule ──────────────────────────────────────────────


class ScheduleBlockCreate(BaseModel):
    date: str
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    title: str = Field(min_length=1, max_length=200)
    priority: int = Field(default=3, ge=1, le=5)
    is_locked: int = Field(default=0, ge=0, le=1)
    note: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        date_type.fromisoformat(v)
        return v

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v: str, info) -> str:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class ScheduleBlockUpdate(BaseModel):
    date: str | None = None
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    title: str | None = Field(default=None, max_length=200)
    priority: int | None = Field(default=None, ge=1, le=5)
    is_locked: int | None = Field(default=None, ge=0, le=1)
    note: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v: str | None, info) -> str | None:
        if v is not None:
            start = info.data.get("start_time")
            if start and v <= start:
                raise ValueError("end_time must be after start_time")
        return v


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
    duration_min: int = 0
    created_at: str


class ScheduleGenerateRequest(BaseModel):
    date: str | None = None
    break_min: int = Field(default=0, ge=0, le=60)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


class ScheduleCopyRequest(BaseModel):
    block_id: int
    target_date: str

    @field_validator("target_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        date_type.fromisoformat(v)
        return v


class ScheduleTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    day_of_week: str
    blocks: list[dict] = Field(min_length=1)

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: str) -> str:
        if v not in VALID_DAYS:
            raise ValueError(f"Invalid day: {v}. Use: {VALID_DAYS}")
        return v


class ScheduleTemplateResponse(BaseModel):
    id: int
    name: str
    day_of_week: str
    blocks_json: str
    is_active: int
    created_at: str


# ── Bulk Operations ──────────────────────────────────────


class BulkCheckItem(BaseModel):
    routine_id: int
    status: LogStatus = LogStatus.DONE
    note: str | None = None


class BulkCheckRequest(BaseModel):
    date: str | None = None
    items: list[BulkCheckItem] = Field(min_length=1)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


class BulkCheckResponse(BaseModel):
    date: str
    checked: int
    results: list[RoutineLogResponse]


class BulkActiveRequest(BaseModel):
    routine_ids: list[int] = Field(min_length=1)
    is_active: int = Field(ge=0, le=1)


class BulkMilestoneCreate(BaseModel):
    milestones: list[MilestoneCreate] = Field(min_length=1)


# ── Habit Increment ──────────────────────────────────────


class HabitIncrementRequest(BaseModel):
    delta: float = Field(default=1, description="Amount to add (negative to subtract)")
    date: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None:
            date_type.fromisoformat(v)
        return v


# ── Dashboard ────────────────────────────────────────────


class DashboardResponse(BaseModel):
    date: str
    routines_total: int
    routines_done: int
    routines_remaining: int = 0
    routines_completion: float
    habits_logged_today: int
    habits_total: int
    active_goals: int
    schedule_blocks: int
    top_streaks: list[dict] = []
    upcoming_deadlines: list[dict] = []
    overdue_goals: list[dict] = []


# ── Export / Import ──────────────────────────────────────


class ExportResponse(BaseModel):
    version: str = ""
    schema_version: str = ""
    exported_at: str
    routines: list[dict]
    habits: list[dict]
    goals: list[dict]
    milestones: list[dict] = []
    routine_logs: list[dict]
    habit_logs: list[dict]


# ── Search ───────────────────────────────────────────────


class SearchResult(BaseModel):
    type: str
    id: int
    name: str
    category: str | None = None
    is_active: int = 1


# ── Admin ────────────────────────────────────────────────


class DbInfoResponse(BaseModel):
    schema_version: int
    table_counts: dict[str, int]
    db_path: str
