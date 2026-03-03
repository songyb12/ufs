"""APScheduler setup for automated pipeline runs."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Settings

logger = logging.getLogger("vibe.scheduler")


def create_scheduler(config: Settings) -> AsyncIOScheduler:
    """Create and configure the scheduler (does not start it)."""
    scheduler = AsyncIOScheduler(
        job_defaults={
            "coalesce": True,       # Combine missed runs into one
            "max_instances": 1,     # Only one instance per job at a time
            "misfire_grace_time": 3600,  # Allow 1h late execution
        },
    )
    return scheduler
