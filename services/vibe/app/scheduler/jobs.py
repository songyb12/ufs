"""Scheduled job definitions for VIBE pipeline."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.collectors.registry import CollectorRegistry
from app.config import Settings
from app.database import repositories as repo
from app.notifier.discord import DiscordNotifier
from app.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger("vibe.scheduler.jobs")


def register_jobs(
    scheduler: AsyncIOScheduler,
    config: Settings,
    collector_registry: CollectorRegistry,
) -> None:
    """Register all cron jobs on the scheduler."""

    orchestrator = PipelineOrchestrator(config, collector_registry)
    notifier = DiscordNotifier(config)

    async def run_market_pipeline(market: str) -> None:
        """Execute pipeline for a specific market and send Discord dashboard."""
        try:
            symbols = await repo.get_active_symbols(market)
            if not symbols:
                logger.warning("No active symbols for %s, skipping pipeline", market)
                return

            logger.info("Scheduled pipeline starting: %s (%d symbols)", market, len(symbols))
            context = await orchestrator.run(
                market=market,
                symbols=symbols,
                run_type="scheduled",
            )

            # Send Discord dashboard
            if context.get("status") == "completed":
                await notifier.send_dashboard(context)
            else:
                logger.error("Pipeline %s failed, dashboard not sent", market)

        except Exception as e:
            logger.exception("Scheduled pipeline %s failed: %s", market, e)

    # KR market pipeline (after KRX close)
    scheduler.add_job(
        lambda: run_market_pipeline("KR"),
        trigger="cron",
        hour=config.KR_PIPELINE_HOUR_UTC,
        minute=config.KR_PIPELINE_MINUTE,
        id="kr_daily_pipeline",
        name="KR Daily Pipeline",
        replace_existing=True,
    )

    # US market pipeline (after US market close)
    scheduler.add_job(
        lambda: run_market_pipeline("US"),
        trigger="cron",
        hour=config.US_PIPELINE_HOUR_UTC,
        minute=config.US_PIPELINE_MINUTE,
        id="us_daily_pipeline",
        name="US Daily Pipeline",
        replace_existing=True,
    )

    logger.info(
        "Scheduler jobs registered: KR=%02d:%02d UTC, US=%02d:%02d UTC",
        config.KR_PIPELINE_HOUR_UTC, config.KR_PIPELINE_MINUTE,
        config.US_PIPELINE_HOUR_UTC, config.US_PIPELINE_MINUTE,
    )
