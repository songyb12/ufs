"""POLARIS API Router — all endpoints for figure profiling, events, and predictions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.polaris import repository as polaris_repo
from app.polaris.collectors.llm_extractor import extract_initial_profile
from app.polaris.models import (
    EventCreate,
    FigureCreate,
    GeopoliticalAdjustmentRequest,
    NewsScanRequest,
    PredictRequest,
    PredictionOutcomeUpdate,
)
from app.polaris.profile.engine import get_current_profile, save_new_profile

logger = logging.getLogger("vibe.polaris.router")

router = APIRouter(prefix="/polaris", tags=["polaris"])


# ═══════════════════════════════════════════════════════════════
# Figures
# ═══════════════════════════════════════════════════════════════


@router.post("/figures", response_model=dict)
async def create_figure(body: FigureCreate):
    """Register a new political figure."""
    existing = await polaris_repo.get_figure_by_name(body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"이미 등록된 인물: {body.name}")
    return await polaris_repo.create_figure(
        name=body.name, name_ko=body.name_ko, role=body.role,
        country=body.country, party=body.party,
    )


@router.get("/figures", response_model=list[dict])
async def list_figures(status: str = "active"):
    """List all registered figures."""
    return await polaris_repo.get_figures(status=status)


@router.get("/figures/{figure_id}", response_model=dict)
async def get_figure(figure_id: str):
    """Get figure details with stats."""
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")

    # Attach stats
    figure["prediction_stats"] = await polaris_repo.get_prediction_stats(figure_id)
    figure["event_stats"] = await polaris_repo.get_event_stats(figure_id)
    return figure


# ═══════════════════════════════════════════════════════════════
# Profiles
# ═══════════════════════════════════════════════════════════════


@router.post("/figures/{figure_id}/init-profile", response_model=dict)
async def init_profile(figure_id: str):
    """Build initial profile using LLM knowledge extraction (10-30s)."""
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")

    existing = await get_current_profile(figure_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"프로파일이 이미 존재합니다 (v{existing['version']}). "
                   f"업데이트는 이벤트 기반으로 수행됩니다.",
        )

    result = await extract_initial_profile(
        figure_name=figure["name"],
        figure_role=figure.get("role", ""),
        figure_country=figure.get("country", ""),
    )

    if result["status"] != "ok":
        raise HTTPException(status_code=502, detail=result.get("message", "LLM 오류"))

    profile = await save_new_profile(
        figure_id=figure_id,
        profile_data=result["profile_data"],
        changelog="LLM 지식 기반 초기 프로파일 생성",
    )

    return {
        "status": "ok",
        "figure": figure["name"],
        "profile_version": profile["version"],
        "metadata": result.get("metadata", {}),
    }


@router.get("/figures/{figure_id}/profile", response_model=dict)
async def get_profile(figure_id: str):
    """Get the latest profile for a figure."""
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")

    profile = await get_current_profile(figure_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="프로파일이 없습니다. POST /init-profile로 초기 프로파일을 생성하세요.",
        )
    return profile


@router.get("/figures/{figure_id}/profile/history", response_model=list[dict])
async def get_profile_history(figure_id: str):
    """Get profile version history."""
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")
    return await polaris_repo.get_profile_history(figure_id)


# ═══════════════════════════════════════════════════════════════
# Events (Phase 2)
# ═══════════════════════════════════════════════════════════════


@router.get("/figures/{figure_id}/events", response_model=list[dict])
async def list_events(figure_id: str,
                      limit: int = Query(50, ge=1, le=200),
                      min_significance: int = Query(1, ge=1, le=5)):
    """List events for a figure."""
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")
    return await polaris_repo.get_events(
        figure_id, limit=limit, min_significance=min_significance,
    )


@router.post("/figures/{figure_id}/events", response_model=dict)
async def create_event(figure_id: str, body: EventCreate):
    """Manually register an event for a figure."""
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")

    return await polaris_repo.insert_event(
        figure_id=figure_id,
        event_type=body.event_type,
        title=body.title,
        summary=body.summary,
        source_url=body.source_url,
        event_date=body.event_date,
        significance=body.significance,
        categories=body.categories,
    )


@router.post("/figures/{figure_id}/scan-news", response_model=dict)
async def scan_news(figure_id: str, body: NewsScanRequest | None = None):
    """Trigger a manual news scan + event detection for a figure.

    Fetches latest news, classifies events via LLM/rules, stores
    significant events, and optionally updates profile.
    """
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")

    from app.polaris.collectors.event_detector import classify_news_batch
    from app.polaris.collectors.news import fetch_figure_news

    extra_kw = body.extra_keywords if body else []
    max_articles = body.max_articles if body else 10
    min_sig = body.min_significance if body else 2

    # Fetch news
    articles = await fetch_figure_news(
        figure_name=figure["name"],
        country=figure.get("country", "US"),
        extra_keywords=extra_kw,
        max_articles=max_articles,
    )

    if not articles:
        return {"status": "ok", "articles_found": 0, "events_created": 0}

    # Classify events
    events = await classify_news_batch(
        figure_name=figure["name"],
        articles=articles,
        min_significance=min_sig,
    )

    # Store events (with dedup)
    created = []
    for event in events:
        event_title = event.get("article_title", "")
        if event_title and await polaris_repo.event_exists(figure_id, event_title):
            continue

        record = await polaris_repo.insert_event(
            figure_id=figure_id,
            event_type=event.get("event_type", "statement"),
            title=event_title,
            summary=event.get("summary", ""),
            raw_content=event.get("market_relevance", ""),
            source_url=event.get("article_url", ""),
            event_date=event.get("article_published", ""),
            significance=event.get("significance", 2),
            categories=event.get("categories", []),
        )
        created.append(record)

    # Check for profile updates
    profile_updated = False
    high_sig_events = [e for e in events if e.get("profile_update_needed") and e.get("significance", 0) >= 4]
    if high_sig_events:
        from app.polaris.collectors.llm_extractor import extract_profile_update
        from app.polaris.profile.engine import update_profile_from_event

        profile = await get_current_profile(figure_id)
        if profile:
            for event in high_sig_events:
                try:
                    update_result = await extract_profile_update(
                        figure_name=figure["name"],
                        current_profile=profile["profile_data"],
                        new_event_summary=event.get("summary", ""),
                    )
                    if update_result.get("should_update"):
                        await update_profile_from_event(
                            figure_id=figure_id,
                            event_summary=event.get("summary", ""),
                            updated_fields=update_result.get("updated_fields", {}),
                            changelog=update_result.get("changelog", ""),
                        )
                        profile_updated = True
                except Exception as e:
                    logger.warning("Profile update failed: %s", e)

    return {
        "status": "ok",
        "articles_found": len(articles),
        "events_created": len(created),
        "events": created,
        "profile_updated": profile_updated,
    }


# ═══════════════════════════════════════════════════════════════
# Predictions (Phase 1 + Phase 3 agentic)
# ═══════════════════════════════════════════════════════════════


@router.post("/figures/{figure_id}/predict", response_model=dict)
async def predict(figure_id: str, body: PredictRequest | None = None):
    """Generate behavior predictions using agentic analysis.

    The analyzer queries DB for historical events and past prediction
    accuracy before generating new predictions.
    """
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")

    profile = await get_current_profile(figure_id)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="프로파일이 없습니다. 먼저 init-profile을 실행하세요.",
        )

    from app.polaris.analysis.behavior_analyzer import run_prediction

    topic = body.topic if body else ""
    context = body.context if body else ""
    result = await run_prediction(
        figure_name=figure["name"],
        profile_data=profile["profile_data"],
        topic=topic,
        extra_context=context,
        figure_id=figure_id,
    )

    if result["status"] != "ok":
        raise HTTPException(status_code=502, detail=result.get("message", "예측 실패"))

    # Save predictions to DB
    saved = []
    for pred in result.get("predictions", []):
        record = await polaris_repo.insert_prediction(
            figure_id=figure_id,
            prediction_type=pred.get("type", "action"),
            prediction=pred.get("prediction", ""),
            reasoning=pred.get("reasoning", ""),
            confidence=pred.get("confidence", 0.5),
            timeframe=pred.get("timeframe", "short"),
            market_impact=pred.get("market_impact"),
        )
        saved.append(record)

    return {
        "status": "ok",
        "figure": figure["name"],
        "predictions_count": len(saved),
        "predictions": saved,
        "metadata": result.get("metadata", {}),
    }


@router.get("/figures/{figure_id}/predictions", response_model=list[dict])
async def list_predictions(figure_id: str,
                           limit: int = Query(20, ge=1, le=100),
                           status: str | None = None):
    """List predictions for a figure."""
    figure = await polaris_repo.get_figure(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="인물을 찾을 수 없습니다.")
    return await polaris_repo.get_predictions(figure_id, limit=limit, status=status)


@router.patch("/predictions/{prediction_id}/outcome", response_model=dict)
async def update_outcome(prediction_id: str, body: PredictionOutcomeUpdate):
    """Record actual outcome for a prediction (post-hoc validation)."""
    updated = await polaris_repo.update_prediction_outcome(
        prediction_id=prediction_id,
        status=body.status,
        outcome=body.outcome,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="예측을 찾을 수 없습니다.")
    return {"status": "ok", "prediction_id": prediction_id, "new_status": body.status}


# ═══════════════════════════════════════════════════════════════
# Signal Bridge (Phase 3 — VIBE integration)
# ═══════════════════════════════════════════════════════════════


@router.post("/signal-adjustment", response_model=dict)
async def get_signal_adjustment(body: GeopoliticalAdjustmentRequest):
    """Calculate geopolitical risk adjustment for a VIBE signal.

    Returns score modifier (±15 points) based on active predictions.
    """
    from app.polaris.analysis.signal_bridge import get_geopolitical_adjustment

    return await get_geopolitical_adjustment(
        symbol=body.symbol,
        market=body.market,
        sector=body.sector,
    )


# ═══════════════════════════════════════════════════════════════
# Dashboard / Summary
# ═══════════════════════════════════════════════════════════════


@router.get("/dashboard", response_model=dict)
async def polaris_dashboard():
    """POLARIS overview dashboard — all figures with recent activity."""
    figures = await polaris_repo.get_figures(status="active")

    dashboard_items = []
    for fig in figures:
        figure_id = fig["id"]

        # Get latest predictions
        recent_preds = await polaris_repo.get_predictions(figure_id, limit=3)

        # Get latest events
        recent_events = await polaris_repo.get_events(figure_id, limit=3, min_significance=2)

        # Get stats
        pred_stats = await polaris_repo.get_prediction_stats(figure_id)

        dashboard_items.append({
            "figure": {
                "id": fig["id"],
                "name": fig["name"],
                "name_ko": fig["name_ko"],
                "role": fig["role"],
                "country": fig["country"],
                "profile_version": fig.get("latest_profile_version"),
            },
            "recent_predictions": recent_preds,
            "recent_events": recent_events,
            "stats": pred_stats,
        })

    return {
        "figures_count": len(figures),
        "figures": dashboard_items,
    }
