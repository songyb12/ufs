"""
Lab-Studio - Creative & Learning Service

Sub-modules: Bocchi-master (guitar/bass practice platform)
Tech: React frontend (separate build) + FastAPI backend
"""

from datetime import datetime, timezone

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="UFS Lab-Studio",
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
        "description": "Creative & Learning Studio",
        "modules": ["bocchi-master"],
        "version": settings.VERSION,
    }
