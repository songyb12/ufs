"""Stage 2b: Fundamental Analysis - Compute fundamental scores."""

import logging
from typing import Any

from app.config import Settings
from app.database import repositories as repo
from app.indicators.fundamental import (
    compute_fundamental_score,
    fetch_fundamental_data_yfinance,
)
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s2b")


class FundamentalAnalysisStage(BaseStage):
    """Stage 2b: Fetch fundamental data and compute scores."""

    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s2b_fundamental_analysis"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return "s1_data_collection" in context

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        symbols = context.get("symbols", [])
        per_symbol: dict[str, dict] = {}
        warnings = []
        errors = []

        for symbol in symbols:
            try:
                # Fetch from yfinance
                raw_data = await fetch_fundamental_data_yfinance(symbol, market)

                if not raw_data:
                    warnings.append(f"{symbol}: no fundamental data available")
                    per_symbol[symbol] = {
                        "fundamental_score": 0,
                        "value_score": 0,
                        "quality_score": 0,
                    }
                    continue

                # Compute scores
                result = compute_fundamental_score(raw_data, market)
                per_symbol[symbol] = result

                # Store to DB
                trade_date = context.get("date", "")
                await repo.upsert_fundamental_data({
                    "symbol": symbol,
                    "market": market,
                    "trade_date": trade_date,
                    "per": raw_data.get("per"),
                    "pbr": raw_data.get("pbr"),
                    "eps": raw_data.get("eps"),
                    "roe": raw_data.get("roe"),
                    "operating_margin": raw_data.get("operating_margin"),
                    "div_yield": raw_data.get("div_yield"),
                    "market_cap": raw_data.get("market_cap"),
                    "fundamental_score": result["fundamental_score"],
                    "value_score": result["value_score"],
                    "quality_score": result["quality_score"],
                })

                logger.debug(
                    "[S2b] %s: fund=%+.1f (val=%+.1f, qual=%+.1f)",
                    symbol, result["fundamental_score"],
                    result["value_score"], result["quality_score"],
                )

            except Exception as e:
                logger.error("[S2b] %s: fundamental fetch failed - %s", symbol, e, exc_info=True)
                errors.append(f"{symbol}: fundamental analysis failed")
                per_symbol[symbol] = {
                    "fundamental_score": 0,
                    "value_score": 0,
                    "quality_score": 0,
                }

        logger.info(
            "[S2b] Fundamental analysis for %d/%d symbols",
            len([s for s in per_symbol.values() if s.get("fundamental_score", 0) != 0]),
            len(symbols),
        )

        return StageResult(
            stage_name=self.name,
            status="success" if per_symbol else "partial",
            data={"per_symbol": per_symbol},
            errors=errors,
            warnings=warnings,
        )
