"""Japanese kanji learning router — listing, search, quizzes."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.services.kanji_service import (
    get_kanji_detail,
    get_kanji_list,
    kanji_quiz_meaning,
    kanji_quiz_reading,
    search_kanji,
)

logger = logging.getLogger("life-master.kanji-router")

router = APIRouter(prefix="/japanese/kanji", tags=["japanese-kanji"])


# ── Endpoints ────────────────────────────────────────────


@router.get("/search")
async def kanji_search(
    q: str = Query(min_length=1, max_length=50),
):
    """Search kanji by character, meaning, or readings."""
    results = await search_kanji(q)
    return {"query": q, "count": len(results), "items": results}


@router.get("/quiz/reading")
async def quiz_reading(
    jlpt_level: str | None = Query(None, pattern=r"^N[1-5]$"),
    count: int = Query(5, ge=1, le=20),
):
    """Reading quiz: show kanji, pick the correct reading."""
    questions = await kanji_quiz_reading(jlpt_level, count)
    if not questions:
        raise HTTPException(status_code=404, detail="No kanji data for this level")
    return {"quiz_type": "kanji_reading", "jlpt_level": jlpt_level, "questions": questions}


@router.get("/quiz/meaning")
async def quiz_meaning(
    jlpt_level: str | None = Query(None, pattern=r"^N[1-5]$"),
    count: int = Query(5, ge=1, le=20),
):
    """Meaning quiz: show kanji, pick the correct meaning."""
    questions = await kanji_quiz_meaning(jlpt_level, count)
    if not questions:
        raise HTTPException(status_code=404, detail="No kanji data for this level")
    return {"quiz_type": "kanji_meaning", "jlpt_level": jlpt_level, "questions": questions}


@router.get("/{kanji_id}")
async def kanji_detail(kanji_id: int):
    """Get kanji detail with linked vocabulary."""
    result = await get_kanji_detail(kanji_id)
    if not result:
        raise HTTPException(status_code=404, detail="Kanji not found")
    return result


@router.get("")
async def list_kanji(
    jlpt_level: str | None = Query(None, pattern=r"^N[1-5]$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List kanji with filtering and pagination."""
    return await get_kanji_list(jlpt_level, page, per_page)
