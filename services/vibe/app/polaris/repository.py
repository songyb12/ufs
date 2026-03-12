"""POLARIS DB repository — CRUD for figures, profiles, events, predictions."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from app.database.connection import get_db

logger = logging.getLogger("vibe.polaris.repository")


def _safe_json_loads(value: Any, fallback: Any = None) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return dict(row)


# ── Schema bootstrap ──


POLARIS_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS polaris_figures (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        name_ko TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT '',
        country TEXT NOT NULL DEFAULT '',
        party TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS polaris_profiles (
        id TEXT PRIMARY KEY,
        figure_id TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        profile_data TEXT NOT NULL DEFAULT '{}',
        changelog TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (figure_id) REFERENCES polaris_figures(id),
        UNIQUE(figure_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS polaris_events (
        id TEXT PRIMARY KEY,
        figure_id TEXT NOT NULL,
        event_type TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        raw_content TEXT NOT NULL DEFAULT '',
        source_url TEXT NOT NULL DEFAULT '',
        event_date TEXT NOT NULL DEFAULT '',
        significance INTEGER NOT NULL DEFAULT 1,
        categories TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (figure_id) REFERENCES polaris_figures(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS polaris_predictions (
        id TEXT PRIMARY KEY,
        figure_id TEXT NOT NULL,
        trigger_event_id TEXT,
        prediction_type TEXT NOT NULL DEFAULT 'action',
        prediction TEXT NOT NULL DEFAULT '',
        reasoning TEXT NOT NULL DEFAULT '',
        confidence REAL NOT NULL DEFAULT 0.0,
        timeframe TEXT NOT NULL DEFAULT 'short',
        market_impact TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'pending',
        outcome TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (figure_id) REFERENCES polaris_figures(id)
    )
    """,
]

POLARIS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_polaris_figures_status ON polaris_figures(status)",
    "CREATE INDEX IF NOT EXISTS idx_polaris_profiles_figure ON polaris_profiles(figure_id, version)",
    "CREATE INDEX IF NOT EXISTS idx_polaris_events_figure ON polaris_events(figure_id, event_date)",
    "CREATE INDEX IF NOT EXISTS idx_polaris_events_significance ON polaris_events(significance, event_date)",
    "CREATE INDEX IF NOT EXISTS idx_polaris_predictions_figure ON polaris_predictions(figure_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_polaris_predictions_status ON polaris_predictions(status)",
]


async def init_polaris_schema() -> None:
    """Create POLARIS tables and indexes (idempotent)."""
    db = await get_db()
    for ddl in POLARIS_TABLES:
        await db.execute(ddl)
    for idx in POLARIS_INDEXES:
        await db.execute(idx)
    await db.commit()
    logger.info("POLARIS schema initialized (%d tables, %d indexes)",
                len(POLARIS_TABLES), len(POLARIS_INDEXES))


# ── Figures ──


async def create_figure(name: str, name_ko: str = "", role: str = "",
                        country: str = "", party: str = "") -> dict:
    db = await get_db()
    figure_id = str(uuid4())
    await db.execute(
        """INSERT INTO polaris_figures (id, name, name_ko, role, country, party)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (figure_id, name, name_ko, role, country, party),
    )
    await db.commit()
    return {"id": figure_id, "name": name, "name_ko": name_ko,
            "role": role, "country": country, "party": party,
            "status": "active", "created_at": ""}


async def get_figures(status: str = "active") -> list[dict]:
    db = await get_db()
    c = await db.execute(
        """SELECT f.*, (SELECT MAX(version) FROM polaris_profiles WHERE figure_id = f.id) as latest_profile_version
           FROM polaris_figures f WHERE f.status = ? ORDER BY f.created_at""",
        (status,),
    )
    return [_row_to_dict(r) for r in await c.fetchall()]


async def get_figure(figure_id: str) -> dict:
    db = await get_db()
    c = await db.execute(
        """SELECT f.*, (SELECT MAX(version) FROM polaris_profiles WHERE figure_id = f.id) as latest_profile_version
           FROM polaris_figures f WHERE f.id = ?""",
        (figure_id,),
    )
    row = await c.fetchone()
    return _row_to_dict(row)


async def get_figure_by_name(name: str) -> dict:
    db = await get_db()
    c = await db.execute(
        "SELECT * FROM polaris_figures WHERE name = ? OR name_ko = ?",
        (name, name),
    )
    row = await c.fetchone()
    return _row_to_dict(row)


# ── Profiles ──


async def get_latest_profile(figure_id: str) -> dict | None:
    db = await get_db()
    c = await db.execute(
        """SELECT * FROM polaris_profiles
           WHERE figure_id = ? ORDER BY version DESC LIMIT 1""",
        (figure_id,),
    )
    row = await c.fetchone()
    if not row:
        return None
    result = _row_to_dict(row)
    result["profile_data"] = _safe_json_loads(result.get("profile_data"), {})
    return result


async def get_profile_history(figure_id: str) -> list[dict]:
    db = await get_db()
    c = await db.execute(
        """SELECT version, changelog, created_at FROM polaris_profiles
           WHERE figure_id = ? ORDER BY version DESC""",
        (figure_id,),
    )
    return [_row_to_dict(r) for r in await c.fetchall()]


async def insert_profile(figure_id: str, profile_data: dict,
                         changelog: str = "초기 프로파일 생성") -> dict:
    db = await get_db()
    c = await db.execute(
        "SELECT COALESCE(MAX(version), 0) FROM polaris_profiles WHERE figure_id = ?",
        (figure_id,),
    )
    current_version = (await c.fetchone())[0]
    new_version = current_version + 1

    profile_id = str(uuid4())
    await db.execute(
        """INSERT INTO polaris_profiles (id, figure_id, version, profile_data, changelog)
           VALUES (?, ?, ?, ?, ?)""",
        (profile_id, figure_id, new_version,
         json.dumps(profile_data, ensure_ascii=False), changelog),
    )
    await db.commit()
    return {
        "id": profile_id, "figure_id": figure_id,
        "version": new_version, "profile_data": profile_data,
        "changelog": changelog,
    }


# ── Events ──


async def insert_event(figure_id: str, event_type: str, title: str,
                       summary: str = "", raw_content: str = "",
                       source_url: str = "", event_date: str = "",
                       significance: int = 1,
                       categories: list[str] | None = None) -> dict:
    db = await get_db()
    event_id = str(uuid4())
    await db.execute(
        """INSERT INTO polaris_events
           (id, figure_id, event_type, title, summary, raw_content, source_url,
            event_date, significance, categories)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, figure_id, event_type, title, summary, raw_content,
         source_url, event_date, significance,
         json.dumps(categories or [], ensure_ascii=False)),
    )
    await db.commit()
    return {"id": event_id, "figure_id": figure_id, "title": title,
            "significance": significance}


