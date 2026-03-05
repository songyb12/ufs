"""Market briefing API endpoints."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.database import repositories as repo

router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.get("")
async def get_briefings(limit: int = Query(10, ge=1, le=30)):
    """Get recent market briefings."""
    briefings = await repo.get_market_briefings(limit=limit)
    return {"briefings": briefings, "count": len(briefings)}


@router.get("/latest")
async def get_latest_briefing():
    """Get the most recent market briefing."""
    briefings = await repo.get_market_briefings(limit=1)
    if not briefings:
        return {"status": "not_generated", "message": "No briefing available yet. Run pipeline or generate manually."}
    return briefings[0]


@router.get("/{briefing_date}")
async def get_briefing_by_date(briefing_date: str, market: str = Query("ALL")):
    """Get a market briefing for a specific date."""
    briefing = await repo.get_market_briefing(briefing_date, market)
    if not briefing:
        return {"status": "not_found", "message": f"No briefing for {briefing_date}"}
    return briefing


@router.post("/generate")
async def generate_briefing_endpoint(target_date: str | None = None):
    """Manually trigger market briefing generation."""
    from app.briefing.market_briefing import generate_market_briefing

    content = await generate_market_briefing(target_date)
    return {"status": "ok", "briefing": content}


class AnalyzeRequest(BaseModel):
    question: str = "오늘의 시장 상황을 종합 분석해주세요."
    markets: list[str] | None = None
    include_portfolio: bool = True
    portfolio_id: int = 1


@router.post("/analyze")
async def ai_analyze(req: AnalyzeRequest):
    """AI-powered market analysis using VIBE database context.

    Gathers real-time data (macro, sentiment, signals, portfolio)
    and sends to LLM for comprehensive Korean market commentary.
    """
    from app.briefing.ai_analysis import run_ai_analysis

    result = await run_ai_analysis(
        question=req.question,
        markets=req.markets,
        include_portfolio=req.include_portfolio,
        portfolio_id=req.portfolio_id,
    )
    return result
