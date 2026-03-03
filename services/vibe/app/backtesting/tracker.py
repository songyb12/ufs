"""Signal Performance Tracker - Tracks T+1/5/20 returns for live signals."""

import logging
from datetime import datetime, timedelta

from app.database import repositories as repo

logger = logging.getLogger("vibe.backtest.tracker")


class SignalPerformanceTracker:
    """Tracks performance of BUY/SELL signals over T+1, T+5, T+20 periods."""

    async def create_performance_record(
        self, run_id: str, symbol: str, market: str,
        signal_date: str, signal_type: str, signal_score: float,
        entry_price: float,
    ) -> None:
        """Create initial performance tracking record when a signal is generated."""
        if signal_type not in ("BUY", "SELL"):
            return  # Only track actionable signals

        signal_id = await repo.get_signal_id_for_performance(run_id, symbol, market)
        if signal_id is None:
            logger.warning("Signal not found for performance tracking: %s %s", symbol, run_id[:8])
            return

        await repo.insert_signal_performance({
            "signal_id": signal_id,
            "symbol": symbol,
            "market": market,
            "signal_date": signal_date,
            "signal_type": signal_type,
            "signal_score": signal_score,
            "entry_price": entry_price,
        })
        logger.debug("Performance record created: %s %s %s", symbol, signal_type, signal_date)

    async def track_pending(self) -> int:
        """Update performance records that have pending T+1/5/20 data.

        Returns number of records updated.
        """
        pending = await repo.get_pending_performance_tracking()
        if not pending:
            return 0

        updated = 0
        today = datetime.utcnow().strftime("%Y-%m-%d")

        for record in pending:
            signal_date = record["signal_date"]
            symbol = record["symbol"]
            market = record["market"]
            entry_price = record["entry_price"]
            signal_type = record["signal_type"]

            updates = {}

            # T+1
            if record.get("return_t1") is None:
                t1_date = self._add_trading_days(signal_date, 1)
                if t1_date <= today:
                    price = await repo.get_price_at_date(symbol, market, t1_date)
                    if price:
                        updates["price_t1"] = price["close"]
                        updates["return_t1"] = round(
                            (price["close"] - entry_price) / entry_price * 100, 4
                        )

            # T+5
            if record.get("return_t5") is None:
                t5_date = self._add_trading_days(signal_date, 5)
                if t5_date <= today:
                    price = await repo.get_price_at_date(symbol, market, t5_date)
                    if price:
                        updates["price_t5"] = price["close"]
                        ret = (price["close"] - entry_price) / entry_price * 100
                        updates["return_t5"] = round(ret, 4)
                        # Correct if BUY went up or SELL went down
                        if signal_type == "BUY":
                            updates["is_correct_t5"] = 1 if ret > 0 else 0
                        else:
                            updates["is_correct_t5"] = 1 if ret < 0 else 0

            # T+20
            if record.get("return_t20") is None:
                t20_date = self._add_trading_days(signal_date, 20)
                if t20_date <= today:
                    price = await repo.get_price_at_date(symbol, market, t20_date)
                    if price:
                        updates["price_t20"] = price["close"]
                        ret = (price["close"] - entry_price) / entry_price * 100
                        updates["return_t20"] = round(ret, 4)
                        if signal_type == "BUY":
                            updates["is_correct_t20"] = 1 if ret > 0 else 0
                        else:
                            updates["is_correct_t20"] = 1 if ret < 0 else 0

            if updates:
                await repo.update_signal_performance(record["signal_id"], updates)
                updated += 1

        logger.info("Performance tracker updated %d/%d records", updated, len(pending))
        return updated

    async def get_hit_rate_summary(
        self, market: str | None = None, lookback_days: int = 90,
    ) -> dict:
        """Get hit rate summary for signals in the last N days."""
        since_date = (
            datetime.utcnow() - timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")
        return await repo.get_performance_summary(market=market, since_date=since_date)

    @staticmethod
    def _add_trading_days(date_str: str, days: int) -> str:
        """Approximate trading days by adding calendar days * 1.5."""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Rough approximation: 1 trading day ≈ 1.4 calendar days
        calendar_days = int(days * 1.4) + 1
        result = dt + timedelta(days=calendar_days)
        return result.strftime("%Y-%m-%d")
