"""Database schema definitions and initialization."""

import logging

from app.database.connection import get_db

logger = logging.getLogger("life-master.schema")

SCHEMA_VERSION = 10

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
    # ── Daily Quests & Weekly Challenges ──────────────────
    """CREATE TABLE IF NOT EXISTS jp_daily_quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        slot INTEGER NOT NULL DEFAULT 0,
        quest_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        target INTEGER NOT NULL,
        xp_reward INTEGER NOT NULL,
        tier TEXT NOT NULL DEFAULT 'basic',
        current_progress INTEGER NOT NULL DEFAULT 0,
        is_completed INTEGER NOT NULL DEFAULT 0,
        completed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(date, slot)
    )""",
    """CREATE TABLE IF NOT EXISTS jp_weekly_challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start TEXT NOT NULL,
        challenge_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        target INTEGER NOT NULL,
        xp_reward INTEGER NOT NULL,
        current_progress INTEGER NOT NULL DEFAULT 0,
        is_completed INTEGER NOT NULL DEFAULT 0,
        completed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(week_start)
    )""",
    # ── Grammar Learning ───────────────────────────────────
    """CREATE TABLE IF NOT EXISTS jp_grammar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grammar_point TEXT NOT NULL,
        meaning_ko TEXT NOT NULL,
        meaning_en TEXT,
        jlpt_level TEXT NOT NULL DEFAULT 'N5',
        category TEXT NOT NULL DEFAULT '문형',
        formation TEXT,
        notes TEXT,
        order_index INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS jp_grammar_example (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grammar_id INTEGER NOT NULL,
        sentence_jp TEXT NOT NULL,
        sentence_ko TEXT NOT NULL,
        sentence_en TEXT,
        audio_url TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (grammar_id) REFERENCES jp_grammar(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS jp_grammar_srs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grammar_id INTEGER NOT NULL,
        ease_factor REAL NOT NULL DEFAULT 2.5,
        interval_days INTEGER NOT NULL DEFAULT 0,
        repetitions INTEGER NOT NULL DEFAULT 0,
        next_review TEXT NOT NULL DEFAULT (date('now')),
        last_reviewed TEXT,
        quality_history TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (grammar_id) REFERENCES jp_grammar(id) ON DELETE CASCADE,
        UNIQUE(grammar_id)
    )""",
    # ── Kanji Learning ────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS jp_kanji (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character TEXT NOT NULL UNIQUE,
        meaning_ko TEXT NOT NULL,
        meaning_en TEXT,
        onyomi TEXT,
        kunyomi TEXT,
        jlpt_level TEXT NOT NULL DEFAULT 'N5',
        grade INTEGER,
        stroke_count INTEGER NOT NULL DEFAULT 1,
        radicals TEXT,
        order_index INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS jp_kanji_vocab_link (
        kanji_id INTEGER NOT NULL,
        vocab_id INTEGER NOT NULL,
        PRIMARY KEY (kanji_id, vocab_id),
        FOREIGN KEY (kanji_id) REFERENCES jp_kanji(id) ON DELETE CASCADE,
        FOREIGN KEY (vocab_id) REFERENCES jp_vocabulary(id) ON DELETE CASCADE
    )""",
    # ── Reading Practice ─────────────────────────────────
    """CREATE TABLE IF NOT EXISTS jp_reading_passage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content_jp TEXT NOT NULL,
        content_ko TEXT,
        jlpt_level TEXT NOT NULL DEFAULT 'N5',
        category TEXT DEFAULT 'daily',
        word_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS jp_reading_question (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        passage_id INTEGER NOT NULL,
        question_jp TEXT NOT NULL,
        question_ko TEXT,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        explanation TEXT,
        FOREIGN KEY (passage_id) REFERENCES jp_reading_passage(id) ON DELETE CASCADE
    )""",
    # ── Writing Practice ─────────────────────────────────
    """CREATE TABLE IF NOT EXISTS jp_writing_exercise (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise_type TEXT NOT NULL,
        jlpt_level TEXT DEFAULT 'N5',
        prompt_ko TEXT NOT NULL,
        prompt_jp TEXT,
        answer_jp TEXT NOT NULL,
        alt_answers TEXT,
        grammar_point TEXT,
        hint TEXT,
        difficulty INTEGER DEFAULT 1
    )""",
    # ── Finance Manager tables ──
    """CREATE TABLE IF NOT EXISTS fin_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        issuer TEXT NOT NULL DEFAULT '',
        card_type TEXT NOT NULL DEFAULT 'CREDIT',
        last_four TEXT,
        billing_day INTEGER,
        annual_fee INTEGER NOT NULL DEFAULT 0,
        annual_fee_waived INTEGER NOT NULL DEFAULT 0,
        color TEXT NOT NULL DEFAULT '#6366f1',
        icon TEXT,
        memo TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS fin_card_benefits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        merchant TEXT,
        benefit_type TEXT NOT NULL DEFAULT 'DISCOUNT',
        benefit_value REAL NOT NULL DEFAULT 0,
        benefit_unit TEXT NOT NULL DEFAULT 'PERCENT',
        monthly_limit INTEGER,
        min_spend INTEGER,
        conditions TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (card_id) REFERENCES fin_cards(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS fin_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'OTHER',
        price INTEGER NOT NULL DEFAULT 0,
        billing_cycle TEXT NOT NULL DEFAULT 'MONTHLY',
        billing_day INTEGER,
        card_id INTEGER,
        is_free_bundled INTEGER NOT NULL DEFAULT 0,
        bundled_via TEXT,
        benefits_json TEXT NOT NULL DEFAULT '[]',
        usage_check_interval INTEGER NOT NULL DEFAULT 7,
        last_used_at TEXT,
        url TEXT,
        icon TEXT,
        memo TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        start_date TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (card_id) REFERENCES fin_cards(id) ON DELETE SET NULL
    )""",
    """CREATE TABLE IF NOT EXISTS fin_subscription_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id INTEGER NOT NULL,
        used_at TEXT NOT NULL DEFAULT (datetime('now')),
        benefit_used TEXT,
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (subscription_id) REFERENCES fin_subscriptions(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS fin_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        amount INTEGER NOT NULL,
        category TEXT NOT NULL DEFAULT 'OTHER',
        subcategory TEXT,
        merchant TEXT,
        card_id INTEGER,
        description TEXT,
        is_recurring INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (card_id) REFERENCES fin_cards(id) ON DELETE SET NULL
    )""",
    """CREATE TABLE IF NOT EXISTS fin_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        asset_type TEXT NOT NULL DEFAULT 'CASH',
        institution TEXT,
        balance INTEGER NOT NULL DEFAULT 0,
        currency TEXT NOT NULL DEFAULT 'KRW',
        last_updated TEXT NOT NULL DEFAULT (datetime('now')),
        memo TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS fin_budget (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year_month TEXT NOT NULL,
        category TEXT NOT NULL,
        budget_amount INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(year_month, category)
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
    "CREATE INDEX IF NOT EXISTS idx_jp_daily_quests_date ON jp_daily_quests(date)",
    "CREATE INDEX IF NOT EXISTS idx_jp_weekly_challenges_week ON jp_weekly_challenges(week_start)",
    # Grammar & Kanji indexes
    "CREATE INDEX IF NOT EXISTS idx_jp_grammar_level ON jp_grammar(jlpt_level)",
    "CREATE INDEX IF NOT EXISTS idx_jp_grammar_category ON jp_grammar(category)",
    "CREATE INDEX IF NOT EXISTS idx_jp_grammar_example_gid ON jp_grammar_example(grammar_id)",
    "CREATE INDEX IF NOT EXISTS idx_jp_grammar_srs_next ON jp_grammar_srs(next_review)",
    "CREATE INDEX IF NOT EXISTS idx_jp_kanji_level ON jp_kanji(jlpt_level)",
    "CREATE INDEX IF NOT EXISTS idx_jp_kanji_vocab_kanji ON jp_kanji_vocab_link(kanji_id)",
    "CREATE INDEX IF NOT EXISTS idx_jp_kanji_vocab_vocab ON jp_kanji_vocab_link(vocab_id)",
    # Reading indexes
    "CREATE INDEX IF NOT EXISTS idx_jp_reading_passage_level ON jp_reading_passage(jlpt_level)",
    "CREATE INDEX IF NOT EXISTS idx_jp_reading_question_passage ON jp_reading_question(passage_id)",
    # Writing indexes
    "CREATE INDEX IF NOT EXISTS idx_jp_writing_type_level ON jp_writing_exercise(exercise_type, jlpt_level)",
    # Finance indexes
    "CREATE INDEX IF NOT EXISTS idx_fin_card_benefits_card ON fin_card_benefits(card_id)",
    "CREATE INDEX IF NOT EXISTS idx_fin_subscriptions_active ON fin_subscriptions(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_fin_sub_usage_sub ON fin_subscription_usage(subscription_id)",
    "CREATE INDEX IF NOT EXISTS idx_fin_sub_usage_date ON fin_subscription_usage(used_at)",
    "CREATE INDEX IF NOT EXISTS idx_fin_expenses_date ON fin_expenses(date)",
    "CREATE INDEX IF NOT EXISTS idx_fin_expenses_category ON fin_expenses(category)",
    "CREATE INDEX IF NOT EXISTS idx_fin_expenses_card ON fin_expenses(card_id)",
    "CREATE INDEX IF NOT EXISTS idx_fin_assets_type ON fin_assets(asset_type)",
    "CREATE INDEX IF NOT EXISTS idx_fin_budget_month ON fin_budget(year_month)",
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
    ("daily_quests_completed", "jp_player_stats", "INTEGER NOT NULL DEFAULT 0"),
    ("weekly_challenges_completed", "jp_player_stats", "INTEGER NOT NULL DEFAULT 0"),
    ("total_quizzes", "jp_player_stats", "INTEGER NOT NULL DEFAULT 0"),
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
