"""Dynamic Screener - Detect volume spikes, breakouts, new highs."""

import logging
from datetime import datetime, timedelta

import pandas as pd

from app.database import repositories as repo

logger = logging.getLogger("vibe.screening.scanner")


class DynamicScreener:
    """Scan for unusual market activity patterns."""

    async def scan(self, market: str, days_back: int = 5) -> list[dict]:
        """Run all screening filters and return candidates.

        Returns list of dicts with: symbol, market, trigger_type, trigger_value,
        trigger_description
        """
        candidates = []

        # Get all symbols for the market
        watchlist = await repo.get_watchlist(market)
        symbols = [w["symbol"] for w in watchlist]

        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d")

        for symbol in symbols:
            prices = await repo.get_price_range(symbol, market, start_date, end_date)
            if not prices or len(prices) < 20:
                continue

            df = pd.DataFrame(prices)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.sort_values("trade_date")

            # Check each trigger
            triggers = []
            triggers.extend(self._check_volume_spike(df, symbol, days_back))
            triggers.extend(self._check_new_high(df, symbol, days_back))
            triggers.extend(self._check_breakout(df, symbol, days_back))

            for t in triggers:
                t["market"] = market
                candidates.append(t)

        logger.info("Screening found %d candidates for %s", len(candidates), market)
        return candidates

    def _check_volume_spike(
        self, df: pd.DataFrame, symbol: str, days_back: int,
    ) -> list[dict]:
        """Detect volume spikes > 3x 20-day average in recent days."""
        results = []
        if "volume" not in df.columns or len(df) < 21:
            return results

        vol_avg_20 = df["volume"].rolling(20).mean()
        recent = df.tail(days_back)

        for idx, row in recent.iterrows():
            i = df.index.get_loc(idx)
            if i < 20:
                continue
            avg = vol_avg_20.iloc[i]
            if avg and avg > 0 and row["volume"] > avg * 3:
                ratio = row["volume"] / avg
                results.append({
                    "symbol": symbol,
                    "detected_date": str(row["trade_date"].date()),
                    "trigger_type": "volume_spike",
                    "trigger_value": round(ratio, 2),
                    "trigger_description": f"Volume {ratio:.1f}x above 20-day avg",
                })
        return results

    def _check_new_high(
        self, df: pd.DataFrame, symbol: str, days_back: int,
    ) -> list[dict]:
        """Detect 52-week (or available period) new highs."""
        results = []
        if len(df) < 20:
            return results

        lookback = min(252, len(df) - 1)  # 52 weeks or max available
        recent = df.tail(days_back)

        for idx, row in recent.iterrows():
            i = df.index.get_loc(idx)
            if i < lookback:
                continue
            period_high = df["close"].iloc[i - lookback:i].max()
            if row["close"] > period_high:
                results.append({
                    "symbol": symbol,
                    "detected_date": str(row["trade_date"].date()),
                    "trigger_type": "new_high",
                    "trigger_value": round(float(row["close"]), 2),
                    "trigger_description": f"New {lookback}-day high at {row['close']:.0f}",
                })
        return results

    def _check_breakout(
        self, df: pd.DataFrame, symbol: str, days_back: int,
    ) -> list[dict]:
        """Detect Bollinger Band upper breakout with volume confirmation."""
        results = []
        if len(df) < 21:
            return results

        close = df["close"]
        ma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std()
        bb_upper = ma_20 + 2 * std_20

        vol_avg = df["volume"].rolling(20).mean()

        recent_indices = df.tail(days_back).index
        for idx in recent_indices:
            i = df.index.get_loc(idx)
            if i < 20:
                continue
            price = close.iloc[i]
            upper = bb_upper.iloc[i]
            vol = df["volume"].iloc[i]
            avg_vol = vol_avg.iloc[i]

            if price > upper and vol > avg_vol * 1.5:
                results.append({
                    "symbol": symbol,
                    "detected_date": str(df["trade_date"].iloc[i].date()),
                    "trigger_type": "breakout",
                    "trigger_value": round(float(price), 2),
                    "trigger_description": f"BB upper breakout at {price:.0f} with volume",
                })
        return results
