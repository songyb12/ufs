"""Japanese writing practice router — translation, sentence ordering, grammar usage."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.writing_service import (
    check_writing_answer,
    get_grammar_usage_exercise,
    get_sentence_order_exercise,
    get_translation_exercise,
)

logger = logging.getLogger("life-master.writing-router")

router = APIRouter(prefix="/japanese/writing", tags=["japanese-writing"])


# ── Schemas ──────────────────────────────────────────────


class WritingAnswerRequest(BaseModel):
    user_answer: str


# ── Endpoints ────────────────────────────────────────────


@router.get("/translation")
async def translation_exercise(
    jlpt_level: str = Query("N5", pattern=r"^N[1-5]$"),
):
    """Get a random translation exercise (Korean → Japanese)."""
    result = await get_translation_exercise(jlpt_level)
    if not result:
        raise HTTPException(status_code=404, detail="No translation exercises for this level")
    return result


@router.get("/sentence-order")
async def sentence_order_exercise(
    jlpt_level: str = Query("N5", pattern=r"^N[1-5]$"),
):
    """Get a random sentence ordering exercise."""
    result = await get_sentence_order_exercise(jlpt_level)
    if not result:
        raise HTTPException(status_code=404, detail="No sentence-order exercises for this level")
    return result


@router.get("/grammar-usage")
async def grammar_usage_exercise(
    jlpt_level: str = Query("N5", pattern=r"^N[1-5]$"),
):
    """Get a random grammar usage writing exercise."""
    result = await get_grammar_usage_exercise(jlpt_level)
    if not result:
        raise HTTPException(status_code=404, detail="No grammar-usage exercises for this level")
    return result


@router.post("/check/{exercise_id}")
async def check_answer(exercise_id: int, data: WritingAnswerRequest):
    """Check a writing answer against correct answers."""
    result = await check_writing_answer(exercise_id, data.user_answer)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/seed")
async def seed_writing():
    """Seed N5 writing exercise data."""
    from app.database.jp_writing_seed import seed_writing_data

    count = await seed_writing_data()
    return {"message": f"Seeded {count} writing exercises"}
