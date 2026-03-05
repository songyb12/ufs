import logging
from datetime import date, timedelta

import pandas as pd

from app.collectors.base import BaseCollector
from app.config import Settings
from app.utils.retry import async_retry

logger = logging.getLogger("vibe.collectors.macro")


class MacroCollector:
    """Global macro indicator collector using FinanceDataReader."""

    def __init__(self, config: Settings):
        self.config = config

    @async_retry(max_attempts=3, base_delay=2.0)
    async def collect(self, days_back: int = 30) -> dict:
        """Collect latest macro indicators. Returns dict for upsert."""
        import asyncio
        import FinanceDataReader as fdr

        loop = asyncio.get_running_loop()
        start = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end = date.today().strftime("%Y-%m-%d")

        async def _fetch(symbol: str) -> pd.DataFrame | None:
            try:
                df = await loop.run_in_executor(
                    None, lambda s=symbol: fdr.DataReader(s, start, end)
                )
                return df if df is not None and not df.empty else None
            except Exception as e:
                logger.warning("Macro fetch failed for %s: %s", symbol, e)
                return None

        # Fetch all macro data concurrently via asyncio.gather
        vix_df, dxy_df, usdkrw_df, wti_df, gold_df, us10y_df, us2y_df = await asyncio.gather(
            _fetch("VIX"),        # CBOE Volatility Index
            _fetch("DX-Y.NYB"),   # US Dollar Index
            _fetch("USD/KRW"),    # Won/Dollar exchange rate
            _fetch("CL=F"),       # WTI Crude Oil Futures
            _fetch("GC=F"),       # Gold Futures
            _fetch("^TNX"),       # US 10Y Treasury Yield
            _fetch("^IRX"),       # US 2Y (13-week T-bill as proxy)
        )

        def _latest(df: pd.DataFrame | None, col: str = "Close") -> float | None:
            if df is None or df.empty:
                return None
            if col in df.columns:
                val = df[col].iloc[-1]
                return float(val) if pd.notna(val) else None
            return None

        us_10y = _latest(us10y_df)
        us_2y = _latest(us2y_df)

        result = {
            "indicator_date": date.today().strftime("%Y-%m-%d"),
            "vix": _latest(vix_df),
            "dxy_index": _latest(dxy_df),
            "usd_krw": _latest(usdkrw_df),
            "wti_crude": _latest(wti_df),
            "gold_price": _latest(gold_df),
            "us_10y_yield": us_10y,
            "us_2y_yield": us_2y,
            "us_yield_spread": (us_10y - us_2y) if (us_10y and us_2y) else None,
            "fed_funds_rate": None,  # Requires FRED API key for direct access
            "kr_base_rate": None,    # Updated manually or via BOK API
            "fear_greed_index": None,  # Requires CNN scraper or alternative
        }

        logger.info(
            "Macro collected: VIX=%.1f, DXY=%.1f, USD/KRW=%.1f, WTI=%.1f",
            result.get("vix") or 0,
            result.get("dxy_index") or 0,
            result.get("usd_krw") or 0,
            result.get("wti_crude") or 0,
        )

        return result
