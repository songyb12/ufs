"""Japanese learning analytics router — weakness, learning curve, forecast, mastery, streak."""

import logging

from fastapi import APIRouter, Query

from app.services.analytics_service import (
    get_learning_curve,
    get_mastery_breakdown,
    get_srs_forecast,
    get_streak_info,
    get_weakness_analysis,
)

logger = logging.getLogger("life-master.analytics-router")

router = APIRouter(prefix="/japanese/analytics", tags=["japanese-analytics"])


@router.get("/weakness")
async def weakness():
    """Analyze weak areas across vocab, grammar, kanji, reading."""
    return await get_weakness_analysis()


@router.get("/learning-curve")
async def learning_curve(days: int = Query(30, ge=1, le=365)):
    """Daily learning activity over the past N days."""
    return await get_learning_curve(days)


@router.get("/srs-forecast")
async def srs_forecast(days: int = Query(14, ge=1, le=90)):
    """Forecast upcoming SRS review load."""
    return await get_srs_forecast(days)


@router.get("/mastery")
async def mastery():
    """Mastery distribution per JLPT level."""
    return await get_mastery_breakdown()


@router.get("/streak")
async def streak():
    """Study streak information."""
    return await get_streak_info()
