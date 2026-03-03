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
from app.routers import dashboard, pipeline, signals, watchlist
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


@app.get("/health")
async def health():
    scheduler = getattr(app.state, "scheduler", None)
    return {
        "service": settings.SERVICE_NAME,
        "status": "healthy",
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scheduler_running": scheduler is not None and scheduler.running if scheduler else False,
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
            "/dashboard",
        ],
    }
