"""API routes — fully connected to engine, collector, and briefing layers."""

import json
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import create_access_token, get_current_user, verify_password
from app.briefing.generator import generate_briefing
from app.collector.macro import get_latest_macro
from app.collector.price import fetch_prices
from app.db import get_db, get_sync_db
from app.engine.signal import run_signal_pipeline
from app.models import (
    BriefingResponse,
    LoginRequest,
    SignalResult,
    TokenResponse,
)

logger = logging.getLogger("vibe2.routes")

router = APIRouter()

# Signal cache: avoid re-running pipeline within 5 minutes
_signal_cache: dict = {"result": None, "timestamp": 0.0}
SIGNAL_CACHE_TTL = 300  # 5 minutes


# ── Auth ──


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(body: LoginRequest):
    """Authenticate and return JWT token."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT username, password_hash FROM users WHERE username = ?",
        (body.username,),
    )
    user = await cursor.fetchone()
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, expires_in = create_access_token(body.username)

    await db.execute(
        "UPDATE users SET last_login = datetime('now') WHERE username = ?",
        (body.username,),
    )
    await db.commit()

    return TokenResponse(token=token, username=body.username, expires_in=expires_in)


# ── Signal ──


def _get_cached_or_db_signal() -> SignalResult | None:
    """Return cached signal if fresh, or latest from DB."""
    now = time.time()

    # Check in-memory cache
    if _signal_cache["result"] and (now - _signal_cache["timestamp"]) < SIGNAL_CACHE_TTL:
        return _signal_cache["result"]

    # Check DB for recent signal
    conn = get_sync_db()
    try:
        cursor = conn.execute(
            "SELECT signal_level, score, summary, details_json, action, risks_json, created_at "
            "FROM signals ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            created_str = row["created_at"]
            try:
                created_dt = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
                age_seconds = (datetime.now() - created_dt).total_seconds()
                if age_seconds < SIGNAL_CACHE_TTL:
                    result = SignalResult(
                        signal=row["signal_level"],
                        score=row["score"],
                        summary=row["summary"] or "",
                        details=json.loads(row["details_json"]) if row["details_json"] else {},
                        action=row["action"] or "",
                        risks=json.loads(row["risks_json"]) if row["risks_json"] else [],
                    )
                    _signal_cache["result"] = result
                    _signal_cache["timestamp"] = now
                    return result
            except (ValueError, TypeError):
                pass
    finally:
        conn.close()

    return None


@router.get("/signal/current", response_model=SignalResult, tags=["signal"])
async def get_current_signal(user: str = Depends(get_current_user)):
    """Get the latest computed signal. Cached for 5 minutes."""
    cached = _get_cached_or_db_signal()
    if cached:
        return cached

    # Run pipeline
    result = run_signal_pipeline()
    _signal_cache["result"] = result
    _signal_cache["timestamp"] = time.time()
    return result


# ── Briefing ──


def _get_latest_briefing_from_db() -> dict | None:
    """Get latest briefing row from DB."""
    conn = get_sync_db()
    try:
        cursor = conn.execute(
            "SELECT briefing_date, signal_level, score, commentary, full_json, created_at "
            "FROM briefings ORDER BY id DESC LIMIT 1"
        )
        return dict(cursor.fetchone()) if cursor.fetchone() is not None else None
    finally:
        conn.close()


def _row_to_briefing_response(row: dict) -> BriefingResponse:
    """Convert a DB row dict to BriefingResponse."""
    full = json.loads(row["full_json"]) if row.get("full_json") else {}
    signal_data = full.get("signal", {})

    signal = SignalResult(
        signal=signal_data.get("signal", row.get("signal_level", "YELLOW")),
        score=signal_data.get("score", row.get("score", 0)),
        summary=signal_data.get("summary", ""),
        details=signal_data.get("details", {}),
        action=signal_data.get("action", ""),
        risks=signal_data.get("risks", []),
    )

    return BriefingResponse(
        date=row["briefing_date"],
        signal=signal,
        commentary=row.get("commentary") or full.get("commentary"),
        generated_at=row.get("created_at"),
    )


@router.get("/briefing/latest", response_model=BriefingResponse, tags=["briefing"])
async def get_latest_briefing(user: str = Depends(get_current_user)):
    """Get the most recent daily briefing. Generates one if none exists."""
    conn = get_sync_db()
    try:
        cursor = conn.execute(
            "SELECT briefing_date, signal_level, score, commentary, full_json, created_at "
            "FROM briefings ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return _row_to_briefing_response(dict(row))
    finally:
        conn.close()

    # No briefing exists — generate one
    signal = run_signal_pipeline()
    briefing = generate_briefing(signal)
    return briefing


@router.get("/briefing/history", tags=["briefing"])
async def get_briefing_history(
    days: int = Query(default=30, ge=1, le=365),
    user: str = Depends(get_current_user),
):
    """Get briefing history for the past N days."""
    conn = get_sync_db()
    try:
        cursor = conn.execute(
            "SELECT briefing_date, signal_level, score, commentary, full_json, created_at "
            "FROM briefings ORDER BY id DESC LIMIT ?",
            (days,),
        )
        rows = cursor.fetchall()
        return [_row_to_briefing_response(dict(r)) for r in rows]
    finally:
        conn.close()


@router.post("/briefing/refresh", response_model=BriefingResponse, tags=["briefing"])
async def refresh_briefing(user: str = Depends(get_current_user)):
    """Force pipeline + briefing regeneration, ignoring cache."""
    # Invalidate cache
    _signal_cache["result"] = None
    _signal_cache["timestamp"] = 0.0

    signal = run_signal_pipeline()
    briefing = generate_briefing(signal)
    return briefing


# ── Data ──


@router.get("/data/price", tags=["data"])
async def get_price_data(
    symbol: str = Query(default="SOXL"),
    days: int = Query(default=90, ge=1, le=365),
    user: str = Depends(get_current_user),
):
    """Get price history for a symbol via yfinance."""
    df = fetch_prices(symbol, days=days)
    if df is None or df.empty:
        return {"symbol": symbol, "days": days, "prices": [], "count": 0}

    prices = []
    for date_idx, row in df.iterrows():
        prices.append({
            "date": str(date_idx)[:10],
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"]),
        })
    return {"symbol": symbol, "days": days, "prices": prices, "count": len(prices)}


@router.get("/data/macro", tags=["data"])
async def get_macro_data(user: str = Depends(get_current_user)):
    """Get latest macro indicators."""
    macro = get_latest_macro()
    if macro is None:
        return {"data": None, "message": "No macro data available"}
    # Convert Row to plain dict
    return {"data": dict(macro)}