async def get_events(figure_id: str, limit: int = 50,
                     min_significance: int = 1) -> list[dict]:
    db = await get_db()
    c = await db.execute(
        """SELECT * FROM polaris_events
           WHERE figure_id = ? AND significance >= ?
           ORDER BY event_date DESC LIMIT ?""",
        (figure_id, min_significance, limit),
    )
    rows = [_row_to_dict(r) for r in await c.fetchall()]
    for r in rows:
        r["categories"] = _safe_json_loads(r.get("categories"), [])
    return rows


async def get_event(event_id: str) -> dict | None:
    db = await get_db()
    c = await db.execute("SELECT * FROM polaris_events WHERE id = ?", (event_id,))
    row = await c.fetchone()
    if not row:
        return None
    result = _row_to_dict(row)
    result["categories"] = _safe_json_loads(result.get("categories"), [])
    return result


# ── Predictions ──


async def insert_prediction(figure_id: str, prediction_type: str,
                            prediction: str, reasoning: str,
                            confidence: float, timeframe: str = "short",
                            market_impact: dict | None = None,
                            trigger_event_id: str | None = None) -> dict:
    db = await get_db()
    pred_id = str(uuid4())
    await db.execute(
        """INSERT INTO polaris_predictions
           (id, figure_id, trigger_event_id, prediction_type, prediction,
            reasoning, confidence, timeframe, market_impact)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pred_id, figure_id, trigger_event_id, prediction_type, prediction,
         reasoning, confidence, timeframe,
         json.dumps(market_impact or {}, ensure_ascii=False)),
    )
    await db.commit()
    return {"id": pred_id, "figure_id": figure_id,
            "prediction": prediction, "confidence": confidence}


async def get_predictions(figure_id: str, limit: int = 20,
                          status: str | None = None) -> list[dict]:
    db = await get_db()
    if status:
        c = await db.execute(
            """SELECT * FROM polaris_predictions
               WHERE figure_id = ? AND status = ?
               ORDER BY created_at DESC LIMIT ?""",
            (figure_id, status, limit),
        )
    else:
        c = await db.execute(
            """SELECT * FROM polaris_predictions
               WHERE figure_id = ? ORDER BY created_at DESC LIMIT ?""",
            (figure_id, limit),
        )
    rows = [_row_to_dict(r) for r in await c.fetchall()]
    for r in rows:
        r["market_impact"] = _safe_json_loads(r.get("market_impact"), {})
    return rows


async def update_prediction_outcome(prediction_id: str, status: str,
                                    outcome: str) -> bool:
    db = await get_db()
    c = await db.execute(
        "UPDATE polaris_predictions SET status = ?, outcome = ? WHERE id = ?",
        (status, outcome, prediction_id),
    )
    await db.commit()
    return c.rowcount > 0


# ── Statistics ──


async def get_prediction_stats(figure_id: str) -> dict:
    """Get prediction accuracy statistics for a figure."""
    db = await get_db()
    c = await db.execute(
        """SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
            SUM(CASE WHEN status = 'partially_confirmed' THEN 1 ELSE 0 END) as partial,
            SUM(CASE WHEN status = 'wrong' THEN 1 ELSE 0 END) as wrong,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            AVG(confidence) as avg_confidence
           FROM polaris_predictions WHERE figure_id = ?""",
        (figure_id,),
    )
    row = await c.fetchone()
    if not row:
        return {"total": 0}
    d = _row_to_dict(row)
    resolved = (d.get("confirmed") or 0) + (d.get("wrong") or 0)
    d["accuracy"] = round((d.get("confirmed") or 0) / max(resolved, 1) * 100, 1)
    return d


async def get_event_stats(figure_id: str) -> dict:
    """Get event statistics for a figure."""
    db = await get_db()
    c = await db.execute(
        """SELECT
            COUNT(*) as total,
            AVG(significance) as avg_significance,
            MAX(event_date) as latest_event_date
           FROM polaris_events WHERE figure_id = ?""",
        (figure_id,),
    )
    row = await c.fetchone()
    return _row_to_dict(row) if row else {"total": 0}
