"""Macro indicator collector — VIX, DXY, Treasury yields via yfinance."""

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from app.db import get_sync_db

logger = logging.getLogger("vibe2.collector.macro")

# Symbol → column mapping in macro_data table
MACRO_SYMBOLS: dict[str, str] = {
    "^VIX": "vix",
    "DX-Y.NYB": "dxy",
    "^TNX": "us_10y_yield",
    "^FVX": "us_2y_yield",   # 5-year as proxy (2-year has no reliable free ticker)
    "CL=F": "wti_crude",
    "GC=F": "gold_price",
}

HISTORY_DAYS = 60


def fetch_macro(
    symbol: str,
    days: int = HISTORY_DAYS,
) -> pd.Series | None:
    """Fetch closing prices for a single macro symbol.

    Returns a Series indexed by date (close values), or None on failure.
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    try:
        df = yf.download(
            symbol,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            logger.warning("No macro data returned for %s", symbol)
            return None

        # Handle MultiIndex columns (yfinance >= 0.2.31)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in df.columns]

        if "close" not in df.columns:
            logger.warning("No 'close' column for %s", symbol)
            return None

        series = df["close"].dropna()
        logger.info("Fetched %d macro rows for %s", len(series), symbol)
        return series

    except Exception as e:
        logger.error("Failed to fetch macro for %s: %s", symbol, e)
        return None


def save_macro(macro_dict: dict[str, pd.Series]) -> int:
    """Merge macro series by date and upsert into macro_data table.

    Args:
        macro_dict: {column_name: Series} e.g. {"vix": Series, "dxy": Series}

    Returns number of rows upserted.
    """
    if not macro_dict:
        return 0

    # Build a combined DataFrame aligned by date
    combined = pd.DataFrame(macro_dict)
    if combined.empty:
        return 0

    combined.index = pd.to_datetime(combined.index)
    combined = combined.sort_index()

    conn = get_sync_db()
    try:
        count = 0
        for date_idx, row in combined.iterrows():
            indicator_date = str(date_idx)[:10]
            values = {col: (float(row[col]) if not pd.isna(row[col]) else None) for col in combined.columns}

            # Compute yield spread if both yields available
            spread = None
            if values.get("us_10y_yield") is not None and values.get("us_2y_yield") is not None:
                spread = values["us_10y_yield"] - values["us_2y_yield"]

            conn.execute(
                """INSERT OR REPLACE INTO macro_data
                   (indicator_date, vix, dxy, us_10y_yield, us_2y_yield,
                    yield_spread, wti_crude, gold_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    indicator_date,
                    values.get("vix"),
                    values.get("dxy"),
                    values.get("us_10y_yield"),
                    values.get("us_2y_yield"),
                    spread,
                    values.get("wti_crude"),
                    values.get("gold_price"),
                ),
            )
            count += 1

        conn.commit()
        logger.info("Saved %d macro rows", count)
        return count
    except Exception as e:
        logger.error("Failed to save macro data: %s", e)
        return 0
    finally:
        conn.close()


def collect_all_macro(days: int = HISTORY_DAYS) -> int:
    """Collect and save all macro indicators. Returns total rows saved."""
    macro_series: dict[str, pd.Series] = {}

    for symbol, column in MACRO_SYMBOLS.items():
        series = fetch_macro(symbol, days=days)
        if series is not None:
            macro_series[column] = series
        time.sleep(1.0)

    return save_macro(macro_series)


def get_latest_macro() -> dict | None:
    """Get the most recent macro data row."""
    conn = get_sync_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM macro_data ORDER BY indicator_date DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    except Exception as e:
        logger.error("Failed to get latest macro: %s", e)
        return None
    finally:
        conn.close()
