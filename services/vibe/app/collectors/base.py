import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta

import pandas as pd

from app.config import Settings

logger = logging.getLogger("vibe.collectors")


class BaseCollector(ABC):
    """Abstract base for market data collectors."""

    def __init__(self, config: Settings):
        self.config = config
        self._executor = None  # Uses default ThreadPoolExecutor

    @property
    @abstractmethod
    def market(self) -> str:
        """Market identifier: 'KR' or 'US'."""
        ...

    @abstractmethod
    async def fetch_ohlcv(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch OHLCV data. Returns DataFrame with columns:
        [open, high, low, close, volume] indexed by date string."""
        ...

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1  # seconds

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Check if the exception warrants a retry (429 or 5xx)."""
        # Check for HTTP status codes in common exception patterns
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if status is not None:
            return status == 429 or (500 <= status < 600)
        # Check for string representations containing status codes
        msg = str(exc).lower()
        if "429" in msg or "rate limit" in msg or "too many requests" in msg:
            return True
        if any(f"{code}" in msg for code in range(500, 600)):
            return True
        # Network errors are retryable
        for keyword in ("timeout", "connection", "reset", "broken pipe"):
            if keyword in msg:
                return True
        return False

    async def _fetch_with_retry(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame | None:
        """Fetch OHLCV with exponential backoff retry for retryable errors."""
        last_exc = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return await self.fetch_ohlcv(symbol, start_date, end_date)
            except Exception as e:
                last_exc = e
                if attempt < self.MAX_RETRIES and self._is_retryable(e):
                    delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))  # 1s, 2s, 4s
                    logger.warning(
                        "[%s] %s: Retry %d/%d after %ds: %s",
                        self.market, symbol, attempt, self.MAX_RETRIES, delay, e,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        raise last_exc  # Should not reach here, but satisfy type checker

    async def fetch_ohlcv_batch(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV for multiple symbols with rate limiting and retry."""
        results: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            try:
                df = await self._fetch_with_retry(symbol, start_date, end_date)
                if df is not None and not df.empty:
                    results[symbol] = df
                    logger.info("[%s] %s: %d rows fetched", self.market, symbol, len(df))
                else:
                    logger.warning("[%s] %s: empty data returned", self.market, symbol)
            except Exception as e:
                logger.error("[%s] %s: fetch failed - %s", self.market, symbol, e, exc_info=True)

            # Rate limiting between requests
            await asyncio.sleep(self.config.COLLECTION_DELAY_SECONDS)

        return results

    def _run_sync(self, func, *args):
        """Run a synchronous function in a thread executor."""
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(self._executor, func, *args)

    @staticmethod
    def _default_start_date(days_back: int = 200) -> str:
        return (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    @staticmethod
    def _today() -> str:
        return date.today().strftime("%Y-%m-%d")

    @staticmethod
    def normalize_columns(df: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
        """Rename columns to standard names: open, high, low, close, volume."""
        df = df.rename(columns=column_map)
        standard_cols = ["open", "high", "low", "close", "volume"]
        existing = [c for c in standard_cols if c in df.columns]
        return df[existing]
