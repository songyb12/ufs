"""Price data collector — SOXL/SOXX/^SOX OHLCV via yfinance."""

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from app.config import settings
from app.db import get_sync_db

logger = logging.getLogger("vibe2.collector.price")

# Symbols that are prices (not macro indicators)
PRICE_SYMBOLS = ["SOXL", "SOXX", "^SOX"]

HISTORY_DAYS = 200


def fetch_prices(
    symbol: str,
    days: int = HISTORY_DAYS,
) -> pd.DataFrame | None:
    """Fetch OHLCV data for a single symbol via yfinance.

    Returns DataFrame with columns [open, high, low, close, volume]
    indexed by date, or None on failure.
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
            logger.warning("No price data returned for %s", symbol)
            return None

        # Handle MultiIndex columns (yfinance >= 0.2.31 returns these)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Normalize column names to lowercase
        df.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in df.columns]

        # Deduplicate column names (can happen after MultiIndex flattening)
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]

        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            logger.warning("Missing columns for %s: %s", symbol, df.columns.tolist())
            return None

        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.to_datetime(df.index)
        logger.info("Fetched %d rows for %s", len(df), symbol)
        return df

    except Exception as e:
        logger.error("Failed to fetch prices for %s: %s", symbol, e)
        return None


def save_prices(symbol: str, df: pd.DataFrame) -> int:
    """Save price DataFrame to the prices table. Returns rows upserted."""
    if df is None or df.empty:
        return 0

    conn = get_sync_db()
    try:
        rows = []
        for date_idx, row in df.iterrows():
            trade_date = str(date_idx)[:10]
            close_val = row["close"]
            # Skip rows with NaN close
            if pd.isna(close_val):
                continue
            rows.append((
                symbol,
                trade_date,
                float(row["open"]) if not pd.isna(row["open"]) else None,
                float(row["high"]) if not pd.isna(row["high"]) else None,
                float(row["low"]) if not pd.isna(row["low"]) else None,
                float(close_val),
                int(row["volume"]) if not pd.isna(row["volume"]) else None,
            ))

        if not rows:
            return 0

        conn.executemany(
            """INSERT OR REPLACE INTO prices
               (symbol, trade_date, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
        logger.info("Saved %d price rows for %s", len(rows), symbol)
        return len(rows)
    except Exception as e:
        logger.error("Failed to save prices for %s: %s", symbol, e)
        return 0
    finally:
        conn.close()


def collect_all_prices(
    symbols: list[str] | None = None,
    days: int = HISTORY_DAYS,
) -> dict[str, int]:
    """Collect and save prices for all symbols. Returns {symbol: rows_saved}."""
    symbols = symbols or PRICE_SYMBOLS
    results: dict[str, int] = {}

    for symbol in symbols:
        df = fetch_prices(symbol, days=days)
        saved = save_prices(symbol, df)
        results[symbol] = saved

        # Rate limiting between symbols
        if symbol != symbols[-1]:
            time.sleep(1.0)

    total = sum(results.values())
    logger.info("Price collection complete: %d total rows across %d symbols", total, len(symbols))
    return results
