"""
Lab-Studio - Creative & Learning Service

Sub-modules: Bocchi-master (guitar/bass practice platform)
Tech: React frontend (separate build) + FastAPI backend
"""

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("lab-studio")

app = FastAPI(
    title="UFS Lab-Studio",
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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
