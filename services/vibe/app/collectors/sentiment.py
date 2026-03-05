"""Sentiment data collectors - Fear & Greed, VIX term structure."""

import logging
from typing import Any

import httpx

logger = logging.getLogger("vibe.collectors.sentiment")


async def fetch_fear_greed_index() -> dict[str, Any]:
    """Fetch CNN Fear & Greed Index from alternative.me API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1")
            data = resp.json()
            if data.get("data"):
                entry = data["data"][0]
                return {
                    "fear_greed_index": int(entry["value"]),
                    "fear_greed_label": entry["value_classification"],
                    "timestamp": entry["timestamp"],
                }
    except Exception as e:
        logger.warning("Fear & Greed fetch failed: %s", e)
    return {}


async def fetch_vix_term_structure() -> dict[str, Any]:
    """Fetch VIX and VIX3M for term structure analysis."""
    import asyncio

    def _fetch():
        try:
            import yfinance as yf

            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="5d")

            vix3m = yf.Ticker("^VIX3M")
            vix3m_hist = vix3m.history(period="5d")

            result = {}
            if not vix_hist.empty:
                result["vix_current"] = round(float(vix_hist["Close"].iloc[-1]), 2)
            if not vix3m_hist.empty:
                result["vix3m_current"] = round(float(vix3m_hist["Close"].iloc[-1]), 2)

            if result.get("vix_current") and result.get("vix3m_current"):
                # Contango (VIX < VIX3M) = normal/bullish
                # Backwardation (VIX > VIX3M) = stress/bearish
                result["vix_term_structure"] = "contango" if result["vix_current"] < result["vix3m_current"] else "backwardation"
                result["vix_ratio"] = round(result["vix_current"] / result["vix3m_current"], 4)

            return result
        except Exception as e:
            logger.warning("VIX term structure fetch failed: %s", e)
            return {}

    return await asyncio.to_thread(_fetch)


async def fetch_put_call_ratio() -> dict[str, Any]:
    """Fetch CBOE Put/Call ratio (approximation from VIX data)."""
    import asyncio

    def _fetch():
        try:
            import yfinance as yf

            # Use CBOE Total Put/Call Ratio index if available
            # Fallback: estimate from SPY options
            spy = yf.Ticker("SPY")
            info = spy.info

            # Approximate put/call ratio from options chain if available
            try:
                exp_dates = spy.options
                if exp_dates:
                    chain = spy.option_chain(exp_dates[0])
                    puts_vol = chain.puts["volume"].sum()
                    calls_vol = chain.calls["volume"].sum()
                    if calls_vol > 0:
                        return {
                            "put_call_ratio": round(puts_vol / calls_vol, 4),
                            "puts_volume": int(puts_vol),
                            "calls_volume": int(calls_vol),
                        }
            except Exception as e:
                logger.debug("SPY options chain parsing failed: %s", e)

            return {}
        except Exception as e:
            logger.warning("Put/Call ratio fetch failed: %s", e)
            return {}

    return await asyncio.to_thread(_fetch)
