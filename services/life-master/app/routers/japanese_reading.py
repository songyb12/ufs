"""Japanese reading practice router — passages, comprehension, vocab highlights."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.reading_service import (
    get_passage_detail,
    get_passage_vocab_highlights,
    get_passages,
    submit_reading_answers,
)

logger = logging.getLogger("life-master.reading-router")

router = APIRouter(prefix="/japanese/reading", tags=["japanese-reading"])


# ── Schemas ──────────────────────────────────────────────


class ReadingAnswersRequest(BaseModel):
    answers: dict[str, str]  # {question_id: "a"|"b"|"c"|"d"}


# ── Endpoints ────────────────────────────────────────────


@router.get("")
async def list_passages(
    jlpt_level: str | None = Query(None, pattern=r"^N[1-5]$"),
    category: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
):
    """List reading passages with filtering and pagination."""
    return await get_passages(jlpt_level, category, page, per_page)


@router.get("/{passage_id}")
async def passage_detail(passage_id: int):
    """Get passage content with comprehension questions."""
    result = await get_passage_detail(passage_id)
    if not result:
        raise HTTPException(status_code=404, detail="Passage not found")
    return result


@router.post("/{passage_id}/submit")
async def submit_answers(passage_id: int, data: ReadingAnswersRequest):
    """Submit answers for a reading passage and get graded results."""
    result = await submit_reading_answers(passage_id, data.answers)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{passage_id}/vocab")
async def passage_vocab(passage_id: int):
    """Get vocabulary words found in the passage content."""
    result = await get_passage_vocab_highlights(passage_id)
    if not result:
        raise HTTPException(status_code=404, detail="Passage not found")
    return result


@router.post("/seed")
async def seed_reading():
    """Seed N5 reading passage data."""
    from app.database.jp_reading_seed import seed_reading_data

    count = await seed_reading_data()
    return {"message": f"Seeded {count} reading passages"}
