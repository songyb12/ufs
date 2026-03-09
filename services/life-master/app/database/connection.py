"""Singleton aiosqlite connection manager."""

import asyncio

import aiosqlite

_connection: aiosqlite.Connection | None = None
_db_lock = asyncio.Lock()
_db_path: str = "/app/data/life-master.db"


def set_db_path(path: str) -> None:
    global _db_path
    _db_path = path


async def get_db() -> aiosqlite.Connection:
    global _connection
    async with _db_lock:
        if _connection is None:
            _connection = await aiosqlite.connect(_db_path)
            _connection.row_factory = aiosqlite.Row
            await _connection.execute("PRAGMA journal_mode=WAL")
            await _connection.execute("PRAGMA foreign_keys=ON")
            await _connection.execute("PRAGMA busy_timeout=5000")
            await _connection.execute("PRAGMA cache_size=-8000")
            await _connection.execute("PRAGMA synchronous=NORMAL")
    return _connection


async def close_db() -> None:
    global _connection
    async with _db_lock:
        if _connection is not None:
            await _connection.close()
            _connection = None
