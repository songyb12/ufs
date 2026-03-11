"""Market briefing API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import repositories as repo

logger = logging.getLogger("vibe.routers.briefing")

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
        raise HTTPException(status_code=404, detail="No briefing available yet. Run pipeline or generate manually.")
    return briefings[0]


@router.get("/{briefing_date}")
async def get_briefing_by_date(briefing_date: str, market: str = Query("ALL")):
    """Get a market briefing for a specific date."""
    briefing = await repo.get_market_briefing(briefing_date, market)
    if not briefing:
        raise HTTPException(status_code=404, detail=f"No briefing for {briefing_date}")
    return briefing


@router.post("/generate")
async def generate_briefing_endpoint(target_date: str | None = None):
    """Manually trigger market briefing generation."""
    from app.briefing.market_briefing import generate_market_briefing

    logger.info("Briefing generation requested: target_date=%s", target_date)
    try:
        content = await generate_market_briefing(target_date)
        return {"status": "ok", "briefing": content}
    except Exception as e:
        logger.error("Briefing generation failed: target_date=%s, error=%s", target_date, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Briefing generation failed. Check server logs for details.")


class RagQueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500, description="Natural language question about VIBE data")


@router.post("/query")
async def rag_query_endpoint(req: RagQueryRequest):
    """SQL-RAG: Ask natural language questions about VIBE data.

    Converts questions to SQL, executes safely, and returns synthesized Korean answers.
    Example: "삼성전자 최근 RSI 추이는?" or "BUY 시그널이 가장 많은 종목은?"
    """
    from app.briefing.rag_query import rag_query

    logger.info("RAG query requested: %s", req.question[:80])
    try:
        result = await rag_query(req.question)
        return result
    except Exception as e:
        logger.error("RAG query failed: error=%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="RAG query failed. Check server logs.")


class AgentReviewRequest(BaseModel):
    request: str = Field(default="포트폴리오를 종합 리뷰해주세요.", max_length=500)
    portfolio_id: int = 1


@router.post("/agent-review")
async def agent_portfolio_review(req: AgentReviewRequest):
    """Agentic portfolio review: LLM autonomously gathers data and writes a review.

    The agent iterates up to 5 times, calling tools to fetch portfolio positions,
    signals, macro data, and more, then synthesizes a comprehensive Korean report.
    """
    from app.briefing.agent_review import run_portfolio_review

    logger.info("Agent review requested: %s", req.request[:80])
    try:
        result = await run_portfolio_review(
            request=req.request,
            portfolio_id=req.portfolio_id,
        )
        return result
    except Exception as e:
        logger.error("Agent review failed: error=%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Agent review failed. Check server logs.")


class AnalyzeRequest(BaseModel):
    question: str = Field(default="오늘의 시장 상황을 종합 분석해주세요.", max_length=1000)
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

    logger.info("AI analysis requested: question=%s, markets=%s", req.question[:50], req.markets)
    try:
        result = await run_ai_analysis(
            question=req.question,
            markets=req.markets,
            include_portfolio=req.include_portfolio,
            portfolio_id=req.portfolio_id,
        )
        return result
    except Exception as e:
        logger.error("AI analysis failed: error=%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="AI analysis failed. Check server logs for details.")
