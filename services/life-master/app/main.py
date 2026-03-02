"""
Life-Master - Routine Scheduler Service

Intelligent task & routine management with dynamic schedule optimization.
"""

from datetime import datetime, timezone

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="UFS Life-Master",
    version=settings.VERSION,
)


@app.get("/health")
async def health():
    return {
        "service": settings.SERVICE_NAME,
        "status": "healthy",
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "description": "Intelligent Routine & Schedule Optimizer",
        "features": ["routine-manager", "dynamic-scheduler"],
        "version": settings.VERSION,
    }
