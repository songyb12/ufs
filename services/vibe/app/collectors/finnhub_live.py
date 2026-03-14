"""
Finnhub.io live data client for real-time SOXL analysis.

Features:
- Token-bucket rate limiter (60 calls/min free tier)
- In-memory TTL cache per endpoint
- Market hours detection (US Eastern)
- Async httpx with connection pooling
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger("vibe.finnhub")

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

FINNHUB_BASE = "https://finnhub.io/api/v1"


class FinnhubRateLimiter:
    """Token-bucket rate limiter: N tokens per minute, continuous refill."""

    def __init__(self, max_calls: int = 55, period: float = 60.0):
        self._tokens: float = float(max_calls)
        self._max: int = max_calls
        self._period: float = period
        self._last_refill: float = time.monotonic()
        self._lock: asyncio.Lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._max, self._tokens + (elapsed / self._period) * self._max)
            self._last_refill = now

            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / (self._max / self._period)
                logger.debug("Rate limit: waiting %.1fs", wait)
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


class _CacheEntry:
    __slots__ = ("data", "expires_at")

    def __init__(self, data: dict | list, ttl: float):
        self.data = data
        self.expires_at = time.monotonic() + ttl

    @property
    def valid(self) -> bool:
        return time.monotonic() < self.expires_at


class FinnhubLiveClient:
    """Async Finnhub REST client with rate limiting and TTL cache."""

    def __init__(self, api_key: str, rate_limiter: FinnhubRateLimiter):
        self._api_key = api_key
        self._limiter = rate_limiter
        self._client = httpx.AsyncClient(
            base_url=FINNHUB_BASE,
            timeout=10.0,
            headers={"X-Finnhub-Token": api_key},
        )
        self._cache: dict[str, _CacheEntry] = {}
        logger.info("FinnhubLiveClient initialized")

    # ── Public API ──

    async def get_quote(self, symbol: str) -> dict:
        """Current price quote. Cache TTL: 10s.

        Returns: {c, d, dp, h, l, o, pc, t}
        c=current, d=change, dp=change%, h=high, l=low, o=open, pc=prev_close, t=timestamp
        """
        key = f"quote:{symbol}"
        cached = self._cache.get(key)
        if cached and cached.valid:
            return cached.data

        await self._limiter.acquire()
        resp = await self._client.get("/quote", params={"symbol": symbol})
        resp.raise_for_status()
        data = resp.json()

        # Finnhub returns {c:0, d:null, dp:null} for invalid symbols
        if data.get("c") == 0 and data.get("d") is None:
            logger.warning("Finnhub quote returned empty for %s", symbol)
            return data

        self._cache[key] = _CacheEntry(data, ttl=10.0)
        return data

    async def get_candles(
        self, symbol: str, resolution: str, from_ts: int, to_ts: int
    ) -> list[dict]:
        """Intraday/daily candles. Cache TTL: 30s for intraday, 300s for daily.

        Resolution: '1', '5', '15', '30', '60', 'D'
        Returns: [{time, open, high, low, close, volume}, ...]
        """
        key = f"candle:{symbol}:{resolution}:{from_ts}"
        cached = self._cache.get(key)
        if cached and cached.valid:
            return cached.data

        await self._limiter.acquire()
        try:
            resp = await self._client.get(
                "/stock/candle",
                params={
                    "symbol": symbol,
                    "resolution": resolution,
                    "from": from_ts,
                    "to": to_ts,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.warning("Finnhub candle 403 for %s res=%s (free tier limit)", symbol, resolution)
                self._cache[key] = _CacheEntry([], ttl=300.0)
                return []
            raise
        raw = resp.json()

        # Finnhub returns {s: "no_data"} when no data
        if raw.get("s") == "no_data" or "t" not in raw:
            self._cache[key] = _CacheEntry([], ttl=30.0)
            return []

        candles = []
        for i in range(len(raw["t"])):
            candles.append({
                "time": raw["t"][i],
                "open": raw["o"][i],
                "high": raw["h"][i],
                "low": raw["l"][i],
                "close": raw["c"][i],
                "volume": raw["v"][i],
            })

        ttl = 30.0 if resolution in ("1", "5", "15") else 300.0
        self._cache[key] = _CacheEntry(candles, ttl=ttl)
        return candles

    async def get_multi_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Batch fetch quotes for multiple symbols. Cache-aware."""
        results = {}
        for sym in symbols:
            try:
                results[sym] = await self.get_quote(sym)
            except Exception as e:
                logger.warning("Quote fetch failed for %s: %s", sym, e)
                results[sym] = {"c": 0, "d": 0, "dp": 0, "error": str(e)}
        return results

    def is_market_open(self) -> bool:
        """Check if US stock market is currently in regular session (09:30-16:00 ET, Mon-Fri)."""
        now_et = datetime.now(ET)
        # Weekend check
        if now_et.weekday() >= 5:
            return False
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= now_et <= market_close

    def get_market_session(self) -> str:
        """Get current market session name."""
        now_et = datetime.now(ET)
        if now_et.weekday() >= 5:
            return "주말"
        h, m = now_et.hour, now_et.minute
        t = h * 60 + m
        if t < 4 * 60:
            return "장마감"
        elif t < 9 * 60 + 30:
            return "프리마켓"
        elif t < 16 * 60:
            return "장중"
        elif t < 20 * 60:
            return "애프터마켓"
        else:
            return "장마감"

    def next_market_open(self) -> datetime | None:
        """Get the next market open time (ET)."""
        now_et = datetime.now(ET)
        target = now_et.replace(hour=9, minute=30, second=0, microsecond=0)

        if now_et.weekday() >= 5 or now_et >= target.replace(hour=16):
            # Move to next weekday
            days_ahead = 1
            while True:
                candidate = now_et + timedelta(days=days_ahead)
                if candidate.weekday() < 5:
                    return candidate.replace(hour=9, minute=30, second=0, microsecond=0)
                days_ahead += 1
        elif now_et < target:
            return target
        return None  # Market is currently open

    async def close(self) -> None:
        await self._client.aclose()
        logger.info("FinnhubLiveClient closed")

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
