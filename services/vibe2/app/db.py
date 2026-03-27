"""SQLite database connection and schema initialization."""

import logging
import sqlite3

import aiosqlite
import bcrypt

from app.config import settings

logger = logging.getLogger("vibe2.db")

_db: aiosqlite.Connection | None = None

# Extract file path from DATABASE_URL (strip "sqlite:///")
_DB_PATH = settings.DATABASE_URL.replace("sqlite:///", "")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(symbol, trade_date)
);

CREATE TABLE IF NOT EXISTS macro_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_date TEXT NOT NULL UNIQUE,
    vix REAL,
    dxy REAL,
    us_10y_yield REAL,
    us_2y_yield REAL,
    yield_spread REAL,
    wti_crude REAL,
    gold_price REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sentiment_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_date TEXT NOT NULL UNIQUE,
    fear_greed_index INTEGER,
    put_call_ratio REAL,
    vix_term_structure TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_date TEXT NOT NULL,
    signal_level TEXT NOT NULL,
    score REAL NOT NULL,
    summary TEXT,
    details_json TEXT,
    action TEXT,
    risks_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_date TEXT NOT NULL,
    signal_level TEXT,
    score REAL,
    commentary TEXT,
    full_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    last_login TEXT
);

CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(signal_date);
CREATE INDEX IF NOT EXISTS idx_briefings_date ON briefings(briefing_date);
"""

# dev account seed: dev / dev1234
_DEV_USERNAME = "dev"
_DEV_PASSWORD = "dev1234"


async def init_db() -> None:
    """Initialize database: create tables, set PRAGMAs, seed dev user."""
    global _db
    _db = await aiosqlite.connect(_DB_PATH)
    _db.row_factory = aiosqlite.Row

    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    await _db.execute("PRAGMA busy_timeout=5000")
    await _db.execute("PRAGMA cache_size=-8000")
    await _db.execute("PRAGMA synchronous=NORMAL")

    await _db.executescript(SCHEMA_SQL)

    # Seed dev user if not exists
    cursor = await _db.execute(
        "SELECT id FROM users WHERE username = ?", (_DEV_USERNAME,)
    )
    if not await cursor.fetchone():
        hashed = bcrypt.hashpw(
            _DEV_PASSWORD.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        await _db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (_DEV_USERNAME, hashed),
        )
        await _db.commit()
        logger.info("Dev user seeded: %s", _DEV_USERNAME)

    logger.info("Database initialized: %s", _DB_PATH)


async def close_db() -> None:
    """Close database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


async def get_db() -> aiosqlite.Connection:
    """FastAPI dependency — returns the shared database connection."""
    if _db is None:
        await init_db()
    return _db


_sync_schema_initialized = False


def get_sync_db() -> sqlite3.Connection:
    """Return a synchronous sqlite3 connection for collector use.

    Collectors run blocking yfinance calls, so async is unnecessary.
    Each call creates a fresh connection — caller must close it.
    Ensures schema is created on first call.
    """
    global _sync_schema_initialized
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")

    if not _sync_schema_initialized:
        conn.executescript(SCHEMA_SQL)
        _sync_schema_initialized = True
        logger.info("Sync schema initialized: %s", _DB_PATH)

    return conn
