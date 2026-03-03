"""Stage 4b: US Fund Flow - ETF flow proxy, short interest (US market only)."""

import logging
from typing import Any

from app.collectors.us_fund_flow import fetch_etf_flow_proxy, fetch_short_interest
from app.config import Settings
from app.database import repositories as repo
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s4b")


class USFundFlowStage(BaseStage):
    """Stage 4b: US market fund flow analysis."""

    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s4b_us_fund_flow"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return (
            context.get("market") == "US"
            and self.config.US_FUND_FLOW_ENABLED
        )

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        symbols = context.get("symbols", [])
        warnings = []
        per_symbol: dict[str, dict] = {}

        # ETF flow proxy (market-wide)
        etf_data = {}
        try:
            etf_data = await fetch_etf_flow_proxy()
            risk_appetite = etf_data.get("risk_appetite", "neutral")
            logger.info("[S4b] ETF flow: risk_appetite=%s", risk_appetite)
        except Exception as e:
            warnings.append(f"ETF flow fetch failed: {e}")

        # Short interest per symbol
        for symbol in symbols:
            try:
                short_data = await fetch_short_interest(symbol)
                if short_data:
                    # Score short interest
                    si_score = _score_short_interest(short_data)
                    per_symbol[symbol] = {
                        **short_data,
                        "short_interest_score": si_score,
                    }

                    # Store to DB
                    trade_date = context.get("date", "")
                    await repo.insert_us_fund_flow({
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "data_type": "short_interest",
                        "value": short_data.get("short_pct_float", 0),
                        "description": f"Short ratio: {short_data.get('short_ratio', 'N/A')}",
                        "source": "yfinance",
                    })
                else:
                    per_symbol[symbol] = {"short_interest_score": 0}
            except Exception as e:
                warnings.append(f"{symbol}: short interest failed - {e}")
                per_symbol[symbol] = {"short_interest_score": 0}

        logger.info("[S4b] US fund flow for %d symbols", len(per_symbol))

        return StageResult(
            stage_name=self.name,
            status="success" if per_symbol else "partial",
            data={
                "per_symbol": per_symbol,
                "etf_flow": etf_data,
                "risk_appetite": etf_data.get("risk_appetite", "neutral"),
            },
            warnings=warnings,
        )


def _score_short_interest(data: dict) -> float:
    """Score short interest data. Range: -50 to +50.

    High short interest = potential short squeeze = bullish
    Rising short interest = bearish pressure
    """
    score = 0.0

    short_pct = data.get("short_pct_float", 0)
    if short_pct > 20:
        score += 30  # Very high short = squeeze potential
    elif short_pct > 10:
        score += 15
    elif short_pct > 5:
        score += 5

    # Short change direction
    change_pct = data.get("short_change_pct", 0)
    if change_pct > 20:
        score -= 15  # Rising shorts = bearish
    elif change_pct < -20:
        score += 15  # Shorts covering = bullish

    return round(max(-50, min(50, score)), 2)
