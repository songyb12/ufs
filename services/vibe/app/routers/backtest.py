"""Backtest API endpoints."""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.backtesting.engine import BacktestEngine
from app.backtesting.optimizer import ParameterOptimizer
from app.config import settings
from app.database import repositories as repo
from app.models.schemas import BacktestRequest, BacktestResultResponse, BacktestRunResponse

logger = logging.getLogger("vibe.routers.backtest")

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(request: BacktestRequest, bg: BackgroundTasks):
    """Trigger a backtest run. Runs asynchronously in background."""
    end = request.end_date or date.today().strftime("%Y-%m-%d")
    start = request.start_date or (
        date.today() - timedelta(days=settings.BACKTEST_DEFAULT_DAYS)
    ).strftime("%Y-%m-%d")

    logger.info("Backtest triggered (async): market=%s, period=%s to %s", request.market, start, end)
    engine = BacktestEngine(settings)

    async def _run():
        await engine.run(
            market=request.market.value if hasattr(request.market, "value") else request.market,
            start_date=start,
            end_date=end,
            config_overrides=request.config_overrides,
        )

    bg.add_task(_run)

    return BacktestRunResponse(
        backtest_id="pending",
        status="started",
        message=f"Backtest queued for {request.market} [{start} to {end}]",
    )


@router.post("/run/sync")
async def run_backtest_sync(request: BacktestRequest):
    """Trigger a backtest run and wait for results (synchronous)."""
    end = request.end_date or date.today().strftime("%Y-%m-%d")
    start = request.start_date or (
        date.today() - timedelta(days=settings.BACKTEST_DEFAULT_DAYS)
    ).strftime("%Y-%m-%d")

    logger.info("Backtest triggered (sync): market=%s, period=%s to %s", request.market, start, end)
    try:
        engine = BacktestEngine(settings)
        result = await engine.run(
            market=request.market.value if hasattr(request.market, "value") else request.market,
            start_date=start,
            end_date=end,
            config_overrides=request.config_overrides,
        )
        return result
    except Exception as e:
        logger.error("Sync backtest failed: market=%s, error=%s", request.market, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Backtest execution failed. Check server logs for details.")


@router.get("/results", response_model=list[BacktestResultResponse])
async def get_backtest_results(limit: int = 20):
    """List recent backtest runs."""
    import json as _json
    limit = min(max(limit, 1), 100)
    runs = await repo.get_backtest_runs(limit=limit)
    # Parse config_snapshot JSON for display
    for run in runs:
        cs = run.get("config_snapshot")
        if isinstance(cs, str):
            try:
                run["config_snapshot"] = _json.loads(cs)
            except (ValueError, TypeError):
                run["config_snapshot"] = None
    return runs


@router.get("/results/{backtest_id}")
async def get_backtest_detail(backtest_id: str):
    """Get detailed results for a specific backtest run."""
    run = await repo.get_backtest_run(backtest_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    trades = await repo.get_backtest_trades(backtest_id)
    return {
        "run": run,
        "trades": trades,
        "trades_count": len(trades),
    }


@router.post("/optimize")
async def run_optimization(request: BacktestRequest, bg: BackgroundTasks):
    """Trigger parameter optimization (grid search). Runs in background."""
    end = request.end_date or date.today().strftime("%Y-%m-%d")
    start = request.start_date or (
        date.today() - timedelta(days=settings.BACKTEST_DEFAULT_DAYS)
    ).strftime("%Y-%m-%d")

    optimizer = ParameterOptimizer(settings)

    async def _optimize():
        results = await optimizer.optimize(
            market=request.market.value if hasattr(request.market, "value") else request.market,
            start_date=start,
            end_date=end,
            param_grid=request.config_overrides,
        )
        return results

    bg.add_task(_optimize)

    return {
        "status": "optimization_started",
        "message": f"Grid search queued for {request.market} [{start} to {end}]",
    }
