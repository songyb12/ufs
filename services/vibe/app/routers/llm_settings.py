"""LLM settings API — runtime toggle for LLM features."""

import logging

from fastapi import APIRouter

from app.config import settings
from app.database import repositories as repo

logger = logging.getLogger("vibe.settings")

router = APIRouter(prefix="/settings", tags=["settings"])

# LLM feature keys that can be toggled at runtime
LLM_TOGGLE_KEYS = {
    "LLM_RED_TEAM_ENABLED",
    "LLM_EXPLANATION_ENABLED",
    "LLM_SCENARIO_ENABLED",
}

# Read-only info keys (displayed but not editable via toggle)
LLM_INFO_KEYS = {
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_EXPLANATION_MODEL",
}


@router.get("/llm")
async def get_llm_settings():
    """Get current LLM feature settings."""
    return {
        "features": {
            "LLM_RED_TEAM_ENABLED": settings.LLM_RED_TEAM_ENABLED,
            "LLM_EXPLANATION_ENABLED": settings.LLM_EXPLANATION_ENABLED,
            "LLM_SCENARIO_ENABLED": settings.LLM_SCENARIO_ENABLED,
        },
        "config": {
            "LLM_PROVIDER": settings.LLM_PROVIDER,
            "LLM_MODEL": settings.LLM_MODEL,
            "LLM_EXPLANATION_MODEL": settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL,
            "LLM_API_KEY_SET": bool(settings.LLM_API_KEY),
        },
        "rule_based": {
            "RED_TEAM_ENABLED": settings.RED_TEAM_ENABLED,
            "EXPLANATION_ALWAYS_ENABLED": settings.EXPLANATION_ALWAYS_ENABLED,
            "PORTFOLIO_SCENARIOS_ENABLED": settings.PORTFOLIO_SCENARIOS_ENABLED,
        },
    }


@router.post("/llm")
async def update_llm_settings(updates: dict):
    """Toggle LLM feature flags at runtime.

    Accepts: { "LLM_RED_TEAM_ENABLED": true/false, ... }
    Only toggleable keys are accepted. Changes persist across restarts via DB.
    """
    applied = {}
    for key, value in updates.items():
        if key not in LLM_TOGGLE_KEYS:
            continue
        bool_val = bool(value)
        # Update in-memory settings
        setattr(settings, key, bool_val)
        # Persist to DB
        await repo.upsert_runtime_config(key, str(bool_val))
        applied[key] = bool_val
        logger.info("LLM setting updated: %s = %s", key, bool_val)

    return {
        "status": "ok",
        "applied": applied,
        "features": {
            "LLM_RED_TEAM_ENABLED": settings.LLM_RED_TEAM_ENABLED,
            "LLM_EXPLANATION_ENABLED": settings.LLM_EXPLANATION_ENABLED,
            "LLM_SCENARIO_ENABLED": settings.LLM_SCENARIO_ENABLED,
        },
    }


async def load_runtime_overrides():
    """Load runtime config from DB and apply to settings.

    Called at startup to restore persisted runtime overrides.
    """
    try:
        config = await repo.get_runtime_config()
        for key in LLM_TOGGLE_KEYS:
            if key in config:
                val = config[key].lower() in ("true", "1", "yes")
                setattr(settings, key, val)
                logger.info("Runtime override loaded: %s = %s", key, val)
    except Exception as e:
        logger.warning("Failed to load runtime config: %s", e)


# ── General runtime config (portfolio_total etc.) ──

ALLOWED_RUNTIME_KEYS = {"portfolio_total"}


@router.get("/runtime")
async def get_runtime_settings():
    """Get user-editable runtime settings."""
    config = await repo.get_runtime_config()
    return {
        "portfolio_total": float(config.get("portfolio_total", settings.PORTFOLIO_TOTAL)),
    }


@router.post("/runtime")
async def update_runtime_settings(updates: dict):
    """Update user-editable runtime settings."""
    applied = {}
    for key, value in updates.items():
        if key not in ALLOWED_RUNTIME_KEYS:
            continue
        # Validate portfolio_total is a reasonable positive number
        if key == "portfolio_total":
            try:
                num_val = float(value)
                if num_val <= 0 or num_val > 100_000_000_000:
                    logger.warning("Invalid portfolio_total value rejected: %s", value)
                    continue
            except (TypeError, ValueError):
                logger.warning("Non-numeric portfolio_total value rejected: %s", value)
                continue
        await repo.upsert_runtime_config(key, str(value))
        applied[key] = value
        logger.info("Runtime setting updated: %s = %s", key, value)
    return {"status": "ok", "applied": applied}
