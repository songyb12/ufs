"""Guru Insights API — Famous investor perspectives on current market."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.database.repositories import get_latest_macro, get_latest_signals
from app.indicators.guru_insights import (
    GURUS,
    analyze_all_gurus,
    build_guru_llm_prompt,
)
from app.risk.sector import get_sector

logger = logging.getLogger("vibe.guru")
router = APIRouter(prefix="/guru", tags=["guru"])


async def _build_context() -> tuple[dict, list[dict]]:
    """Fetch macro + enriched signals for guru analysis."""
    macro = await get_latest_macro() or {}
    signals = await get_latest_signals()

    # Enrich signals with sector
    for s in signals:
        s["sector"] = get_sector(s["symbol"])

    return macro, signals


@router.get("/insights")
async def get_guru_insights():
    """Get all guru market views, stock picks, and known holdings."""
    macro, signals = await _build_context()
    results = analyze_all_gurus(macro, signals)

    return {
        "gurus": results,
        "macro_snapshot": {
            "vix": macro.get("vix"),
            "fear_greed": macro.get("fear_greed_index"),
            "usd_krw": macro.get("usd_krw"),
            "date": macro.get("indicator_date"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{guru_id}")
async def get_guru_detail(guru_id: str):
    """Get a specific guru's analysis."""
    macro, signals = await _build_context()
    results = analyze_all_gurus(macro, signals)

    guru = next((g for g in results if g["id"] == guru_id), None)
    if not guru:
        valid = [g["id"] for g in GURUS]
        raise HTTPException(status_code=404, detail=f"Unknown guru: {guru_id}. Valid: {valid}")

    return {
        "guru": guru,
        "macro_snapshot": {
            "vix": macro.get("vix"),
            "fear_greed": macro.get("fear_greed_index"),
            "usd_krw": macro.get("usd_krw"),
            "us10y": macro.get("us_10y_yield"),
            "dxy": macro.get("dxy_index"),
            "date": macro.get("indicator_date"),
        },
    }


@router.post("/{guru_id}/analyze")
async def guru_llm_analysis(guru_id: str):
    """LLM-enhanced deep analysis for a specific guru (requires LLM API key)."""
    if not settings.LLM_API_KEY:
        raise HTTPException(status_code=400, detail="LLM API key not configured. Set LLM_API_KEY in .env")

    guru_exists = any(g["id"] == guru_id for g in GURUS)
    if not guru_exists:
        valid = [g["id"] for g in GURUS]
        raise HTTPException(status_code=404, detail=f"Unknown guru: {guru_id}. Valid: {valid}")

    macro, signals = await _build_context()

    # Build signal summary for LLM
    buy_signals = [s for s in signals if s.get("final_signal") == "BUY"]
    sell_signals = [s for s in signals if s.get("final_signal") == "SELL"]
    summary_parts = [
        f"총 {len(signals)}개 종목 분석 완료",
        f"BUY: {len(buy_signals)}개, SELL: {len(sell_signals)}개, HOLD: {len(signals) - len(buy_signals) - len(sell_signals)}개",
    ]
    if buy_signals:
        top3 = buy_signals[:3]
        summary_parts.append("상위 BUY: " + ", ".join(
            f"{s.get('name', s['symbol'])}({s['symbol']}, score={s.get('raw_score', 0):.1f})"
            for s in top3
        ))

    signals_summary = "\n".join(summary_parts)
    prompt = build_guru_llm_prompt(guru_id, macro, signals_summary)

    # Call LLM
    model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL
    provider = settings.LLM_PROVIDER.lower()
    analysis_text = None

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
            response = await client.messages.create(
                model=model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            analysis_text = response.content[0].text.strip()
        elif provider == "openai":
            import openai
            client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)
            response = await client.chat.completions.create(
                model=model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            analysis_text = response.choices[0].message.content.strip()
        else:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 LLM 프로바이더: {provider}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Guru LLM analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="LLM 호출 실패. 서버 로그를 확인하세요.")

    return {
        "status": "ok",
        "guru_id": guru_id,
        "analysis": analysis_text,
        "model": model,
        "provider": provider,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
