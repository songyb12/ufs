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
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, lambda s=symbol: fdr.DataReader(s, start, end)
                    ),
                    timeout=30.0,
                )
                return df if df is not None and not df.empty else None
            except asyncio.TimeoutError:
                logger.warning("Macro fetch timed out for %s (30s)", symbol)
                return None
            except Exception as e:
                logger.warning("Macro fetch failed for %s: %s", symbol, e)
                return None

        # Fetch all macro data concurrently via asyncio.gather
        (vix_df, dxy_df, usdkrw_df, wti_df, gold_df,
         us10y_df, us2y_df, copper_df) = await asyncio.gather(
            _fetch("VIX"),        # CBOE Volatility Index
            _fetch("DX-Y.NYB"),   # US Dollar Index
            _fetch("USD/KRW"),    # Won/Dollar exchange rate
            _fetch("CL=F"),       # WTI Crude Oil Futures
            _fetch("GC=F"),       # Gold Futures
            _fetch("^TNX"),       # US 10Y Treasury Yield
            _fetch("^IRX"),       # US 13-week T-bill rate (proxy for short-term rate;
                                  # true 2Y not reliably available via FDR)
            _fetch("HG=F"),       # Copper Futures (Dr. Copper — economic leading indicator)
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
            "copper_price": _latest(copper_df),
            "us_10y_yield": us_10y,
            "us_2y_yield": us_2y,
            "us_yield_spread": (us_10y - us_2y) if (us_10y is not None and us_2y is not None) else None,
            "fed_funds_rate": None,  # Requires FRED API key for direct access
            "kr_base_rate": None,    # Updated manually or via BOK API
            "fear_greed_index": None,  # Requires CNN scraper or alternative
        }

        logger.info(
            "Macro collected: VIX=%.1f, DXY=%.1f, USD/KRW=%.1f, WTI=%.1f, Gold=%.0f, Copper=%.2f",
            result.get("vix") or 0,
            result.get("dxy_index") or 0,
            result.get("usd_krw") or 0,
            result.get("wti_crude") or 0,
            result.get("gold_price") or 0,
            result.get("copper_price") or 0,
        )

        return result

    async def backfill(self, days_back: int = 90) -> list[dict]:
        """Backfill historical macro data for the given period.

        Unlike collect() which stores only the latest day, this retrieves
        the full time-series from FinanceDataReader and returns one dict per day
        for bulk upsert.
        """
        import asyncio
        import FinanceDataReader as fdr

        loop = asyncio.get_running_loop()
        start = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end = date.today().strftime("%Y-%m-%d")

        async def _fetch(symbol: str) -> pd.DataFrame | None:
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, lambda s=symbol: fdr.DataReader(s, start, end)
                    ),
                    timeout=60.0,  # backfill fetches more data, allow longer
                )
                return df if df is not None and not df.empty else None
            except asyncio.TimeoutError:
                logger.warning("Macro backfill fetch timed out for %s (60s)", symbol)
                return None
            except Exception as e:
                logger.warning("Macro backfill fetch failed for %s: %s", symbol, e)
                return None

        (vix_df, dxy_df, usdkrw_df, wti_df, gold_df,
         us10y_df, us2y_df, copper_df) = await asyncio.gather(
            _fetch("VIX"),        # CBOE Volatility Index
            _fetch("DX-Y.NYB"),   # US Dollar Index
            _fetch("USD/KRW"),    # Won/Dollar exchange rate
            _fetch("CL=F"),       # WTI Crude Oil Futures
            _fetch("GC=F"),       # Gold Futures
            _fetch("^TNX"),       # US 10Y Treasury Yield
            _fetch("^IRX"),       # US 13-week T-bill rate (proxy for short-term rate)
            _fetch("HG=F"),       # Copper Futures
        )

        # Collect all unique dates across all DataFrames
        all_dates: set[str] = set()
        dfs = {
            "vix": vix_df, "dxy_index": dxy_df, "usd_krw": usdkrw_df,
            "wti_crude": wti_df, "gold_price": gold_df,
            "us_10y_yield": us10y_df, "us_2y_yield": us2y_df,
            "copper_price": copper_df,
        }
        for df in dfs.values():
            if df is not None and not df.empty:
                for dt in df.index:
                    all_dates.add(dt.strftime("%Y-%m-%d"))

        def _val(df: pd.DataFrame | None, date_str: str, col: str = "Close") -> float | None:
            if df is None or df.empty or col not in df.columns:
                return None
            try:
                day_rows = df[df.index.strftime("%Y-%m-%d") == date_str]
                if day_rows.empty:
                    return None
                val = day_rows[col].iloc[-1]
                return float(val) if pd.notna(val) else None
            except Exception:
                return None

        rows = []
        for d in sorted(all_dates):
            us10y = _val(us10y_df, d)
            us2y = _val(us2y_df, d)
            row = {
                "indicator_date": d,
                "vix": _val(vix_df, d),
                "dxy_index": _val(dxy_df, d),
                "usd_krw": _val(usdkrw_df, d),
                "wti_crude": _val(wti_df, d),
                "gold_price": _val(gold_df, d),
                "copper_price": _val(copper_df, d),
                "us_10y_yield": us10y,
                "us_2y_yield": us2y,
                "us_yield_spread": (us10y - us2y) if (us10y is not None and us2y is not None) else None,
                "fed_funds_rate": None,
                "kr_base_rate": None,
                "fear_greed_index": None,
            }
            rows.append(row)

        logger.info("Macro backfill: %d days fetched (%s ~ %s)", len(rows), start, end)
        return rows
