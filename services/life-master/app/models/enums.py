"""Domain enumerations."""

from enum import StrEnum


class RoutineCategory(StrEnum):
    HEALTH = "HEALTH"
    WORK = "WORK"
    STUDY = "STUDY"
    SELF_DEV = "SELF_DEV"
    SOCIAL = "SOCIAL"
    CREATIVE = "CREATIVE"
    GENERAL = "GENERAL"


class TimeSlot(StrEnum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    EVENING = "EVENING"
    FLEXIBLE = "FLEXIBLE"


class LogStatus(StrEnum):
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    PARTIAL = "PARTIAL"


class HabitTargetType(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    COUNT = "COUNT"


class GoalCategory(StrEnum):
    CAREER = "CAREER"
    HEALTH = "HEALTH"
    FINANCE = "FINANCE"
    SKILL = "SKILL"
    RELATIONSHIP = "RELATIONSHIP"
    GENERAL = "GENERAL"


class GoalStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ACHIEVED = "ACHIEVED"
    ABANDONED = "ABANDONED"
    PAUSED = "PAUSED"


class BlockSource(StrEnum):
    MANUAL = "MANUAL"
    ROUTINE = "ROUTINE"
    GENERATED = "GENERATED"
    TEMPLATE = "TEMPLATE"
