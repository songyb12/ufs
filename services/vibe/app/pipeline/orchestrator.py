"""Pipeline Orchestrator - Runs all 7 stages sequentially."""

import logging
import time
from datetime import date
from typing import Any
from uuid import uuid4

from app.collectors.registry import CollectorRegistry
from app.config import Settings
from app.database import repositories as repo
from app.pipeline.base import BaseStage, StageResult
from app.pipeline.stages.s1_data_collection import DataCollectionStage
from app.pipeline.stages.s2_technical_analysis import TechnicalAnalysisStage
from app.pipeline.stages.s3_macro_analysis import MacroAnalysisStage
from app.pipeline.stages.s4_fund_flow import FundFlowStage
from app.pipeline.stages.s5_hard_limit import HardLimitStage
from app.pipeline.stages.s6_signal_generation import SignalGenerationStage
from app.pipeline.stages.s6b_risk_sizing import RiskSizingStage
from app.pipeline.stages.s7_red_team import RedTeamStage

logger = logging.getLogger("vibe.pipeline")


class PipelineOrchestrator:
    def __init__(self, config: Settings, collector_registry: CollectorRegistry):
        self.config = config
        self.stages: list[BaseStage] = [
            DataCollectionStage(config, collector_registry),
            TechnicalAnalysisStage(config),
            MacroAnalysisStage(config),
            FundFlowStage(config, collector_registry),
            HardLimitStage(config),
            SignalGenerationStage(config),
            RiskSizingStage(config),
            RedTeamStage(config),
        ]

    async def run(
        self,
        market: str,
        symbols: list[str],
        run_type: str = "manual",
    ) -> dict[str, Any]:
        """Execute the full 7-stage pipeline.

        Returns context dict with all stage results.
        """
        run_id = str(uuid4())
        start_time = time.time()

        # Fetch symbol -> name mapping for display
        symbol_names = await repo.get_symbol_names(market)

        context: dict[str, Any] = {
            "market": market,
            "symbols": symbols,
            "run_id": run_id,
            "date": date.today().strftime("%Y-%m-%d"),
            "symbol_names": symbol_names,
        }

        logger.info(
            "Pipeline started: run_id=%s market=%s symbols=%d type=%s",
            run_id[:8], market, len(symbols), run_type,
        )

        await repo.insert_pipeline_run(run_id, market, run_type)

        completed_stages: list[str] = []
        try:
            for stage in self.stages:
                # Check if stage should run
                if not stage.validate_input(context):
                    logger.info("Stage %s skipped (validation)", stage.name)
                    continue

                # Execute stage
                logger.info("Stage %s starting...", stage.name)
                stage_start = time.time()

                result = await stage.execute(context, market)
                context[stage.name] = result
                completed_stages.append(stage.name)

                elapsed = time.time() - stage_start
                logger.info(
                    "Stage %s completed: status=%s (%.1fs)",
                    stage.name, result.status, elapsed,
                )

                # Log warnings
                for w in result.warnings:
                    logger.warning("  [%s] %s", stage.name, w)

                # Stop on critical failure
                if result.status == "failed":
                    error_msg = f"Stage {stage.name} failed: {result.errors}"
                    logger.error(error_msg)
                    await repo.update_pipeline_run(
                        run_id, "failed", completed_stages, error_msg,
                    )
                    context["status"] = "failed"
                    context["error"] = error_msg
                    return context

            # Pipeline completed successfully
            total_elapsed = time.time() - start_time
            context["elapsed"] = total_elapsed
            context["status"] = "completed"

            await repo.update_pipeline_run(run_id, "completed", completed_stages)

            # Store signals to DB
            await self._store_signals(context)

            logger.info(
                "Pipeline completed: run_id=%s elapsed=%.1fs stages=%d",
                run_id[:8], total_elapsed, len(completed_stages),
            )

        except Exception as e:
            logger.exception("Pipeline failed with exception: %s", e)
            await repo.update_pipeline_run(
                run_id, "failed", completed_stages, str(e),
            )
            context["status"] = "failed"
            context["error"] = str(e)
            raise

        return context

    async def _store_signals(self, context: dict[str, Any]) -> None:
        """Extract final signals from S7 (or S6 fallback) and store to DB."""
        s7 = context.get("s7_red_team")
        s6 = context.get("s6_signal_generation")

        # Prefer S7 output (has confidence + red_team_warning)
        source = s7 if s7 and s7.status == "success" else s6
        if not source:
            return

        per_symbol = source.data.get("per_symbol", {})
        signal_rows = []

        for symbol, data in per_symbol.items():
            signal_rows.append({
                "run_id": context["run_id"],
                "symbol": symbol,
                "market": context["market"],
                "signal_date": context["date"],
                "raw_signal": data["raw_signal"],
                "raw_score": data["raw_score"],
                "hard_limit_triggered": data.get("hard_limit_triggered", False),
                "hard_limit_reason": data.get("hard_limit_reason"),
                "final_signal": data["final_signal"],
                "confidence": data.get("confidence"),
                "red_team_warning": data.get("red_team_warning"),
                "rsi_value": data.get("rsi_value"),
                "disparity_value": data.get("disparity_value"),
                "macro_score": data.get("macro_score"),
                "technical_score": data.get("technical_score"),
                "fund_flow_score": data.get("fund_flow_score"),
                "rationale": data.get("rationale"),
            })

        if signal_rows:
            count = await repo.insert_signals(signal_rows)
            logger.info("Stored %d signals to DB", count)

            # Seed performance tracking records for BUY/SELL signals
            if self.config.PERFORMANCE_TRACKING_ENABLED:
                from app.backtesting.tracker import SignalPerformanceTracker

                tracker = SignalPerformanceTracker()
                s1 = context.get("s1_data_collection")
                for row in signal_rows:
                    if row["final_signal"] in ("BUY", "SELL"):
                        entry_price = None
                        if s1 and s1.data.get("ohlcv_data"):
                            ohlcv_df = s1.data["ohlcv_data"].get(row["symbol"])
                            if ohlcv_df is not None and not ohlcv_df.empty:
                                entry_price = float(ohlcv_df.iloc[-1]["close"])
                        if entry_price:
                            await tracker.create_performance_record(
                                run_id=row["run_id"],
                                symbol=row["symbol"],
                                market=row["market"],
                                signal_date=row["signal_date"],
                                signal_type=row["final_signal"],
                                signal_score=row["raw_score"],
                                entry_price=entry_price,
                            )
