"""SOXL Briefing Scheduler — daily briefing generation via APScheduler.

Runs at 12:30 UTC (21:30 KST, before US market open) each day.
On failure, retries up to 3 times at 10-minute intervals.
"""

import asyncio
import functools
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("vibe.soxl_briefing.scheduler")

_MAX_RETRIES = 3
_RETRY_DELAY_SEC = 600  # 10 minutes


async def _run_with_retry() -> None:
    """Execute briefing generation with retry logic."""
    from app.soxl_briefing.generator import generate_soxl_briefing

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info("SOXL briefing generation attempt %d/%d", attempt, _MAX_RETRIES)
            result = await generate_soxl_briefing()

            if result["status"] == "ok":
                logger.info("SOXL briefing generated successfully")
                return
            else:
                logger.warning(
                    "SOXL briefing returned status=%s (attempt %d/%d): %s",
                    result["status"], attempt, _MAX_RETRIES,
                    result.get("metadata", {}).get("error", "unknown"),
                )
        except Exception as e:
            logger.error(
                "SOXL briefing attempt %d/%d failed: %s",
                attempt, _MAX_RETRIES, e, exc_info=True,
            )

        if attempt < _MAX_RETRIES:
            logger.info("Retrying in %d seconds...", _RETRY_DELAY_SEC)
            await asyncio.sleep(_RETRY_DELAY_SEC)

    logger.error("SOXL briefing generation failed after %d attempts", _MAX_RETRIES)


def register_briefing_job(scheduler: AsyncIOScheduler) -> None:
    """Register the daily SOXL briefing job on the given scheduler.

    Schedule: 12:30 UTC daily (21:30 KST / 07:30 EST).
    """
    scheduler.add_job(
        _run_with_retry,
        trigger="cron",
        hour=12,
        minute=30,
        id="soxl_daily_briefing",
        name="SOXL Daily Briefing",
        replace_existing=True,
    )
    logger.info("SOXL daily briefing job registered (12:30 UTC)")
