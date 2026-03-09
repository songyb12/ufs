"""Alert configuration and history API endpoints."""

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.database import repositories as repo

logger = logging.getLogger("vibe.routers.alerts")

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertConfigUpdate(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    value: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=200)


@router.get("/config")
async def get_alert_config():
    """Get all alert configuration entries."""
    config = await repo.get_alert_config()
    return {"config": config}


@router.post("/config")
async def update_alert_config(updates: list[AlertConfigUpdate]):
    """Update alert configuration entries."""
    for u in updates:
        await repo.upsert_alert_config(u.key, u.value, u.description)
        logger.info("Alert config updated: %s = %s", u.key, u.value)
    return {"status": "ok", "updated": len(updates)}


@router.get("/history")
async def get_alert_history(limit: int = Query(50, ge=1, le=200)):
    """Get recent alert history."""
    history = await repo.get_alert_history(limit=limit)
    return {"history": history, "count": len(history)}
