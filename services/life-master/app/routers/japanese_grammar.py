"""Japanese grammar learning router — grammar points, SRS, quizzes."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.grammar_service import (
    get_grammar_detail,
    get_grammar_for_review,
    get_grammar_list,
    grammar_quiz_fill_blank,
    grammar_quiz_sentence_order,
    submit_grammar_review,
)

logger = logging.getLogger("life-master.grammar-router")

router = APIRouter(prefix="/japanese/grammar", tags=["japanese-grammar"])


# ── Schemas ──────────────────────────────────────────────


class GrammarReviewRequest(BaseModel):
    quality: int = Field(ge=0, le=5)


# ── Endpoints ────────────────────────────────────────────


@router.get("/list")
async def list_grammar(
    jlpt_level: str | None = Query(None, pattern=r"^N[1-5]$"),
    category: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List grammar points with filtering and pagination."""
    return await get_grammar_list(jlpt_level, category, page, per_page)


@router.get("/categories")
async def grammar_categories():
    """List available grammar categories."""
    from app.database.connection import get_db

    db = await get_db()
    cursor = await db.execute(
        "SELECT DISTINCT category, COUNT(*) as cnt FROM jp_grammar WHERE is_active = 1 GROUP BY category ORDER BY cnt DESC"
    )
    rows = await cursor.fetchall()
    return [{"category": r[0], "count": r[1]} for r in rows]


@router.get("/{grammar_id}")
async def grammar_detail(grammar_id: int):
    """Get grammar point with examples and SRS state."""
    result = await get_grammar_detail(grammar_id)
    if not result:
        raise HTTPException(status_code=404, detail="Grammar point not found")
    return result


@router.get("/review/due")
async def grammar_review_due(limit: int = Query(20, ge=1, le=100)):
    """Get grammar cards due for review today."""
    return await get_grammar_for_review(limit)


@router.post("/review/{grammar_id}")
async def review_grammar(grammar_id: int, data: GrammarReviewRequest):
    """Submit a grammar review (quality 0-5) and update SRS."""
    # Verify grammar exists
    from app.database.connection import get_db

    db = await get_db()
    cursor = await db.execute("SELECT id FROM jp_grammar WHERE id = ?", (grammar_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Grammar point not found")

    try:
        result = await submit_grammar_review(grammar_id, data.quality)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result


@router.get("/quiz/fill-blank")
async def quiz_fill_blank(
    jlpt_level: str = Query("N5", pattern=r"^N[1-5]$"),
    count: int = Query(5, ge=1, le=20),
):
    """Generate fill-in-the-blank grammar quiz."""
    questions = await grammar_quiz_fill_blank(jlpt_level, count)
    if not questions:
        raise HTTPException(status_code=404, detail="No grammar data for this level")
    return {"quiz_type": "fill_blank", "jlpt_level": jlpt_level, "questions": questions}


@router.get("/quiz/sentence-order")
async def quiz_sentence_order(
    jlpt_level: str = Query("N5", pattern=r"^N[1-5]$"),
    count: int = Query(5, ge=1, le=20),
):
    """Generate sentence-ordering grammar quiz."""
    questions = await grammar_quiz_sentence_order(jlpt_level, count)
    if not questions:
        raise HTTPException(status_code=404, detail="No grammar data for this level")
    return {"quiz_type": "sentence_order", "jlpt_level": jlpt_level, "questions": questions}


@router.post("/seed")
async def seed_grammar():
    """Seed N5 grammar data."""
    from app.database.jp_grammar_seed import seed_grammar_data

    count = await seed_grammar_data()
    return {"message": f"Seeded {count} grammar points"}
