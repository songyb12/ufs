"""VIBE 2.0 — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close_db, init_db
from app.routes import router
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("vibe2")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("VIBE 2.0 starting up")
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()
    await close_db()
    logger.info("VIBE 2.0 shut down")


app = FastAPI(
    title="VIBE 2.0",
    description="SOXL-focused investment intelligence briefing engine",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "vibe2", "version": "2.0.0"}
