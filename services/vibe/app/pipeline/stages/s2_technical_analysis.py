"""Stage 2: Technical Analysis - Compute indicators from price data."""

import logging
from typing import Any

import pandas as pd

from app.config import Settings
from app.database import repositories as repo
from app.indicators.technical import compute_all_indicators
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s2")


class TechnicalAnalysisStage(BaseStage):
    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s2_technical_analysis"

    def validate_input(self, context: dict[str, Any]) -> bool:
        s1 = context.get("s1_data_collection")
        return s1 is not None and s1.status in ("success", "partial")

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        s1_data = context["s1_data_collection"].data
        ohlcv_data = s1_data.get("ohlcv_data", {})

        per_symbol: dict[str, dict] = {}
        errors = []

        for symbol, df in ohlcv_data.items():
            try:
                if not isinstance(df, pd.DataFrame) or df.empty:
                    logger.warning("[S2] %s: invalid OHLCV data (type=%s)", symbol, type(df).__name__)
                    errors.append(f"{symbol}: invalid DataFrame")
                    continue

                # Ensure sorted ascending by date
                df = df.sort_index()

                indicators = compute_all_indicators(df)
                if not indicators:
                    logger.warning("[S2] %s: insufficient data for indicators", symbol)
                    continue

                # Add close price for scoring reference
                indicators["close"] = float(df["close"].iloc[-1])
                per_symbol[symbol] = indicators

                # Store latest to DB
                trade_date = df.index[-1]
                await repo.upsert_technical_indicators([{
                    "symbol": symbol,
                    "market": market,
                    "trade_date": trade_date,
                    **indicators,
                }])

            except Exception as e:
                logger.error("[S2] %s: indicator computation failed - %s", symbol, e)
                errors.append(f"{symbol}: {e}")

        logger.info(
            "[S2] Computed indicators for %d/%d symbols",
            len(per_symbol), len(ohlcv_data),
        )

        return StageResult(
            stage_name=self.name,
            status="success" if per_symbol else "failed",
            data={"per_symbol": per_symbol},
            errors=errors,
        )
