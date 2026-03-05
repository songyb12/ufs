import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from app.collectors.registry import CollectorRegistry
from app.config import settings
from app.database import repositories as repo
from app.models.schemas import PipelineRunDetail, PipelineRunRequest, PipelineRunResponse
from app.notifier.discord import DiscordNotifier
from app.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger("vibe.routers.pipeline")

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run")
async def run_pipeline(request: PipelineRunRequest, req: Request):
    """Manually trigger a pipeline run."""
    collector_registry: CollectorRegistry = req.app.state.collector_registry

    markets = []
    if request.market == "ALL":
        markets = ["KR", "US"]
    else:
        markets = [request.market.upper()]

    results = []
    orchestrator = PipelineOrchestrator(settings, collector_registry)
    notifier = DiscordNotifier(settings)

    for market in markets:
        symbols = await repo.get_active_symbols(market)
        if not symbols:
            results.append({
                "market": market,
                "status": "skipped",
                "message": f"No active symbols for {market}",
            })
            continue

        try:
            context = await orchestrator.run(
                market=market,
                symbols=symbols,
                run_type="manual",
            )

            # Send Discord dashboard
            discord_sent = False
            if context.get("status") == "completed":
                discord_sent = await notifier.send_dashboard(context)

            results.append({
                "run_id": context["run_id"],
                "market": market,
                "status": context.get("status", "unknown"),
                "symbols_analyzed": len(symbols),
                "elapsed": context.get("elapsed", 0),
                "discord_sent": discord_sent,
            })

        except Exception as e:
            logger.exception("Pipeline run failed for %s: %s", market, e)
            results.append({
                "market": market,
                "status": "failed",
                "error": str(e),
            })

    return {"results": results}


@router.get("/status")
async def pipeline_status():
    """Get status of the most recent pipeline run."""
    run = await repo.get_latest_pipeline_run()
    if not run:
        return {"status": "no_runs", "message": "No pipeline runs recorded yet."}
    return run


@router.get("/runs", response_model=list[PipelineRunDetail])
async def list_runs(limit: int = 20):
    """List past pipeline runs."""
    limit = min(max(limit, 1), 100)
    return await repo.get_pipeline_runs(limit=limit)
