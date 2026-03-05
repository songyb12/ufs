"""Alert configuration and history API endpoints."""

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.database import repositories as repo

logger = logging.getLogger("vibe.routers.alerts")

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertConfigUpdate(BaseModel):
    key: str
    value: str
    description: str | None = None


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
