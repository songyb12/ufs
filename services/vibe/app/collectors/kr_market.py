import logging

import pandas as pd

from app.collectors.base import BaseCollector
from app.config import Settings
from app.utils.retry import async_retry

logger = logging.getLogger("vibe.collectors.kr")


class KRMarketCollector(BaseCollector):
    """Korean market data collector using pykrx (KRX direct)."""

    @property
    def market(self) -> str:
        return "KR"

    @async_retry(max_attempts=3, base_delay=2.0)
    async def fetch_ohlcv(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        from pykrx import stock

        # pykrx uses YYYYMMDD format
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")

        df = await self._run_sync(
            stock.get_market_ohlcv_by_date, start, end, symbol
        )

        if df is None or df.empty:
            return pd.DataFrame()

        # pykrx columns: 시가, 고가, 저가, 종가, 거래량
        df = self.normalize_columns(df, {
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
        })

        # Drop rows where close is NaN (invalid data from pykrx)
        if "close" in df.columns:
            df = df.dropna(subset=["close"])

        # Convert index to date string (guard against non-DatetimeIndex)
        if hasattr(df.index, "strftime"):
            df.index = df.index.strftime("%Y-%m-%d")
        else:
            df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
        return df

    @async_retry(max_attempts=3, base_delay=2.0)
    async def fetch_fund_flow(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch investor net buy/sell data (외국인/기관/개인 수급)."""
        from pykrx import stock

        start = start_date.replace("-", "")
        end = end_date.replace("-", "")

        df = await self._run_sync(
            stock.get_market_trading_value_by_date, start, end, symbol
        )

        if df is None or df.empty:
            return pd.DataFrame()

        # Columns: 기관합계, 기타법인, 개인, 외국인합계, 전체
        df = self.normalize_columns(df, {
            "외국인합계": "foreign_net_buy",
            "기관합계": "institution_net_buy",
            "개인": "individual_net_buy",
        })

        # Convert index to date string (guard against non-DatetimeIndex)
        if hasattr(df.index, "strftime"):
            df.index = df.index.strftime("%Y-%m-%d")
        else:
            df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
        return df

    @async_retry(max_attempts=2, base_delay=1.0)
    async def fetch_fundamentals(self, symbol: str, date_str: str) -> dict:
        """Fetch PER, PBR, EPS, dividend yield for a given date."""
        from pykrx import stock

        d = date_str.replace("-", "")

        df = await self._run_sync(
            stock.get_market_fundamental_by_date, d, d, symbol
        )

        if df is None or df.empty:
            return {}

        row = df.iloc[0]

        def _safe_val(series_row, col):
            """Extract float from pandas row, returning None for NaN/missing."""
            import math
            if col not in series_row.index:
                return None
            val = series_row[col]
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return None
            return float(val)

        return {
            "per": _safe_val(row, "PER"),
            "pbr": _safe_val(row, "PBR"),
            "eps": _safe_val(row, "EPS"),
            "div_yield": _safe_val(row, "DIV"),
        }
