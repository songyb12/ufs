import logging

import pandas as pd

from app.collectors.base import BaseCollector
from app.config import Settings
from app.utils.retry import async_retry

logger = logging.getLogger("vibe.collectors.us")


class USMarketCollector(BaseCollector):
    """US market data collector using yfinance."""

    @property
    def market(self) -> str:
        return "US"

    @async_retry(max_attempts=3, base_delay=2.0)
    async def fetch_ohlcv(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        import yfinance as yf

        def _download():
            df = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
            )
            return df

        df = await self._run_sync(_download)

        if df is None or df.empty:
            return pd.DataFrame()

        # yfinance with auto_adjust: Open, High, Low, Close, Volume
        # Handle MultiIndex columns from yfinance (ticker as second level)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = self.normalize_columns(df, {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })

        # Convert index to date string
        df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
        return df

    async def fetch_ohlcv_batch(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        """Batch download for US stocks using yfinance multi-ticker."""
        import yfinance as yf

        tickers_str = " ".join(symbols)

        def _download_all():
            return yf.download(
                tickers_str,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
            )

        try:
            raw = await self._run_sync(_download_all)
        except Exception as e:
            logger.error("Batch download failed, falling back to individual: %s", e)
            return await super().fetch_ohlcv_batch(symbols, start_date, end_date)

        if raw is None or raw.empty:
            return {}

        results: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            try:
                if len(symbols) == 1:
                    # Single ticker: no MultiIndex on columns
                    df = raw.copy()
                else:
                    df = raw[symbol].copy()

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                df = df.dropna(how="all")
                if df.empty:
                    continue

                df = self.normalize_columns(df, {
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                })
                df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
                results[symbol] = df
                logger.info("[US] %s: %d rows fetched", symbol, len(df))
            except Exception as e:
                logger.warning("[US] %s: parse error - %s", symbol, e)

        return results

    @async_retry(max_attempts=2, base_delay=1.0)
    async def fetch_fundamentals(self, symbol: str) -> dict:
        """Fetch PER, PBR, EPS, dividend yield."""
        import yfinance as yf

        def _get_info():
            ticker = yf.Ticker(symbol)
            return ticker.info

        try:
            info = await self._run_sync(_get_info)
        except Exception:
            return {}

        return {
            "per": info.get("trailingPE"),
            "pbr": info.get("priceToBook"),
            "eps": info.get("trailingEps"),
            "div_yield": info.get("dividendYield"),
        }
