"""Singleton aiosqlite connection manager."""

import asyncio

import aiosqlite

_connection: aiosqlite.Connection | None = None
_db_lock = asyncio.Lock()
_db_path: str | None = None


def set_db_path(path: str) -> None:
    global _db_path
    _db_path = path


def _get_db_path() -> str:
    if _db_path is not None:
        return _db_path
    from app.config import settings
    return settings.DB_PATH


async def _create_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(_get_db_path())
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA busy_timeout=5000")
    await conn.execute("PRAGMA cache_size=-8000")
    await conn.execute("PRAGMA synchronous=NORMAL")
    return conn


async def get_db() -> aiosqlite.Connection:
    global _connection
    async with _db_lock:
        if _connection is not None:
            try:
                await _connection.execute("SELECT 1")
            except Exception:
                try:
                    await _connection.close()
                except Exception:
                    pass
                _connection = None
        if _connection is None:
            _connection = await _create_connection()
    return _connection


async def close_db() -> None:
    global _connection
    async with _db_lock:
        if _connection is not None:
            await _connection.close()
            _connection = None
