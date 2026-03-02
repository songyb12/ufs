"""
Engineering-Ops - Work Automation Service

C-language HW verification log analysis & daily report generator.
"""

from datetime import datetime, timezone

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="UFS Engineering-Ops",
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
        "description": "HW Verification Log Analysis & Work Automation",
        "features": ["log-parser", "daily-report", "csv-export"],
        "version": settings.VERSION,
    }
