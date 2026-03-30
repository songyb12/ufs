"""SOXL Briefing SQLite store.

Persists daily SOXL briefings so they can be retrieved later
without re-running the LLM.  Reuses the existing VIBE DB
connection from app.database.connection.
"""

import json
import logging

from app.database.connection import get_db

logger = logging.getLogger("vibe.soxl_briefing.store")


async def init_briefing_table() -> None:
    """Create the soxl_briefings table if it does not exist."""
    db = await get_db()
    await db.execute(
        """CREATE TABLE IF NOT EXISTS soxl_briefings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT    NOT NULL UNIQUE,
            briefing_text TEXT  NOT NULL,
            metadata_json TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        )"""
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_soxl_briefings_date "
        "ON soxl_briefings(date)"
    )
    await db.commit()
    logger.info("soxl_briefings table ready")


async def save_briefing(date: str, text: str, metadata: dict | None = None) -> int:
    """Save or update a briefing for *date* (UPSERT).

    Returns the row id of the inserted/updated row.
    """
    db = await get_db()
    meta_str = json.dumps(metadata, ensure_ascii=False) if metadata else None
    cursor = await db.execute(
        """INSERT INTO soxl_briefings (date, briefing_text, metadata_json)
           VALUES (?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
               briefing_text = excluded.briefing_text,
               metadata_json = excluded.metadata_json,
               created_at    = datetime('now')""",
        (date, text, meta_str),
    )
    await db.commit()
    logger.info("Briefing saved for %s (rowid=%d)", date, cursor.lastrowid)
    return cursor.lastrowid


async def get_latest_briefing() -> dict | None:
    """Return the most recent briefing, or None."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, date, briefing_text, metadata_json, created_at
           FROM soxl_briefings
           ORDER BY date DESC LIMIT 1"""
    )
    row = await cursor.fetchone()
    return _row_to_dict(row) if row else None


async def get_briefing_history(limit: int = 30) -> list[dict]:
    """Return the *limit* most recent briefings (newest first)."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, date, briefing_text, metadata_json, created_at
           FROM soxl_briefings
           ORDER BY date DESC LIMIT ?""",
        (limit,),
    )
    return [_row_to_dict(r) for r in await cursor.fetchall()]


def _row_to_dict(row) -> dict:
    """Convert a DB row to a plain dict."""
    meta = None
    if row[3]:
        try:
            meta = json.loads(row[3])
        except (json.JSONDecodeError, TypeError):
            meta = None
    return {
        "id": row[0],
        "date": row[1],
        "briefing_text": row[2],
        "metadata": meta,
        "created_at": row[4],
    }
