"""Database schema definitions and initialization."""

import logging

from app.database.connection import get_db

logger = logging.getLogger("life-master.schema")

SCHEMA_VERSION = 5

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
    """CREATE TABLE IF NOT EXISTS notification_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        trigger_type TEXT NOT NULL DEFAULT 'ROUTINE_REMINDER',
        target_id INTEGER,
        cron_time TEXT,
        days TEXT NOT NULL DEFAULT '["mon","tue","wed","thu","fri","sat","sun"]',
        priority TEXT NOT NULL DEFAULT '0',
        is_active INTEGER NOT NULL DEFAULT 1,
        last_sent_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS notification_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id INTEGER,
        trigger_type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        provider TEXT NOT NULL,
        success INTEGER NOT NULL DEFAULT 0,
        detail TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (rule_id) REFERENCES notification_rules(id) ON DELETE SET NULL
    )""",
    # ── Japanese Learning ─────────────────────────────────
    """CREATE TABLE IF NOT EXISTS jp_vocabulary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL,
        reading TEXT NOT NULL,
        meaning TEXT NOT NULL,
        jlpt_level TEXT NOT NULL DEFAULT 'N5',
        part_of_speech TEXT NOT NULL DEFAULT 'noun',
        example_ja TEXT,
        example_ko TEXT,
        tags TEXT NOT NULL DEFAULT '[]',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS jp_srs_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vocab_id INTEGER NOT NULL,
        ease_factor REAL NOT NULL DEFAULT 2.5,
        interval_days INTEGER NOT NULL DEFAULT 0,
        repetitions INTEGER NOT NULL DEFAULT 0,
        next_review TEXT NOT NULL DEFAULT (date('now')),
        last_reviewed TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (vocab_id) REFERENCES jp_vocabulary(id) ON DELETE CASCADE,
        UNIQUE(vocab_id)
    )""",
    """CREATE TABLE IF NOT EXISTS jp_review_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vocab_id INTEGER NOT NULL,
        quality INTEGER NOT NULL,
        time_ms INTEGER NOT NULL DEFAULT 0,
        xp_earned INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (vocab_id) REFERENCES jp_vocabulary(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS jp_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        artist TEXT,
        source_type TEXT NOT NULL DEFAULT 'song',
        content_ja TEXT NOT NULL,
        content_ko TEXT,
        difficulty TEXT NOT NULL DEFAULT 'N4',
        tags TEXT NOT NULL DEFAULT '[]',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS jp_source_vocab (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id INTEGER NOT NULL,
        vocab_id INTEGER NOT NULL,
        line_number INTEGER NOT NULL DEFAULT 0,
        context_ja TEXT,
        FOREIGN KEY (source_id) REFERENCES jp_sources(id) ON DELETE CASCADE,
        FOREIGN KEY (vocab_id) REFERENCES jp_vocabulary(id) ON DELETE CASCADE,
        UNIQUE(source_id, vocab_id)
    )""",
    """CREATE TABLE IF NOT EXISTS jp_player_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_xp INTEGER NOT NULL DEFAULT 0,
        level INTEGER NOT NULL DEFAULT 1,
        current_streak INTEGER NOT NULL DEFAULT 0,
        longest_streak INTEGER NOT NULL DEFAULT 0,
        last_study_date TEXT,
        total_reviews INTEGER NOT NULL DEFAULT 0,
        total_correct INTEGER NOT NULL DEFAULT 0,
        combo_best INTEGER NOT NULL DEFAULT 0,
        achievements TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS jp_quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_type TEXT NOT NULL DEFAULT 'flashcard',
        total_questions INTEGER NOT NULL,
        correct INTEGER NOT NULL,
        max_combo INTEGER NOT NULL DEFAULT 0,
        xp_earned INTEGER NOT NULL DEFAULT 0,
        time_seconds INTEGER NOT NULL DEFAULT 0,
        jlpt_level TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    # Indexes
    "CREATE INDEX IF NOT EXISTS idx_notification_logs_date ON notification_logs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_notification_rules_active ON notification_rules(is_active, trigger_type)",
    "CREATE INDEX IF NOT EXISTS idx_routine_logs_date ON routine_logs(date)",
    "CREATE INDEX IF NOT EXISTS idx_routine_logs_routine ON routine_logs(routine_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_habit_logs_date ON habit_logs(date)",
    "CREATE INDEX IF NOT EXISTS idx_habit_logs_habit ON habit_logs(habit_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_blocks_date ON schedule_blocks(date)",
    "CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)",
    "CREATE INDEX IF NOT EXISTS idx_milestones_goal ON milestones(goal_id)",
    "CREATE INDEX IF NOT EXISTS idx_schedule_templates_day ON schedule_templates(day_of_week)",
    # Japanese learning indexes
    "CREATE INDEX IF NOT EXISTS idx_jp_vocab_level ON jp_vocabulary(jlpt_level)",
    "CREATE INDEX IF NOT EXISTS idx_jp_srs_next ON jp_srs_cards(next_review)",
    "CREATE INDEX IF NOT EXISTS idx_jp_review_logs_date ON jp_review_logs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_jp_source_vocab_source ON jp_source_vocab(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_jp_quiz_date ON jp_quiz_results(created_at)",
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
