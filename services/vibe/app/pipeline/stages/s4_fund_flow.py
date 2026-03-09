"""Stage 4: Fund Flow Analysis - KR market investor trends (외국인/기관 수급)."""

import asyncio
import logging
from typing import Any

from app.collectors.kr_market import KRMarketCollector
from app.collectors.registry import CollectorRegistry
from app.config import Settings
from app.database import repositories as repo
from app.indicators.scoring import compute_fund_flow_score
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s4")


class FundFlowStage(BaseStage):
    def __init__(self, config: Settings, collector_registry: CollectorRegistry):
        self.config = config
        self.registry = collector_registry

    @property
    def name(self) -> str:
        return "s4_fund_flow"

    def validate_input(self, context: dict[str, Any]) -> bool:
        # Only run for KR market
        return context.get("market") == "KR"

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        if market != "KR":
            return StageResult(
                stage_name=self.name,
                status="skipped",
                data={"reason": "Fund flow data only available for KR market"},
            )

        symbols = context.get("symbols", [])
        collector = self.registry.get("KR")

        if not isinstance(collector, KRMarketCollector):
            return StageResult(
                stage_name=self.name,
                status="failed",
                errors=["KR collector not available"],
            )

        from app.collectors.base import BaseCollector
        start_date = BaseCollector._default_start_date(20)  # Last 20 days
        end_date = BaseCollector._today()

        per_symbol: dict[str, dict] = {}
        errors = []

        for symbol in symbols:
            try:
                df = await collector.fetch_fund_flow(symbol, start_date, end_date)
                if df is None or df.empty:
                    continue

                # Get latest row
                latest = df.iloc[-1]
                flow_data = {
                    "foreign_net_buy": float(latest.get("foreign_net_buy", 0)),
                    "institution_net_buy": float(latest.get("institution_net_buy", 0)),
                    "individual_net_buy": float(latest.get("individual_net_buy", 0)),
                }

                score = compute_fund_flow_score(flow_data)
                per_symbol[symbol] = {
                    **flow_data,
                    "fund_flow_score": score,
                }

                # Store to DB
                rows = [
                    {
                        "symbol": symbol,
                        "trade_date": date_str,
                        "foreign_net_buy": float(row.get("foreign_net_buy", 0)),
                        "institution_net_buy": float(row.get("institution_net_buy", 0)),
                        "individual_net_buy": float(row.get("individual_net_buy", 0)),
                        "pension_net_buy": None,
                        "foreign_holding_ratio": None,
                    }
                    for date_str, row in df.iterrows()
                ]
                await repo.upsert_fund_flow_kr(rows)

                await asyncio.sleep(self.config.COLLECTION_DELAY_SECONDS)

            except Exception as e:
                logger.error("[S4] %s: fund flow fetch failed - %s", symbol, e, exc_info=True)
                errors.append(f"{symbol}: fund flow fetch failed")

        logger.info("[S4] Fund flow analyzed for %d/%d symbols", len(per_symbol), len(symbols))

        return StageResult(
            stage_name=self.name,
            status="success" if per_symbol else "partial",
            data={"per_symbol": per_symbol},
            errors=errors,
        )
