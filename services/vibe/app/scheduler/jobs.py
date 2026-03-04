"""Scheduled job definitions for VIBE pipeline."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.backtesting.tracker import SignalPerformanceTracker
from app.collectors.registry import CollectorRegistry
from app.config import Settings
from app.database import repositories as repo
from app.notifier.discord import DiscordNotifier
from app.pipeline.orchestrator import PipelineOrchestrator
from app.utils.backup import backup_database

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

    # Signal performance tracking (1 hour after KR pipeline)
    if config.PERFORMANCE_TRACKING_ENABLED:
        async def track_signal_performance():
            try:
                tracker = SignalPerformanceTracker()
                updated = await tracker.track_pending()
                logger.info("Signal performance tracker: updated %d records", updated)
            except Exception as e:
                logger.exception("Signal performance tracking failed: %s", e)

        scheduler.add_job(
            track_signal_performance,
            trigger="cron",
            hour=(config.KR_PIPELINE_HOUR_UTC + 1) % 24,
            minute=0,
            id="signal_performance_tracker",
            name="Signal Performance Tracker",
            replace_existing=True,
        )

    # Daily database backup (04:00 UTC = 13:00 KST, before any pipeline)
    async def run_db_backup():
        try:
            result = await backup_database(
                db_path=config.DB_PATH,
                backup_dir=config.DB_BACKUP_DIR,
                keep_days=config.DB_BACKUP_KEEP_DAYS,
            )
            if result:
                logger.info("Scheduled backup completed: %s", result)
            else:
                logger.error("Scheduled backup failed")
        except Exception as e:
            logger.exception("Backup job failed: %s", e)

    scheduler.add_job(
        run_db_backup,
        trigger="cron",
        hour=4,
        minute=0,
        id="daily_db_backup",
        name="Daily DB Backup",
        replace_existing=True,
    )

    # Weekly report (Sunday 06:00 UTC = 15:00 KST)
    async def send_weekly_report():
        try:
            from app.notifier.weekly_report import build_weekly_report_payloads

            payloads = await build_weekly_report_payloads()
            if payloads and config.DISCORD_WEBHOOK_URL:
                import asyncio
                import httpx

                async with httpx.AsyncClient() as client:
                    for payload in payloads:
                        resp = await client.post(
                            config.DISCORD_WEBHOOK_URL,
                            json=payload,
                            timeout=15.0,
                        )
                        if resp.status_code == 204:
                            logger.info("Weekly report sent to Discord")
                        else:
                            logger.error("Weekly report Discord failed: %d", resp.status_code)
                        await asyncio.sleep(1.0)
            else:
                logger.info("Weekly report generated but no webhook configured")
        except Exception as e:
            logger.exception("Weekly report failed: %s", e)

    scheduler.add_job(
        send_weekly_report,
        trigger="cron",
        day_of_week="sun",
        hour=6,
        minute=0,
        id="weekly_report",
        name="Weekly Report",
        replace_existing=True,
    )

    # Price alert check (every 2 hours during market hours)
    async def check_price_alerts():
        try:
            from app.notifier.alerts import check_and_send_alerts
            await check_and_send_alerts(config)
        except Exception as e:
            logger.exception("Price alert check failed: %s", e)

    scheduler.add_job(
        check_price_alerts,
        trigger="cron",
        hour="7,9,11,13,22",  # During KR/US market hours
        minute=30,
        id="price_alert_check",
        name="Price Alert Check",
        replace_existing=True,
    )

    # Weekly data retention cleanup (Sunday 03:00 UTC, before backup)
    async def run_data_retention():
        try:
            from app.utils.retention import run_retention
            results = await run_retention(config)
            if results:
                logger.info("Data retention completed: %s", results)
            else:
                logger.info("Data retention: no rows to prune")
        except Exception as e:
            logger.exception("Data retention failed: %s", e)

    scheduler.add_job(
        run_data_retention,
        trigger="cron",
        day_of_week="sun",
        hour=3,
        minute=0,
        id="weekly_data_retention",
        name="Weekly Data Retention",
        replace_existing=True,
    )

    # Weekly event calendar refresh (Sunday 05:00 UTC)
    async def refresh_event_calendar():
        try:
            from app.risk.events import EventCalendar
            calendar = EventCalendar(config)
            count = await calendar.seed_static_events()
            logger.info("Event calendar refreshed: %d events", count)
        except Exception as e:
            logger.exception("Event calendar refresh failed: %s", e)

    scheduler.add_job(
        refresh_event_calendar,
        trigger="cron",
        day_of_week="sun",
        hour=5,
        minute=0,
        id="weekly_event_refresh",
        name="Weekly Event Calendar Refresh",
        replace_existing=True,
    )

    logger.info(
        "Scheduler jobs registered: KR=%02d:%02d UTC, US=%02d:%02d UTC, Backup=04:00, Weekly=Sun 06:00",
        config.KR_PIPELINE_HOUR_UTC, config.KR_PIPELINE_MINUTE,
        config.US_PIPELINE_HOUR_UTC, config.US_PIPELINE_MINUTE,
    )
