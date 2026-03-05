"""Data retention - prune old records to keep DB lean."""

import logging
from datetime import datetime, timedelta, timezone

from app.database.connection import get_db

logger = logging.getLogger("vibe.utils.retention")

# Tables and their date columns for retention pruning
RETENTION_TARGETS = [
    ("price_history", "trade_date", "RETENTION_PRICE_DAYS"),
    ("technical_indicators", "trade_date", "RETENTION_PRICE_DAYS"),
    ("fundamental_data", "trade_date", "RETENTION_PRICE_DAYS"),
    ("weekly_indicators", "week_ending", "RETENTION_PRICE_DAYS"),
    ("signals", "signal_date", "RETENTION_SIGNAL_DAYS"),
    ("signal_performance", "signal_date", "RETENTION_SIGNAL_DAYS"),
    ("dashboard_snapshots", "snapshot_date", "RETENTION_SIGNAL_DAYS"),
    ("pipeline_runs", "started_at", "RETENTION_PIPELINE_RUNS_DAYS"),
    ("news_data", "trade_date", "RETENTION_NEWS_DAYS"),
    ("us_fund_flow", "trade_date", "RETENTION_NEWS_DAYS"),
    ("fund_flow_kr", "trade_date", "RETENTION_PRICE_DAYS"),
    ("sentiment_data", "indicator_date", "RETENTION_NEWS_DAYS"),
    ("macro_indicators", "indicator_date", "RETENTION_PRICE_DAYS"),
    ("portfolio_scenarios", "scenario_date", "RETENTION_NEWS_DAYS"),
    ("llm_reviews", "review_date", "RETENTION_NEWS_DAYS"),
]


async def run_retention(config) -> dict[str, int]:
    """Delete rows older than configured retention period.

    Returns: {table_name: rows_deleted}
    """
    results: dict[str, int] = {}
    db = await get_db()

    for table, date_col, config_key in RETENTION_TARGETS:
        keep_days = getattr(config, config_key, 365)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime(
            "%Y-%m-%d"
        )

        try:
            cursor = await db.execute(
                f"DELETE FROM {table} WHERE {date_col} < ?",  # noqa: S608
                (cutoff,),
            )
            deleted = cursor.rowcount
            if deleted > 0:
                results[table] = deleted
                logger.info(
                    "[Retention] %s: deleted %d rows older than %s",
                    table, deleted, cutoff,
                )
        except Exception as e:
            logger.warning("[Retention] %s: skip - %s", table, e)

    await db.commit()

    # Reclaim disk space only when significant data was pruned
    total = sum(results.values())
    if total > 1000:
        try:
            await db.execute("VACUUM")
            logger.info("[Retention] VACUUM completed (pruned %d rows)", total)
        except Exception as e:
            logger.warning("[Retention] VACUUM failed: %s", e)

    logger.info("[Retention] Total pruned: %d rows across %d tables", total, len(results))
    return results
