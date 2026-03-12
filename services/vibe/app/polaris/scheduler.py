"""POLARIS Scheduler Jobs — Periodic news collection and event processing.

Registers with VIBE's existing APScheduler to run:
1. News scan: Fetch + classify news for all active figures (every 6h)
2. Prediction refresh: Re-run predictions for figures with new events (daily)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import partial

from app.config import settings

logger = logging.getLogger("vibe.polaris.scheduler")


async def polaris_news_scan() -> dict:
    """Fetch and classify news for all active figures.

    Flow:
    1. Get all active figures
    2. Fetch news via Google RSS
    3. Classify events (LLM or rule-based)
    4. Store significant events in DB
    5. Update profiles if needed
    """
    from app.polaris import repository as polaris_repo
    from app.polaris.collectors.event_detector import classify_news_batch
    from app.polaris.collectors.llm_extractor import extract_profile_update
    from app.polaris.collectors.news import fetch_figure_news
    from app.polaris.profile.engine import update_profile_from_event

    figures = await polaris_repo.get_figures(status="active")
    if not figures:
        logger.info("POLARIS: No active figures registered, skipping news scan")
        return {"scanned": 0, "events_created": 0}

    total_events = 0
    profile_updates = 0

    for figure in figures:
        figure_id = figure["id"]
        figure_name = figure["name"]

        try:
            # 1. Fetch news
            articles = await fetch_figure_news(
                figure_name=figure_name,
                country=figure.get("country", "US"),
                max_articles=10,
            )
            if not articles:
                continue

            # 2. Classify events
            events = await classify_news_batch(
                figure_name=figure_name,
                articles=articles,
                min_significance=2,
            )

            # 3. Store events
            for event in events:
                await polaris_repo.insert_event(
                    figure_id=figure_id,
                    event_type=event.get("event_type", "statement"),
                    title=event.get("article_title", ""),
                    summary=event.get("summary", ""),
                    raw_content=event.get("market_relevance", ""),
                    source_url=event.get("article_url", ""),
                    event_date=event.get("article_published", ""),
                    significance=event.get("significance", 2),
                    categories=event.get("categories", []),
                )
                total_events += 1

                # 4. Check if profile update needed
                if event.get("profile_update_needed") and event.get("significance", 0) >= 4:
                    try:
                        update_result = await extract_profile_update(
                            figure_name=figure_name,
                            current_profile=(await polaris_repo.get_latest_profile(figure_id) or {}).get("profile_data", {}),
                            new_event_summary=event.get("summary", ""),
                        )
                        if update_result.get("should_update"):
                            await update_profile_from_event(
                                figure_id=figure_id,
                                event_summary=event.get("summary", ""),
                                updated_fields=update_result.get("updated_fields", {}),
                                changelog=update_result.get("changelog", ""),
                            )
                            profile_updates += 1
                    except Exception as e:
                        logger.warning("Profile update failed for %s: %s", figure_name, e)

            logger.info("POLARIS: %s — %d articles → %d events",
                        figure_name, len(articles), len(events))

        except Exception as e:
            logger.error("POLARIS news scan failed for %s: %s", figure_name, e, exc_info=True)

    result = {
        "scanned": len(figures),
        "events_created": total_events,
        "profile_updates": profile_updates,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("POLARIS news scan complete: %s", result)
    return result


async def polaris_prediction_refresh() -> dict:
    """Re-run predictions for figures with recent significant events.

    Flow:
    1. Check which figures have events since last prediction
    2. For each, run the agentic analyzer
    3. Store new predictions
    """
    from app.polaris import repository as polaris_repo
    from app.polaris.analysis.behavior_analyzer import run_prediction
    from app.polaris.profile.engine import get_current_profile

    figures = await polaris_repo.get_figures(status="active")
    if not figures:
        return {"figures_analyzed": 0, "predictions_generated": 0}

    total_predictions = 0

    for figure in figures:
        figure_id = figure["id"]
        figure_name = figure["name"]

        try:
            # Check if there are recent events (significance >= 3)
            events = await polaris_repo.get_events(figure_id, limit=5, min_significance=3)
            if not events:
                continue

            profile = await get_current_profile(figure_id)
            if not profile:
                continue

            # Build context from recent events
            event_context = "\n".join(
                f"- [{e.get('event_type', '?')}] {e.get('title', '')} "
                f"(중요도: {e.get('significance', '?')})"
                for e in events[:5]
            )

            result = await run_prediction(
                figure_name=figure_name,
                profile_data=profile["profile_data"],
                topic="최근 이벤트 기반 행동 예측",
                extra_context=f"## 최근 주요 이벤트\n{event_context}",
                figure_id=figure_id,
            )

            if result["status"] == "ok":
                for pred in result.get("predictions", []):
                    await polaris_repo.insert_prediction(
                        figure_id=figure_id,
                        prediction_type=pred.get("type", "action"),
                        prediction=pred.get("prediction", ""),
                        reasoning=pred.get("reasoning", ""),
                        confidence=pred.get("confidence", 0.5),
                        timeframe=pred.get("timeframe", "short"),
                        market_impact=pred.get("market_impact"),
                    )
                    total_predictions += 1

            logger.info("POLARIS: %s — %d new predictions",
                        figure_name, len(result.get("predictions", [])))

        except Exception as e:
            logger.error("POLARIS prediction refresh failed for %s: %s",
                         figure_name, e, exc_info=True)

    result = {
        "figures_analyzed": len(figures),
        "predictions_generated": total_predictions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("POLARIS prediction refresh complete: %s", result)
    return result


def register_polaris_jobs(scheduler, config) -> None:
    """Register POLARIS jobs with the VIBE scheduler.

    Called from main.py during lifespan startup.
    """
    # News scan every 6 hours (00, 06, 12, 18 UTC)
    scheduler.add_job(
        partial(polaris_news_scan),
        "cron",
        hour="0,6,12,18",
        minute=30,
        id="polaris_news_scan",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Prediction refresh daily at 07:30 UTC (after KR market pipeline)
    scheduler.add_job(
        partial(polaris_prediction_refresh),
        "cron",
        hour=7,
        minute=30,
        id="polaris_prediction_refresh",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    logger.info("POLARIS scheduler jobs registered (news_scan 6h, prediction_refresh daily)")
