"""
SOXL Real-time Analysis Endpoints.

Provides live price, intraday charts, real-time indicators,
sector correlation, SSE streaming, and price alerts.
Data source: Finnhub.io (quote) + yfinance (candles, fallback).
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/soxl/live", tags=["soxl-live"])
logger = logging.getLogger("vibe.soxl_live")

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

SECTOR_ETFS = ["SOXX", "SMH", "QQQ", "SPY"]

# Thread pool for sync yfinance calls
_yf_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="yfinance")

# Simple TTL cache for yfinance intraday data
_yf_cache: dict[str, tuple[float, list]] = {}  # key -> (expires_at, data)
_YF_INTRADAY_TTL = 30.0  # 30 seconds


def _get_finnhub(request: Request):
    """Get Finnhub client from app state."""
    client = getattr(request.app.state, "finnhub", None)
    if not client:
        raise HTTPException(503, detail="Finnhub client not configured. Set FINNHUB_API_KEY in .env")
    return client


# ── Models ──

class SoxlAlertCreate(BaseModel):
    alert_type: str  # 'price_above', 'price_below', 'change_pct'
    threshold: float
    label: str = ""


# ── Endpoint 1: GET /soxl/live/quote ──

@router.get("/quote")
async def soxl_live_quote(request: Request):
    """Current SOXL price + market status."""
    fh = _get_finnhub(request)
    quote = await fh.get_quote("SOXL")

    return {
        "price": quote.get("c", 0),
        "change": quote.get("d", 0),
        "change_pct": quote.get("dp", 0),
        "high": quote.get("h", 0),
        "low": quote.get("l", 0),
        "open": quote.get("o", 0),
        "prev_close": quote.get("pc", 0),
        "volume": 0,  # quote endpoint doesn't return volume
        "market_open": fh.is_market_open(),
        "session": fh.get_market_session(),
        "market_session": fh.get_market_session(),  # backward compat
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ── yfinance intraday helper ──

async def _yfinance_intraday(symbol: str, resolution: str) -> list[dict]:
    """Fetch intraday candles from yfinance (sync, run in thread pool)."""
    cache_key = f"yf_intraday:{symbol}:{resolution}"
    cached = _yf_cache.get(cache_key)
    if cached and time.monotonic() < cached[0]:
        return cached[1]

    loop = asyncio.get_running_loop()

    def _fetch():
        import yfinance as yf
        interval = f"{resolution}m"
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval=interval)
        if df.empty:
            return []
        candles = []
        for ts, row in df.iterrows():
            candles.append({
                "time": int(ts.timestamp()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return candles

    try:
        candles = await loop.run_in_executor(_yf_executor, _fetch)
        _yf_cache[cache_key] = (time.monotonic() + _YF_INTRADAY_TTL, candles)
        logger.info("yfinance intraday fetched: %s %sm → %d candles", symbol, resolution, len(candles))
        return candles
    except Exception as e:
        logger.warning("yfinance intraday failed for %s: %s", symbol, e)
        return []


# ── Endpoint 2: GET /soxl/live/intraday ──

@router.get("/intraday")
async def soxl_intraday(
    request: Request,
    resolution: str = Query("1", pattern="^(1|5)$"),
    count: int = Query(390, ge=10, le=780),
):
    """Intraday candlestick data for SOXL.
    Tries Finnhub first, falls back to yfinance for ETFs.
    """
    fh = _get_finnhub(request)

    # Calculate time range: today's market session
    now_et = datetime.now(ET)
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)

    # If before market open, get previous trading day
    if now_et < market_open:
        market_open -= timedelta(days=1)
        while market_open.weekday() >= 5:
            market_open -= timedelta(days=1)

    from_ts = int(market_open.timestamp())
    to_ts = int(now_et.timestamp())

    # Try Finnhub first
    candles = await fh.get_candles("SOXL", resolution, from_ts, to_ts)

    # Fallback to yfinance if Finnhub returns empty (free tier ETF limitation)
    source = "finnhub"
    if not candles:
        candles = await _yfinance_intraday("SOXL", resolution)
        source = "yfinance"

    # Limit to requested count (most recent)
    if len(candles) > count:
        candles = candles[-count:]

    return {
        "candles": candles,
        "resolution": resolution,
        "count": len(candles),
        "market_open": fh.is_market_open(),
        "source": source,
        "from_ts": from_ts,
        "to_ts": to_ts,
    }


# ── Endpoint 3: GET /soxl/live/indicators ──

@router.get("/indicators")
async def soxl_live_indicators(request: Request):
    """Real-time technical indicators computed from daily + intraday data."""
    fh = _get_finnhub(request)

    # 1. Get last 60 daily closes from DB
    from app.database.connection import get_db
    db = await get_db()

    cursor = await db.execute(
        """SELECT close, volume FROM price_history
           WHERE symbol='SOXL' AND market='US'
           ORDER BY trade_date DESC LIMIT 60"""
    )
    rows = await cursor.fetchall()
    if not rows:
        raise HTTPException(404, detail="No historical SOXL data in DB")

    daily_closes = [r[0] for r in reversed(rows)]
    daily_volumes = [r[1] or 0 for r in reversed(rows)]

    # 2. Get today's latest price from Finnhub
    quote = await fh.get_quote("SOXL")
    current_price = quote.get("c", 0)
    if current_price > 0:
        daily_closes.append(current_price)

    # 3. Compute indicators using numpy
    closes = np.array(daily_closes, dtype=float)

    # RSI-14
    rsi_14 = _compute_rsi(closes, 14)

    # MACD (12, 26, 9)
    macd_line, signal_line, histogram = _compute_macd(closes)

    # Bollinger Bands (20, 2)
    bb_upper, bb_middle, bb_lower = _compute_bollinger(closes, 20, 2)

    # Moving Averages
    ma_5 = float(np.mean(closes[-5:])) if len(closes) >= 5 else None
    ma_20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else None
    ma_60 = float(np.mean(closes[-60:])) if len(closes) >= 60 else None

    # VWAP (from intraday candles: Finnhub → yfinance fallback)
    vwap = None
    try:
        now_et = datetime.now(ET)
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        if now_et >= market_open and fh.is_market_open():
            from_ts = int(market_open.timestamp())
            to_ts = int(now_et.timestamp())
            intraday = await fh.get_candles("SOXL", "5", from_ts, to_ts)
            if not intraday:
                intraday = await _yfinance_intraday("SOXL", "5")
            if intraday:
                total_pv = sum(c["close"] * c["volume"] for c in intraday if c["volume"])
                total_v = sum(c["volume"] for c in intraday if c["volume"])
                vwap = round(total_pv / total_v, 2) if total_v > 0 else None
    except Exception as e:
        logger.debug("VWAP calculation failed: %s", e)

    # Volume ratio
    vol_ratio = None
    if daily_volumes and len(daily_volumes) >= 20:
        avg_vol = np.mean(daily_volumes[-20:])
        if avg_vol > 0 and quote.get("c"):
            # Use last known daily volume as proxy
            vol_ratio = round(daily_volumes[-1] / avg_vol, 2)

    return {
        "price": current_price,
        "rsi_14": round(rsi_14, 1) if rsi_14 else None,
        "macd": round(macd_line, 4) if macd_line is not None else None,
        "macd_signal": round(signal_line, 4) if signal_line is not None else None,
        "macd_histogram": round(histogram, 4) if histogram is not None else None,
        "bb_upper": round(bb_upper, 2) if bb_upper is not None else None,
        "bb_middle": round(bb_middle, 2) if bb_middle is not None else None,
        "bb_lower": round(bb_lower, 2) if bb_lower is not None else None,
        "ma_5": round(ma_5, 2) if ma_5 else None,
        "ma_20": round(ma_20, 2) if ma_20 else None,
        "ma_60": round(ma_60, 2) if ma_60 else None,
        "vwap": vwap,
        "volume_ratio": vol_ratio,
        "computed_at": datetime.now(UTC).isoformat(),
    }


# ── Daily correlation helper ──

_corr_cache: dict[str, tuple[float, dict]] = {}
_CORR_CACHE_TTL = 3600.0  # 1 hour (daily data, rarely changes)


async def _compute_daily_correlations(days: int = 60) -> dict[str, float]:
    """Compute 60-day daily return correlations: SOXL vs sector ETFs.
    Uses DB for available symbols + yfinance fallback for missing ones.
    """
    cache_key = f"daily_corr:{days}"
    cached = _corr_cache.get(cache_key)
    if cached and time.monotonic() < cached[0]:
        return cached[1]

    from app.database.connection import get_db
    db = await get_db()

    # Get SOXL daily closes from DB
    cursor = await db.execute(
        """SELECT trade_date, close FROM price_history
           WHERE symbol='SOXL' AND market='US'
           ORDER BY trade_date DESC LIMIT ?""",
        (days,),
    )
    soxl_rows = await cursor.fetchall()
    if len(soxl_rows) < 20:
        return {}

    soxl_dates = [r[0] for r in reversed(soxl_rows)]
    soxl_closes = np.array([r[1] for r in reversed(soxl_rows)], dtype=float)
    soxl_returns = np.diff(soxl_closes) / soxl_closes[:-1]

    correlations = {}
    for sym in SECTOR_ETFS:
        try:
            # Try DB first
            cursor = await db.execute(
                """SELECT trade_date, close FROM price_history
                   WHERE symbol=? AND market='US'
                   ORDER BY trade_date DESC LIMIT ?""",
                (sym, days),
            )
            rows = await cursor.fetchall()

            if len(rows) >= 20:
                # DB data available — align dates
                sym_map = {r[0]: r[1] for r in rows}
                aligned_soxl = []
                aligned_sym = []
                for i, d in enumerate(soxl_dates):
                    if d in sym_map:
                        aligned_soxl.append(soxl_closes[i])
                        aligned_sym.append(sym_map[d])

                if len(aligned_soxl) >= 20:
                    arr_soxl = np.array(aligned_soxl, dtype=float)
                    arr_sym = np.array(aligned_sym, dtype=float)
                    ret_soxl = np.diff(arr_soxl) / arr_soxl[:-1]
                    ret_sym = np.diff(arr_sym) / arr_sym[:-1]
                    corr = float(np.corrcoef(ret_soxl, ret_sym)[0, 1])
                    correlations[sym] = round(corr, 3)
                    continue

            # Fallback to yfinance for symbols not in DB (SOXX, SMH)
            loop = asyncio.get_running_loop()

            def _fetch_yf(symbol=sym):
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="3mo")
                if df.empty:
                    return []
                return [(row.name.strftime("%Y-%m-%d"), float(row["Close"]))
                        for _, row in df.iterrows()]

            yf_data = await loop.run_in_executor(_yf_executor, _fetch_yf)
            if len(yf_data) >= 20:
                sym_map = {d: c for d, c in yf_data}
                aligned_soxl = []
                aligned_sym = []
                for i, d in enumerate(soxl_dates):
                    if d in sym_map:
                        aligned_soxl.append(soxl_closes[i])
                        aligned_sym.append(sym_map[d])

                if len(aligned_soxl) >= 20:
                    arr_soxl = np.array(aligned_soxl, dtype=float)
                    arr_sym = np.array(aligned_sym, dtype=float)
                    ret_soxl = np.diff(arr_soxl) / arr_soxl[:-1]
                    ret_sym = np.diff(arr_sym) / arr_sym[:-1]
                    corr = float(np.corrcoef(ret_soxl, ret_sym)[0, 1])
                    correlations[sym] = round(corr, 3)
        except Exception as e:
            logger.debug("Correlation calc failed for %s: %s", sym, e)

    _corr_cache[cache_key] = (time.monotonic() + _CORR_CACHE_TTL, correlations)
    logger.info("Daily correlations computed: %s", correlations)
    return correlations


# ── Endpoint 4: GET /soxl/live/sector ──

@router.get("/sector")
async def soxl_sector_correlation(request: Request):
    """Sector ETF comparison with SOXL. Quotes from Finnhub, correlation from daily data."""
    fh = _get_finnhub(request)

    # Fetch live quotes from Finnhub
    all_symbols = ["SOXL"] + SECTOR_ETFS
    quotes = await fh.get_multi_quotes(all_symbols)

    # Compute correlations from daily historical data (DB + yfinance fallback)
    correlations = await _compute_daily_correlations(60)

    etfs = []
    for sym in SECTOR_ETFS:
        q = quotes.get(sym, {})
        etfs.append({
            "symbol": sym,
            "price": q.get("c", 0),
            "change": q.get("d", 0),
            "change_pct": q.get("dp", 0),
            "correlation": correlations.get(sym),
        })

    soxl_q = quotes.get("SOXL", {})
    return {
        "soxl": {
            "price": soxl_q.get("c", 0),
            "change": soxl_q.get("d", 0),
            "change_pct": soxl_q.get("dp", 0),
        },
        "etfs": etfs,
        "market_open": fh.is_market_open(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


# ── Endpoint 5: GET /soxl/live/stream ──

@router.get("/stream")
async def soxl_live_stream(request: Request):
    """SSE endpoint for real-time SOXL price updates."""
    fh = _get_finnhub(request)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            try:
                quote = await fh.get_quote("SOXL")
                market_open = fh.is_market_open()
                session = fh.get_market_session()

                # Check alerts
                triggered_alerts = await _check_alerts(quote.get("c", 0), quote.get("dp", 0))

                payload = {
                    "price": quote.get("c", 0),
                    "change": quote.get("d", 0),
                    "change_pct": quote.get("dp", 0),
                    "high": quote.get("h", 0),
                    "low": quote.get("l", 0),
                    "market_open": market_open,
                    "session": session,
                    "ts": datetime.now(UTC).isoformat(),
                    "alerts": triggered_alerts,
                }

                yield {
                    "event": "price",
                    "data": json.dumps(payload, ensure_ascii=False),
                }
            except Exception as e:
                logger.debug("SSE price fetch error: %s", e)
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)}),
                }

            # Poll interval: 15s during market hours, 60s otherwise
            interval = 15 if fh.is_market_open() else 60
            await asyncio.sleep(interval)

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Endpoint 6: Alerts CRUD ──

@router.get("/alerts")
async def get_soxl_alerts():
    """List all SOXL price alerts."""
    from app.database.connection import get_db
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, alert_type, threshold, label, triggered_at, active, created_at FROM soxl_alerts ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return {
        "alerts": [
            {
                "id": r[0], "alert_type": r[1], "threshold": r[2],
                "label": r[3], "triggered_at": r[4], "active": bool(r[5]),
                "created_at": r[6],
            }
            for r in rows
        ]
    }


@router.post("/alerts")
async def create_soxl_alert(alert: SoxlAlertCreate):
    """Create a new SOXL price alert."""
    valid_types = ("price_above", "price_below", "change_pct")
    if alert.alert_type not in valid_types:
        raise HTTPException(400, detail=f"Invalid alert_type. Must be one of: {valid_types}")

    from app.database.connection import get_db
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO soxl_alerts (alert_type, threshold, label) VALUES (?, ?, ?)",
        (alert.alert_type, alert.threshold, alert.label),
    )
    await db.commit()
    return {"id": cursor.lastrowid, "status": "created"}


@router.delete("/alerts/{alert_id}")
async def delete_soxl_alert(alert_id: int):
    """Delete an alert by ID."""
    from app.database.connection import get_db
    db = await get_db()
    await db.execute("DELETE FROM soxl_alerts WHERE id = ?", (alert_id,))
    await db.commit()
    return {"status": "deleted", "id": alert_id}


# ── Helper: Check alerts ──

async def _check_alerts(current_price: float, change_pct: float) -> list[dict]:
    """Check all active alerts against current quote. Returns triggered ones."""
    if current_price <= 0:
        return []

    from app.database.connection import get_db
    db = await get_db()

    cursor = await db.execute(
        "SELECT id, alert_type, threshold, label FROM soxl_alerts WHERE active = 1"
    )
    rows = await cursor.fetchall()

    triggered = []
    for r in rows:
        aid, atype, threshold, label = r
        fire = False

        if atype == "price_above" and current_price >= threshold:
            fire = True
        elif atype == "price_below" and current_price <= threshold:
            fire = True
        elif atype == "change_pct" and change_pct is not None and abs(change_pct) >= abs(threshold):
            fire = True

        if fire:
            await db.execute(
                "UPDATE soxl_alerts SET triggered_at = datetime('now'), active = 0 WHERE id = ?",
                (aid,),
            )
            triggered.append({
                "id": aid, "alert_type": atype, "threshold": threshold,
                "label": label, "current_price": current_price,
            })

    if triggered:
        await db.commit()
        logger.info("SOXL alerts triggered: %d", len(triggered))

    return triggered


# ── Technical indicator computations (numpy) ──

def _compute_rsi(closes: np.ndarray, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_macd(
    closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float | None, float | None, float | None]:
    if len(closes) < slow + signal:
        return None, None, None

    def ema(data: np.ndarray, period: int) -> np.ndarray:
        alpha = 2.0 / (period + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line

    return float(macd_line[-1]), float(signal_line[-1]), float(histogram[-1])


def _compute_bollinger(
    closes: np.ndarray, period: int = 20, std_dev: float = 2.0
) -> tuple[float | None, float | None, float | None]:
    if len(closes) < period:
        return None, None, None

    window = closes[-period:]
    middle = float(np.mean(window))
    std = float(np.std(window))
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return round(upper, 2), round(middle, 2), round(lower, 2)


# ── Endpoint 7: POST /soxl/live/ai-analysis ──

async def _gather_soxl_context(request: Request) -> dict:
    """Aggregate all SOXL-relevant data for AI analysis."""
    from app.database.connection import get_db
    db = await get_db()
    ctx = {}

    # 1. Current price (Finnhub)
    try:
        fh = _get_finnhub(request)
        quote = await fh.get_quote("SOXL")
        ctx["price"] = quote.get("c", 0)
        ctx["change"] = quote.get("d", 0)
        ctx["change_pct"] = quote.get("dp", 0)
        ctx["high"] = quote.get("h", 0)
        ctx["low"] = quote.get("l", 0)
        ctx["session"] = fh.get_market_session()
    except Exception as e:
        logger.warning("AI analysis: quote fetch failed: %s", e)
        ctx["price"] = 0

    # 2. Technical indicators (reuse existing computation)
    try:
        cursor = await db.execute(
            """SELECT close, volume FROM price_history
               WHERE symbol='SOXL' AND market='US'
               ORDER BY trade_date DESC LIMIT 60"""
        )
        rows = await cursor.fetchall()
        if rows:
            daily_closes = [r[0] for r in reversed(rows)]
            daily_volumes = [r[1] or 0 for r in reversed(rows)]
            if ctx["price"] > 0:
                daily_closes.append(ctx["price"])
            closes = np.array(daily_closes, dtype=float)

            ctx["rsi_14"] = round(_compute_rsi(closes, 14), 1) if _compute_rsi(closes, 14) else None
            macd_l, sig_l, hist = _compute_macd(closes)
            ctx["macd"] = round(macd_l, 4) if macd_l is not None else None
            ctx["macd_signal"] = round(sig_l, 4) if sig_l is not None else None
            ctx["macd_histogram"] = round(hist, 4) if hist is not None else None
            bb_u, bb_m, bb_l = _compute_bollinger(closes, 20, 2)
            ctx["bb_upper"] = bb_u
            ctx["bb_middle"] = bb_m
            ctx["bb_lower"] = bb_l
            ctx["ma_5"] = round(float(np.mean(closes[-5:])), 2) if len(closes) >= 5 else None
            ctx["ma_20"] = round(float(np.mean(closes[-20:])), 2) if len(closes) >= 20 else None
            ctx["ma_60"] = round(float(np.mean(closes[-60:])), 2) if len(closes) >= 60 else None

            if daily_volumes and len(daily_volumes) >= 20:
                avg_vol = np.mean(daily_volumes[-20:])
                ctx["volume_ratio"] = round(daily_volumes[-1] / avg_vol, 2) if avg_vol > 0 else None
            else:
                ctx["volume_ratio"] = None
    except Exception as e:
        logger.warning("AI analysis: technicals failed: %s", e)

    # 3. Latest SOXL signal
    try:
        cursor = await db.execute(
            """SELECT final_signal, raw_score, confidence, rationale, signal_date
               FROM signals WHERE symbol='SOXL'
               ORDER BY signal_date DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            ctx["signal"] = {
                "final_signal": row[0], "raw_score": row[1],
                "confidence": row[2], "rationale": row[3], "date": row[4],
            }
    except Exception as e:
        logger.debug("AI analysis: signal query failed: %s", e)

    # 4. Macro snapshot
    try:
        cursor = await db.execute(
            """SELECT vix, dxy_index, us_10y_yield, us_2y_yield, us_yield_spread,
                      wti_crude, gold_price, usd_krw, fed_funds_rate, fear_greed_index,
                      indicator_date
               FROM macro_indicators ORDER BY indicator_date DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            ctx["macro"] = {
                "vix": row[0], "dxy": row[1], "us_10y": row[2], "us_2y": row[3],
                "yield_spread": row[4], "wti": row[5], "gold": row[6],
                "usd_krw": row[7], "fed_rate": row[8], "fear_greed": row[9],
                "date": row[10],
            }
    except Exception as e:
        logger.debug("AI analysis: macro query failed: %s", e)

    # 5. Geopolitical events (recent 5)
    try:
        cursor = await db.execute(
            """SELECT event_date, event_text, detail, impact
               FROM geopolitical_events
               ORDER BY event_date DESC, id DESC LIMIT 5"""
        )
        rows = await cursor.fetchall()
        ctx["geo_events"] = [
            {"date": r[0], "event": r[1], "detail": r[2], "impact": r[3]}
            for r in rows
        ]
    except Exception as e:
        logger.debug("AI analysis: geo events query failed: %s", e)
        ctx["geo_events"] = []

    # 6. Semiconductor risks & key variables (from geopolitical module)
    try:
        from app.routers.geopolitical import SEMICONDUCTOR_RISKS, KEY_VARIABLES, SECTOR_IMPACT
        ctx["semi_risks"] = SEMICONDUCTOR_RISKS
        ctx["key_variables"] = KEY_VARIABLES
        # Filter sector impact for semiconductor
        ctx["semi_sector_impact"] = [s for s in SECTOR_IMPACT if "반도체" in s.get("sector", "")]
    except Exception:
        ctx["semi_risks"] = []
        ctx["key_variables"] = []

    # 7. Sector correlations
    try:
        ctx["correlations"] = await _compute_daily_correlations(60)
    except Exception:
        ctx["correlations"] = {}

    return ctx


def _build_soxl_ai_prompt(ctx: dict) -> str:
    """Build structured LLM prompt from gathered context."""
    sections = []

    # Header
    sections.append(
        "당신은 SOXL(Direxion Daily Semiconductor Bull 3X Shares ETF) 전문 투자 해설 AI입니다.\n"
        "아래 실시간 데이터를 종합하여 SOXL의 현재 상황과 전망을 한국어로 분석해주세요.\n"
        "투자 조언이 아닌 객관적 데이터 기반 해설입니다."
    )

    # Technical indicators
    tech = (
        f"현재가: ${ctx.get('price', '?')}, 등락: {ctx.get('change_pct', '?')}%\n"
        f"RSI-14: {ctx.get('rsi_14', '?')}\n"
        f"MACD: {ctx.get('macd', '?')} (신호선: {ctx.get('macd_signal', '?')}, 히스토그램: {ctx.get('macd_histogram', '?')})\n"
        f"볼린저밴드: 상단={ctx.get('bb_upper', '?')}, 중심={ctx.get('bb_middle', '?')}, 하단={ctx.get('bb_lower', '?')}\n"
        f"이동평균: MA5={ctx.get('ma_5', '?')}, MA20={ctx.get('ma_20', '?')}, MA60={ctx.get('ma_60', '?')}\n"
        f"거래량비율(vs 20일평균): {ctx.get('volume_ratio', '?')}"
    )
    sections.append(f"[SOXL 기술적 지표]\n{tech}")

    # Signal
    sig = ctx.get("signal", {})
    if sig:
        sig_text = (
            f"최신 시그널({sig.get('date', '?')}): {sig.get('final_signal', '?')}\n"
            f"점수: {sig.get('raw_score', '?')}, 신뢰도: {sig.get('confidence', '?')}\n"
            f"근거: {sig.get('rationale', '없음')}"
        )
        sections.append(f"[SOXL 파이프라인 시그널]\n{sig_text}")

    # Macro
    macro = ctx.get("macro", {})
    if macro:
        macro_text = (
            f"VIX: {macro.get('vix', '?')}, DXY: {macro.get('dxy', '?')}\n"
            f"미국 10Y 금리: {macro.get('us_10y', '?')}%, 2Y 금리: {macro.get('us_2y', '?')}%\n"
            f"금리 스프레드(10Y-2Y): {macro.get('yield_spread', '?')}%\n"
            f"기준금리: {macro.get('fed_rate', '?')}%\n"
            f"WTI 원유: ${macro.get('wti', '?')}, 금: ${macro.get('gold', '?')}\n"
            f"USD/KRW: {macro.get('usd_krw', '?')}\n"
            f"Fear & Greed: {macro.get('fear_greed', '?')}\n"
            f"데이터 기준일: {macro.get('date', '?')}"
        )
        sections.append(f"[매크로 환경]\n{macro_text}")

    # Geopolitical events
    geo = ctx.get("geo_events", [])
    if geo:
        geo_lines = [f"- [{e['date']}] ({e['impact']}) {e['event']}: {e.get('detail', '')}" for e in geo]
        sections.append(f"[지정학적 이벤트 (최근 5건)]\n" + "\n".join(geo_lines))

    # Semiconductor risks
    risks = ctx.get("semi_risks", [])
    if risks:
        risk_lines = [f"- [{r['severity']}] {r['risk']}: {r['detail']}" for r in risks]
        sections.append(f"[반도체 섹터 리스크]\n" + "\n".join(risk_lines))

    # Key variables
    kvars = ctx.get("key_variables", [])
    if kvars:
        kvar_lines = [f"- {k['variable']}: 현재={k['current']}, 긍정={k['bullish']}, 부정={k['bearish']}" for k in kvars]
        sections.append(f"[핵심 모니터링 변수]\n" + "\n".join(kvar_lines))

    # Sector correlations
    corr = ctx.get("correlations", {})
    if corr:
        corr_lines = [f"- SOXL vs {sym}: {val}" for sym, val in corr.items()]
        sections.append(f"[섹터 상관계수 (60일)]\n" + "\n".join(corr_lines))

    # Semi sector impact
    semi_impact = ctx.get("semi_sector_impact", [])
    if semi_impact:
        for s in semi_impact:
            sections.append(
                f"[반도체 섹터 영향 평가]\n"
                f"방향: {s['direction']}, 강도: {s['magnitude']}\n"
                f"관련 종목: {', '.join(s.get('tickers', []))}\n"
                f"사유: {s['reason']}"
            )

    # Analysis request
    sections.append(
        "[분석 요청]\n"
        "위 데이터를 종합하여 다음 4가지 항목으로 분석해주세요:\n\n"
        "1. **기술적 분석 요약**: 현재 추세, 과매수/과매도 상태, 주요 지지/저항선\n"
        "2. **매크로/지정학 영향**: VIX·유가·금리·지정학 리스크가 반도체/SOXL에 미치는 구체적 영향\n"
        "3. **종합 판단**: 단기(1-2주)/중기(1-3개월) 방향성, 핵심 모니터링 변수\n"
        "4. **리스크 관리**: 현 상황에서의 헤지 전략 제안 (SOXS, 현금비중 등)\n\n"
        "- 각 항목은 소제목과 함께 작성\n"
        "- 구체적 수치와 근거를 포함\n"
        "- 3x 레버리지 ETF의 특성(일일 리밸런싱 decay)을 고려\n"
        "- 한국어로 작성"
    )

    return "\n\n".join(sections)


@router.post("/ai-analysis")
async def soxl_ai_analysis(request: Request):
    """Generate comprehensive SOXL analysis combining technicals, macro, and geopolitical data via LLM."""
    from app.config import settings

    if not getattr(settings, "LLM_API_KEY", None):
        return {"status": "error", "message": "LLM API 키가 설정되지 않았습니다. .env에 LLM_API_KEY를 추가하세요."}

    try:
        # 1. Gather all context
        ctx = await _gather_soxl_context(request)

        # 2. Build prompt
        prompt = _build_soxl_ai_prompt(ctx)
        logger.info("SOXL AI analysis: prompt built (%d chars), calling LLM...", len(prompt))

        # 3. Call LLM
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
        msg = await client.messages.create(
            model=settings.LLM_MODEL or "claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        analysis_text = msg.content[0].text.strip()

        # 4. Build context snapshot for frontend KPI display
        macro = ctx.get("macro", {})
        sig = ctx.get("signal", {})
        context_snapshot = {
            "price": ctx.get("price"),
            "change_pct": ctx.get("change_pct"),
            "rsi": ctx.get("rsi_14"),
            "signal": sig.get("final_signal", "N/A"),
            "vix": macro.get("vix"),
            "oil": macro.get("wti"),
            "gold": macro.get("gold"),
            "dxy": macro.get("dxy"),
            "fear_greed": macro.get("fear_greed"),
            "geo_events_count": len(ctx.get("geo_events", [])),
            "correlations": ctx.get("correlations", {}),
        }

        return {
            "status": "ok",
            "analysis": analysis_text,
            "context_snapshot": context_snapshot,
            "generated_at": datetime.now(UTC).isoformat(),
            "model": settings.LLM_MODEL or "claude-sonnet-4-20250514",
        }

    except Exception as e:
        logger.error("SOXL AI analysis failed: %s", e, exc_info=True)
        return {"status": "error", "message": f"AI 분석 생성 실패: {str(e)}"}
