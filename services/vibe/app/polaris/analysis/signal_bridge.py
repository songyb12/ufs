"""Signal Bridge — Connect POLARIS predictions to VIBE signal adjustments.

Provides a geopolitical risk modifier that can adjust VIBE signal scores
based on active POLARIS predictions with market impact data.
"""

from __future__ import annotations

import logging

from app.polaris import repository as polaris_repo
from app.polaris.analysis.market_mapper import summarize_market_impact

logger = logging.getLogger("vibe.polaris.analysis.signal_bridge")

# Maximum adjustment from geopolitical factors (±15 points on -100..+100 scale)
MAX_GEO_ADJUSTMENT = 15.0


async def get_geopolitical_adjustment(
    symbol: str,
    market: str,
    sector: str = "",
) -> dict:
    """Calculate geopolitical risk adjustment for a VIBE signal.

    Queries active POLARIS predictions and computes a score modifier
    based on relevant market impact data.

    Args:
        symbol: Stock symbol.
        market: Market code (KR/US).
        sector: Optional sector for more targeted adjustment.

    Returns:
        {
            "adjustment": float (-15..+15),
            "reason": str,
            "predictions_used": int,
            "figures_analyzed": int,
        }
    """
    figures = await polaris_repo.get_figures(status="active")
    if not figures:
        return _no_adjustment("인물 데이터 없음")

    all_relevant_preds = []

    for figure in figures:
        preds = await polaris_repo.get_predictions(
            figure["id"], limit=10, status="pending",
        )
        for pred in preds:
            impact = pred.get("market_impact", {})
            if not impact:
                continue

            # Check if this prediction affects the relevant sector
            affected_sectors = [s.lower() for s in impact.get("sectors", [])]
            if sector and sector.lower() not in affected_sectors:
                # Also check for broad market predictions
                if not any(s in affected_sectors for s in ["market", "equities", "전체"]):
                    continue

            all_relevant_preds.append(pred)

    if not all_relevant_preds:
        return _no_adjustment("관련 예측 없음")

    # Compute weighted adjustment
    impact_summary = summarize_market_impact(all_relevant_preds)

    direction_mult = {
        "positive": 1.0,
        "negative": -1.0,
        "mixed": 0.0,
        "neutral": 0.0,
    }.get(impact_summary["overall_direction"], 0.0)

    avg_conf = impact_summary["avg_confidence"]
    raw_adjustment = direction_mult * avg_conf * MAX_GEO_ADJUSTMENT

    # Clamp
    adjustment = max(-MAX_GEO_ADJUSTMENT, min(MAX_GEO_ADJUSTMENT, raw_adjustment))

    # Build reason string
    high_impact = impact_summary.get("high_impact_sectors", [])
    sector_names = [s["sector"] for s in high_impact[:3]]
    reason = (
        f"POLARIS 지정학적 조정: {impact_summary['overall_direction']} "
        f"({len(all_relevant_preds)}개 예측, 평균 신뢰도 {avg_conf:.0%})"
    )
    if sector_names:
        reason += f" — 영향 섹터: {', '.join(sector_names)}"

    return {
        "adjustment": round(adjustment, 2),
        "reason": reason,
        "predictions_used": len(all_relevant_preds),
        "figures_analyzed": len(figures),
    }


def _no_adjustment(reason: str) -> dict:
    return {
        "adjustment": 0.0,
        "reason": reason,
        "predictions_used": 0,
        "figures_analyzed": 0,
    }
