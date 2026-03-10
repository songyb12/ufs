"""
Life-Master - Intelligent Routine & Schedule Optimizer

Full-system backend: routines, habits, goals, dynamic scheduler.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.connection import close_db, set_db_path
from app.database.schema import init_db
from app.routers import goals, habits, routines, scheduler


def _setup_logging() -> None:
    log_level = getattr(
        logging,
        os.environ.get("LOG_LEVEL", "DEBUG" if settings.DEBUG else settings.LOG_LEVEL).upper(),
        logging.INFO,
    )
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )


_setup_logging()
logger = logging.getLogger("life-master")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Life-Master v%s", settings.VERSION)
    set_db_path(settings.DB_PATH)
    await init_db()
    logger.info("Database initialized: %s", settings.DB_PATH)
    yield
    await close_db()
    logger.info("Life-Master shutdown complete")


app = FastAPI(
    title="UFS Life-Master",
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    f"http://localhost:{settings.SERVICE_PORT}",
]
if settings.CORS_EXTRA_ORIGINS:
    origins.extend(settings.CORS_EXTRA_ORIGINS.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Routers
app.include_router(routines.router)
app.include_router(habits.router)
app.include_router(goals.router)
app.include_router(scheduler.router)


@app.get("/health")
async def health():
    db_ok = True
    try:
        from app.database.connection import get_db
        db = await get_db()
        await db.execute("SELECT 1")
    except Exception:
        db_ok = False
    return {
        "service": settings.SERVICE_NAME,
        "status": "healthy" if db_ok else "degraded",
        "version": settings.VERSION,
        "db_connected": db_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "description": "Intelligent Routine & Schedule Optimizer",
        "version": settings.VERSION,
        "features": [
            "routine-manager",
            "habit-tracker",
            "goal-system",
            "dynamic-scheduler",
            "heatmaps",
            "templates",
            "export-import",
        ],
        "endpoints": {
            "routines": "/routines",
            "habits": "/habits",
            "goals": "/goals",
            "schedule": "/schedule",
            "dashboard": "/dashboard",
            "search": "/search",
            "report_weekly": "/report/weekly",
            "report_monthly": "/report/monthly",
            "export": "/export",
            "admin": "/admin",
            "docs": "/docs",
        },
    }


@app.get("/dashboard")
async def dashboard(date: str | None = None):
    """Today's (or specified date's) overview at a glance."""
    from app.database import repositories as repo
    from app.services.streak import calculate_streak
    from app.utils.time_helpers import today_day_name, today_str

    DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    if date:
        from datetime import date as d
        target = date
        day_name = DAY_NAMES[d.fromisoformat(date).weekday()]
    else:
        target = today_str()
        day_name = today_day_name()

    data = await repo.get_dashboard_data(target, day_name)

    habits_list = await repo.get_habits(active_only=True)
    streaks = []
    for h in habits_list:
        logs = await repo.get_habit_logs(h["id"])
        s = calculate_streak(logs, h.get("target_value", 1))
        if s["current_streak"] > 0:
            streaks.append({"name": h["name"], "streak": s["current_streak"]})
    streaks.sort(key=lambda x: -x["streak"])
    data["top_streaks"] = streaks[:5]
    return data


@app.get("/search")
async def global_search(q: str = Query(min_length=1)):
    """Search across routines, habits, and goals."""
    from app.database import repositories as repo
    return await repo.global_search(q)


@app.get("/report/weekly")
async def weekly_report(date: str | None = None):
    """Weekly summary report."""
    from app.database import repositories as repo
    from app.utils.time_helpers import week_range
    start, end = week_range(date)
    return await repo.get_weekly_report(start, end)


@app.get("/report/monthly")
async def monthly_report(year: int, month: int):
    """Monthly summary report."""
    from app.database import repositories as repo
    return await repo.get_monthly_report(year, month)


@app.get("/export")
async def export_data():
    """Export all data as JSON."""
    from app.database import repositories as repo
    data = await repo.export_all()
    data["version"] = settings.VERSION
    return data


@app.post("/admin/retention")
async def run_retention():
    """Clean up old logs beyond retention period."""
    from app.database import repositories as repo
    result = await repo.cleanup_old_logs(settings.RETENTION_LOG_DAYS)
    logger.info("Retention cleanup: %s", result)
    return result


@app.get("/admin/db-info")
async def db_info():
    """Database statistics and info."""
    from app.database import repositories as repo
    info = await repo.get_db_info()
    info["db_path"] = settings.DB_PATH
    return info


@app.get("/version")
async def version():
    return {"service": settings.SERVICE_NAME, "version": settings.VERSION}
