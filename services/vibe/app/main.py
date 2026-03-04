"""
VIBE - Investment Intelligence Service

7-stage quant analysis engine with Hard Limit safety + Red-Team validation.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from app.collectors.registry import CollectorRegistry
from app.config import settings
from app.database.connection import set_db_path
from app.database.schema import init_db
from app.database.seed import seed_watchlist
from app.routers import backtest, dashboard, pipeline, portfolio, risk, screening, sentiment, signals, watchlist
from app.scheduler.jobs import register_jobs
from app.scheduler.runner import create_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("vibe")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    set_db_path(settings.DB_PATH)
    await init_db()
    logger.info("Database initialized: %s", settings.DB_PATH)

    seeded = await seed_watchlist()
    if seeded > 0:
        logger.info("Watchlist seeded with %d symbols", seeded)

    # Collector registry (shared across pipeline + scheduler)
    collector_registry = CollectorRegistry(settings)
    app.state.collector_registry = collector_registry

    # Scheduler
    if settings.SCHEDULER_ENABLED:
        scheduler = create_scheduler(settings)
        register_jobs(scheduler, settings, collector_registry)
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    else:
        app.state.scheduler = None
        logger.info("Scheduler disabled")

    yield

    # ── Shutdown ──
    if hasattr(app.state, "scheduler") and app.state.scheduler:
        app.state.scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")

    logger.info("VIBE service shutting down")


app = FastAPI(
    title="UFS VIBE",
    version=settings.VERSION,
    lifespan=lifespan,
)

# Register routers
app.include_router(watchlist.router)
app.include_router(pipeline.router)
app.include_router(signals.router)
app.include_router(dashboard.router)
app.include_router(backtest.router)
app.include_router(risk.router)
app.include_router(screening.router)
app.include_router(sentiment.router)
app.include_router(portfolio.router)


@app.get("/health")
async def health():
    from app.database import repositories as repo

    scheduler = getattr(app.state, "scheduler", None)
    now = datetime.now(timezone.utc)

    # DB connectivity check
    db_ok = False
    db_tables = 0
    try:
        from app.database.connection import get_db
        db = await get_db()
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            row = await cursor.fetchone()
            db_tables = row[0] if row else 0
            db_ok = db_tables > 0
        finally:
            await db.close()
    except Exception:
        db_ok = False

    # Last pipeline run freshness
    last_kr = await repo.get_latest_pipeline_run("KR")
    last_us = await repo.get_latest_pipeline_run("US")

    def _pipeline_info(run):
        if not run:
            return {"status": "never_run", "age_hours": None}
        completed = run.get("completed_at") or run.get("started_at")
        age = None
        if completed:
            try:
                run_time = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                if run_time.tzinfo is None:
                    run_time = run_time.replace(tzinfo=timezone.utc)
                age = round((now - run_time).total_seconds() / 3600, 1)
            except Exception:
                pass
        return {
            "status": run.get("status", "unknown"),
            "last_run": completed,
            "age_hours": age,
        }

    # Scheduler jobs
    scheduler_jobs = []
    if scheduler and scheduler.running:
        for job in scheduler.get_jobs():
            scheduler_jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })

    # Data freshness
    price_count = 0
    signal_count = 0
    try:
        from app.database.connection import get_db
        db = await get_db()
        try:
            c = await db.execute("SELECT COUNT(*) FROM price_history")
            price_count = (await c.fetchone())[0]
            c = await db.execute("SELECT COUNT(*) FROM signals")
            signal_count = (await c.fetchone())[0]
        finally:
            await db.close()
    except Exception:
        pass

    overall = "healthy" if db_ok else "degraded"

    return {
        "service": settings.SERVICE_NAME,
        "status": overall,
        "version": settings.VERSION,
        "timestamp": now.isoformat(),
        "database": {
            "connected": db_ok,
            "tables": db_tables,
            "prices": price_count,
            "signals": signal_count,
        },
        "scheduler": {
            "running": scheduler is not None and scheduler.running if scheduler else False,
            "jobs": scheduler_jobs,
        },
        "pipelines": {
            "KR": _pipeline_info(last_kr),
            "US": _pipeline_info(last_us),
        },
    }


@app.get("/")
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "description": "Investment Intelligence - 7-stage Quant Analysis Engine",
        "version": settings.VERSION,
        "hard_limits": {
            "rsi_ceiling": settings.RSI_HARD_LIMIT,
            "rsi_buy_kr": settings.RSI_BUY_THRESHOLD_KR,
            "rsi_buy_us": settings.RSI_BUY_THRESHOLD_US,
            "disparity_ceiling": settings.DISPARITY_HARD_LIMIT,
        },
        "endpoints": [
            "/health",
            "/watchlist",
            "/pipeline/run",
            "/pipeline/status",
            "/signals",
            "/signals/performance",
            "/dashboard",
            "/backtest/run",
            "/backtest/run/sync",
            "/backtest/results",
            "/backtest/optimize",
            "/risk/portfolio",
            "/risk/events",
            "/risk/events/seed",
            "/risk/sectors",
            "/screening/scan",
            "/screening/candidates",
            "/sentiment",
            "/sentiment/latest",
            "/portfolio",
            "/portfolio/position",
            "/portfolio/quick",
            "/portfolio/bulk",
            "/portfolio/seed",
            "/portfolio/scenarios",
            "/admin/backup",
        ],
    }


@app.post("/admin/backup")
async def trigger_backup():
    """Manually trigger a database backup."""
    from app.utils.backup import backup_database

    result = await backup_database(
        db_path=settings.DB_PATH,
        backup_dir=settings.DB_BACKUP_DIR,
        keep_days=settings.DB_BACKUP_KEEP_DAYS,
    )
    if result:
        import os
        size_mb = os.path.getsize(result) / (1024 * 1024)
        return {
            "status": "success",
            "backup_path": result,
            "size_mb": round(size_mb, 2),
        }
    return {"status": "failed", "error": "Backup creation failed"}
