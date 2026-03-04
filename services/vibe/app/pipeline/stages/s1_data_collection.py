"""Stage 1: Data Collection - Fetch OHLCV and store to DB."""

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from app.collectors.registry import CollectorRegistry
from app.config import Settings
from app.database import repositories as repo
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s1")


class DataCollectionStage(BaseStage):
    def __init__(self, config: Settings, collector_registry: CollectorRegistry):
        self.config = config
        self.registry = collector_registry

    @property
    def name(self) -> str:
        return "s1_data_collection"

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        symbols = context.get("symbols", [])
        if not symbols:
            return StageResult(
                stage_name=self.name,
                status="failed",
                errors=["No symbols provided"],
            )

        collector = self.registry.get(market)
        start_date = collector._default_start_date(self.config.PRICE_HISTORY_DAYS)
        end_date = collector._today()

        logger.info("[S1] Collecting %s data for %d symbols", market, len(symbols))

        # Fetch OHLCV
        ohlcv_data = await collector.fetch_ohlcv_batch(symbols, start_date, end_date)

        # Store to DB
        total_rows = 0
        collected_symbols = []
        for symbol, df in ohlcv_data.items():
            rows = [
                {
                    "symbol": symbol,
                    "market": market,
                    "trade_date": date_str,
                    "open": float(row.get("open", 0)) if row.get("open") is not None else None,
                    "high": float(row.get("high", 0)) if row.get("high") is not None else None,
                    "low": float(row.get("low", 0)) if row.get("low") is not None else None,
                    "close": float(row["close"]),
                    "volume": int(row.get("volume", 0)) if row.get("volume") is not None else None,
                }
                for date_str, row in df.iterrows()
            ]
            count = await repo.upsert_price_history(rows)
            total_rows += count
            collected_symbols.append(symbol)

        # Collect macro data (shared, run once)
        macro_data = None
        if "macro_data" not in context:
            try:
                macro_data = await self.registry.macro.collect()
                await repo.upsert_macro_indicators(macro_data)
                logger.info("[S1] Macro data collected and stored")
            except Exception as e:
                logger.error("[S1] Macro collection failed: %s", e)

        failed_symbols = [s for s in symbols if s not in collected_symbols]

        # Stale data detection: warn if latest data is older than 5 trading days
        stale_warnings = []
        now = datetime.now()
        stale_cutoff = now - timedelta(days=7)  # ~5 trading days
        for symbol, df in ohlcv_data.items():
            if df is not None and not df.empty:
                latest_date = pd.to_datetime(df.index[-1])
                if latest_date < stale_cutoff:
                    days_old = (now - latest_date).days
                    stale_warnings.append(f"{symbol}: {days_old}d old")
        if stale_warnings:
            logger.warning(
                "[S1] Stale data (%d symbols): %s",
                len(stale_warnings), ", ".join(stale_warnings[:10]),
            )

        status = "success" if not failed_symbols else "partial"

        result_data: dict[str, Any] = {
            "collected_symbols": collected_symbols,
            "failed_symbols": failed_symbols,
            "total_rows": total_rows,
            "ohlcv_data": ohlcv_data,  # Pass raw DataFrames to next stage
            "stale_symbols": [w.split(":")[0] for w in stale_warnings],
        }
        if macro_data:
            result_data["macro_data"] = macro_data

        return StageResult(
            stage_name=self.name,
            status=status,
            data=result_data,
            errors=[f"Failed to collect: {s}" for s in failed_symbols],
        )
