import logging

import aiosqlite

logger = logging.getLogger("vibe.database")

_db_path: str = ""
_connection: aiosqlite.Connection | None = None


def set_db_path(path: str) -> None:
    global _db_path
    _db_path = path


async def get_db() -> aiosqlite.Connection:
    """Get a cached aiosqlite connection. PRAGMAs are set once on first connect."""
    global _connection
    if _connection is not None:
        try:
            # Verify connection is still alive
            await _connection.execute("SELECT 1")
            return _connection
        except (aiosqlite.DatabaseError, OSError) as e:
            logger.warning("DB connection stale, reconnecting: %s", e)
            _connection = None

    db = await aiosqlite.connect(_db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA cache_size=-8000")
    await db.execute("PRAGMA synchronous=NORMAL")
    _connection = db
    return db


async def close_db() -> None:
    """Close the cached connection. Call at application shutdown."""
    global _connection
    if _connection is not None:
        try:
            await _connection.close()
        except (aiosqlite.DatabaseError, OSError) as e:
            logger.warning("Error closing DB connection: %s", e)
        _connection = None
