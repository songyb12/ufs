"""APScheduler setup — market-hours-aware job scheduling."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = logging.getLogger("vibe2.scheduler")

US_EASTERN = ZoneInfo("America/New_York")

_scheduler: BackgroundScheduler | None = None


def is_market_hours(now: datetime | None = None) -> bool:
    """Check if US stock market is currently open (9:30-16:00 ET, weekdays)."""
    now = now or datetime.now(US_EASTERN)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def is_extended_hours(now: datetime | None = None) -> bool:
    """Check if within pre-market (4:00-9:30) or after-hours (16:00-20:00)."""
    now = now or datetime.now(US_EASTERN)
    if now.weekday() >= 5:
        return False
    hour_min = now.hour * 60 + now.minute
    pre_market = 4 * 60 <= hour_min < 9 * 60 + 30
    after_hours = 16 * 60 <= hour_min < 20 * 60
    return pre_market or after_hours


# ---------------------------------------------------------------------------
# Job functions
# ---------------------------------------------------------------------------


def job_collect_and_signal() -> None:
    """Collect all data and run signal pipeline. Market hours only."""
    if not is_market_hours():
        logger.debug("Skipping collect_and_signal — market closed")
        return

    logger.info("[Job] collect_and_signal start")
    try:
        from app.collector import collect_all
        from app.engine.signal import run_signal_pipeline

        collect_all()
        result = run_signal_pipeline()
        logger.info("[Job] collect_and_signal done: %s (%.3f)", result.signal.value, result.score)
    except Exception as e:
        logger.error("[Job] collect_and_signal failed: %s", e, exc_info=True)


def job_generate_briefing() -> None:
    """Run pipeline and generate briefing. Called once after market close."""
    logger.info("[Job] generate_briefing start")
    try:
        from app.briefing.generator import generate_briefing
        from app.engine.signal import run_signal_pipeline

        signal = run_signal_pipeline()
        briefing = generate_briefing(signal)
        logger.info("[Job] generate_briefing done: %s", briefing.commentary[:50] if briefing.commentary else "N/A")
    except Exception as e:
        logger.error("[Job] generate_briefing failed: %s", e, exc_info=True)


def job_macro_only() -> None:
    """Collect macro data only. For off-hours monitoring."""
    logger.info("[Job] macro_only start")
    try:
        from app.collector.macro import collect_all_macro

        rows = collect_all_macro(days=10)
        logger.info("[Job] macro_only done: %d rows", rows)
    except Exception as e:
        logger.error("[Job] macro_only failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------


def start_scheduler() -> None:
    """Register jobs and start the BackgroundScheduler."""
    global _scheduler
    _scheduler = BackgroundScheduler(timezone=US_EASTERN)

    # Market hours: collect + signal every 30 min (weekdays only)
    _scheduler.add_job(
        job_collect_and_signal,
        IntervalTrigger(minutes=settings.UPDATE_INTERVAL_MINUTES),
        id="collect_and_signal",
        replace_existing=True,
    )

    # After market close: 16:05 ET weekdays — generate daily briefing
    _scheduler.add_job(
        job_generate_briefing,
        CronTrigger(hour=16, minute=5, day_of_week="mon-fri", timezone=US_EASTERN),
        id="daily_briefing",
        replace_existing=True,
    )

    # Off-hours: macro data every 4 hours
    _scheduler.add_job(
        job_macro_only,
        IntervalTrigger(hours=4),
        id="macro_only",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started: signal every %dm, briefing at 16:05 ET, macro every 4h",
        settings.UPDATE_INTERVAL_MINUTES,
    )


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
