"""Database schema definitions and initialization."""

import logging

from app.database.connection import get_db

logger = logging.getLogger("life-master.schema")

SCHEMA_VERSION = 3

TABLES = [
    """CREATE TABLE IF NOT EXISTS routines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL DEFAULT 'GENERAL',
        time_slot TEXT NOT NULL DEFAULT 'FLEXIBLE',
        duration_min INTEGER NOT NULL DEFAULT 30,
        priority INTEGER NOT NULL DEFAULT 3,
        repeat_days TEXT NOT NULL DEFAULT '["mon","tue","wed","thu","fri","sat","sun"]',
        is_active INTEGER NOT NULL DEFAULT 1,
        sort_order INTEGER NOT NULL DEFAULT 0,
        color TEXT NOT NULL DEFAULT '#6366f1',
        icon TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS routine_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        routine_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'DONE',
        started_at TEXT,
        completed_at TEXT,
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (routine_id) REFERENCES routines(id),
        UNIQUE(routine_id, date)
    )""",
    """CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        target_type TEXT NOT NULL DEFAULT 'DAILY',
        target_value REAL NOT NULL DEFAULT 1,
        unit TEXT NOT NULL DEFAULT '회',
        color TEXT NOT NULL DEFAULT '#6366f1',
        icon TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS habit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        value REAL NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (habit_id) REFERENCES habits(id),
        UNIQUE(habit_id, date)
    )""",
    """CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL DEFAULT 'GENERAL',
        deadline TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        progress REAL NOT NULL DEFAULT 0.0,
        priority INTEGER NOT NULL DEFAULT 3,
        color TEXT NOT NULL DEFAULT '#6366f1',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS milestones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        is_completed INTEGER NOT NULL DEFAULT 0,
        target_date TEXT,
        completed_at TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS schedule_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        title TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'MANUAL',
        routine_id INTEGER,
        priority INTEGER NOT NULL DEFAULT 3,
        is_locked INTEGER NOT NULL DEFAULT 0,
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (routine_id) REFERENCES routines(id)
    )""",
    """CREATE TABLE IF NOT EXISTS schedule_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        blocks_json TEXT NOT NULL DEFAULT '[]',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    # Indexes
    "CREATE INDEX IF NOT EXISTS idx_routine_logs_date ON routine_logs(date)",
    "CREATE INDEX IF NOT EXISTS idx_routine_logs_routine ON routine_logs(routine_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_habit_logs_date ON habit_logs(date)",
    "CREATE INDEX IF NOT EXISTS idx_habit_logs_habit ON habit_logs(habit_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_blocks_date ON schedule_blocks(date)",
    "CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)",
    "CREATE INDEX IF NOT EXISTS idx_milestones_goal ON milestones(goal_id)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_templates_day ON schedule_templates(day_of_week)",
]

_MIGRATIONS = [
    ("sort_order", "routines", "INTEGER NOT NULL DEFAULT 0"),
    ("note", "schedule_blocks", "TEXT"),
    ("description", "routines", "TEXT"),
    ("description", "habits", "TEXT"),
    ("icon", "routines", "TEXT"),
    ("icon", "habits", "TEXT"),
    ("color", "routines", "TEXT NOT NULL DEFAULT '#6366f1'"),
    ("priority", "goals", "INTEGER NOT NULL DEFAULT 3"),
    ("color", "goals", "TEXT NOT NULL DEFAULT '#6366f1'"),
]


async def init_db() -> None:
    db = await get_db()
    for statement in TABLES:
        await db.execute(statement)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)"
    )

    for col, table, typedef in _MIGRATIONS:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass  # Column already exists — expected
            else:
                logger.warning("Migration failed for %s.%s: %s", table, col, e)

    await db.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
        (str(SCHEMA_VERSION),),
    )
    await db.commit()
