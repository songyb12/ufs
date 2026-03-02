"""
VIBE - Investment Intelligence Service

7-stage quant analysis engine with Hard Limit safety + Red-Team validation.
"""

from datetime import datetime, timezone

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="UFS VIBE",
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
        "description": "Investment Intelligence - 7-stage Quant Analysis Engine",
        "version": settings.VERSION,
        "hard_limits": {
            "rsi_ceiling": settings.RSI_HARD_LIMIT,
            "rsi_buy_kr": settings.RSI_BUY_THRESHOLD_KR,
            "rsi_buy_us": settings.RSI_BUY_THRESHOLD_US,
            "disparity_ceiling": settings.DISPARITY_HARD_LIMIT,
        },
    }


@app.get("/dashboard")
async def dashboard():
    """Daily dashboard endpoint (placeholder for VIBE pipeline)."""
    return {
        "dashboard": "VIBE DAILY DASHBOARD",
        "status": "pipeline_not_configured",
        "message": "Connect data sources to activate 7-stage analysis.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
