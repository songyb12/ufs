import aiosqlite

_db_path: str = ""


def set_db_path(path: str) -> None:
    global _db_path
    _db_path = path


async def get_db() -> aiosqlite.Connection:
    """Get an aiosqlite connection. Caller must close or use as async context."""
    db = await aiosqlite.connect(_db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")  # Wait up to 5s on lock
    await db.execute("PRAGMA cache_size=-8000")  # 8MB page cache
    await db.execute("PRAGMA synchronous=NORMAL")  # Faster writes with WAL
    return db
