"""
Tests for SOXL Briefing module (store, generator, routes).

Covers:
- init_briefing_table — table creation
- save_briefing / get_latest_briefing — UPSERT + retrieval
- get_briefing_history — limit parameter
- GET /soxl-briefing/latest — 404 when empty
- _collect_context — returns empty dict when no SOXL data
- generate_soxl_briefing — fallback when no data / no API key
"""

import pytest
import pytest_asyncio

from tests.conftest import setup_db  # noqa: F401 — session-scoped DB fixture

from app.database.connection import get_db
from app.soxl_briefing.store import (
    get_briefing_history,
    get_latest_briefing,
    init_briefing_table,
    save_briefing,
)


# ── Helpers ──

async def _cleanup_briefings():
    db = await get_db()
    await db.execute("DELETE FROM soxl_briefings")
    await db.commit()


# ════════════════════════════════════════════════════════════════
# Store unit tests
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_init_briefing_table(setup_db):  # noqa: F811
    """init_briefing_table should create the table without error."""
    await init_briefing_table()
    db = await get_db()
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='soxl_briefings'"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "soxl_briefings"


@pytest.mark.asyncio
async def test_save_and_get_briefing(setup_db):  # noqa: F811
    """save_briefing should persist, get_latest_briefing should retrieve.

    Saving the same date twice should UPSERT (overwrite).
    """
    await init_briefing_table()
    await _cleanup_briefings()

    # First save
    rowid = await save_briefing("2026-03-31", "첫 브리핑 내용", {"price": 25.0})
    assert rowid > 0

    latest = await get_latest_briefing()
    assert latest is not None
    assert latest["date"] == "2026-03-31"
    assert latest["briefing_text"] == "첫 브리핑 내용"
    assert latest["metadata"]["price"] == 25.0

    # UPSERT — same date, new content
    await save_briefing("2026-03-31", "업데이트된 브리핑", {"price": 26.0})
    latest2 = await get_latest_briefing()
    assert latest2["briefing_text"] == "업데이트된 브리핑"
    assert latest2["metadata"]["price"] == 26.0

    await _cleanup_briefings()


@pytest.mark.asyncio
async def test_briefing_history(setup_db):  # noqa: F811
    """get_briefing_history should respect the limit parameter."""
    await init_briefing_table()
    await _cleanup_briefings()

    await save_briefing("2026-03-29", "day1", None)
    await save_briefing("2026-03-30", "day2", None)
    await save_briefing("2026-03-31", "day3", None)

    # limit=2 should return only the 2 most recent
    history = await get_briefing_history(limit=2)
    assert len(history) == 2
    assert history[0]["date"] == "2026-03-31"
    assert history[1]["date"] == "2026-03-30"

    # default limit should return all 3
    all_history = await get_briefing_history()
    assert len(all_history) == 3

    await _cleanup_briefings()


# ════════════════════════════════════════════════════════════════
# Route integration test
# ════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def briefing_client(setup_db):  # noqa: F811
    """Async HTTP client with the soxl-briefing router mounted."""
    import httpx
    from fastapi import FastAPI
    from app.soxl_briefing.routes import router

    test_app = FastAPI()
    test_app.include_router(router)

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_generate_endpoint_latest_404(briefing_client):
    """GET /soxl-briefing/latest should return 404 when no briefings exist."""
    await init_briefing_table()
    await _cleanup_briefings()

    resp = await briefing_client.get("/soxl-briefing/latest")
    assert resp.status_code == 404
    assert "브리핑" in resp.json()["detail"]


# ════════════════════════════════════════════════════════════════
# Generator tests (context collection + fallback)
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_collect_context_empty_db(setup_db):  # noqa: F811
    """_collect_context returns an empty-ish dict when no SOXL data exists."""
    from app.soxl_briefing.generator import _collect_context

    ctx = await _collect_context()
    # No SOXL rows in the in-memory DB → price should be absent
    assert ctx.get("price") is None
    # geo_events key should still exist (defaults to [])
    assert isinstance(ctx.get("geo_events", []), list)


@pytest.mark.asyncio
async def test_generate_fallback_no_price(setup_db):  # noqa: F811
    """generate_soxl_briefing returns a fallback when no price data exists."""
    await init_briefing_table()
    await _cleanup_briefings()

    from app.soxl_briefing.generator import generate_soxl_briefing

    result = await generate_soxl_briefing()
    assert result["status"] == "error"
    assert "가격 데이터" in result["briefing_text"] or "데이터" in result["briefing_text"]
    assert result["metadata"].get("error") == "no_price_data"


@pytest.mark.asyncio
async def test_generate_fallback_no_api_key(setup_db):  # noqa: F811
    """generate_soxl_briefing returns a fallback when LLM_API_KEY is empty."""
    await init_briefing_table()
    await _cleanup_briefings()

    # Seed minimal SOXL price data so we pass the price check
    db = await get_db()
    for i in range(5):
        await db.execute(
            """INSERT OR IGNORE INTO price_history
               (symbol, market, trade_date, open, high, low, close, volume)
               VALUES ('SOXL', 'US', ?, 25, 26, 24, 25, 1000000)""",
            (f"2026-03-{27 + i:02d}",),
        )
    await db.commit()

    from app.soxl_briefing.generator import generate_soxl_briefing
    from app.config import settings

    original_key = settings.LLM_API_KEY
    try:
        settings.LLM_API_KEY = ""
        result = await generate_soxl_briefing()
        assert result["status"] == "error"
        assert "API 키" in result["briefing_text"]
        assert result["metadata"].get("error") == "no_api_key"
    finally:
        settings.LLM_API_KEY = original_key
        # Cleanup seeded data
        await db.execute("DELETE FROM price_history WHERE symbol='SOXL'")
        await db.commit()
