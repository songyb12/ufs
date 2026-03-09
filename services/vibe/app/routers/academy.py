"""Market Academy Router — /academy endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from app.database import repositories as repo
from app.indicators.market_academy import (
    find_matching_patterns,
    generate_todays_lesson,
    get_all_concepts,
    get_concept_detail,
)

logger = logging.getLogger("vibe.routers.academy")

router = APIRouter(prefix="/academy", tags=["academy"])


async def _get_macro_and_sentiment() -> tuple[dict, dict | None]:
    """Fetch latest macro and sentiment data."""
    macro = await repo.get_latest_macro() or {}
    sentiment = await repo.get_latest_sentiment()
    return macro, sentiment


@router.get("/today")
async def get_todays_lesson():
    """Get today's most relevant educational concept based on current market."""
    try:
        macro, sentiment = await _get_macro_and_sentiment()
        lesson = generate_todays_lesson(macro, sentiment)

        # Also find matching historical patterns
        patterns = find_matching_patterns(macro, sentiment)

        return {
            "lesson": lesson,
            "historical_patterns": patterns[:3],  # Top 3 matches
            "market_snapshot": {
                "vix": macro.get("vix"),
                "fear_greed": (sentiment or {}).get("fear_greed_index"),
                "yield_spread": macro.get("us_yield_spread"),
                "wti": macro.get("wti_crude"),
            },
        }
    except Exception as e:
        logger.error("Today's lesson failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Today's lesson generation failed. Check server logs for details.")


@router.get("/concepts")
async def get_concept_catalog():
    """Get all educational concepts grouped by category."""
    try:
        return {"categories": get_all_concepts()}
    except Exception as e:
        logger.error("Concept catalog failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Concept catalog generation failed.")


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """Get detailed concept with current market annotation."""
    try:
        macro, _ = await _get_macro_and_sentiment()
        detail = get_concept_detail(concept_id, macro)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Concept detail failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Concept detail generation failed.")


@router.get("/patterns")
async def get_historical_patterns():
    """Find historical patterns matching current market conditions."""
    try:
        macro, sentiment = await _get_macro_and_sentiment()
        patterns = find_matching_patterns(macro, sentiment)
        return {
            "patterns": patterns,
            "current_conditions": {
                "vix": macro.get("vix"),
                "fear_greed": (sentiment or {}).get("fear_greed_index"),
                "yield_spread": macro.get("us_yield_spread"),
            },
        }
    except Exception as e:
        logger.error("Pattern matching failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Pattern matching failed.")
