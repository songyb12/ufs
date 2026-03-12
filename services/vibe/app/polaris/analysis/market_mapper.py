"""Market Mapper — Map political predictions to market impact signals."""

from __future__ import annotations

import logging

logger = logging.getLogger("vibe.polaris.analysis.market_mapper")

SECTOR_KEYWORDS = {
    "tariff": ["technology", "semiconductor", "manufacturing", "retail"],
    "관세": ["technology", "semiconductor", "manufacturing", "retail"],
    "deregulation": ["energy", "finance", "banking"],
    "규제완화": ["energy", "finance", "banking"],
    "interest_rate": ["finance", "real_estate", "utilities"],
    "금리": ["finance", "real_estate", "utilities"],
    "defense": ["defense", "aerospace"],
    "국방": ["defense", "aerospace"],
    "infrastructure": ["construction", "materials", "industrial"],
    "인프라": ["construction", "materials", "industrial"],
    "tech_regulation": ["technology", "social_media", "cloud"],
    "기술규제": ["technology", "social_media", "cloud"],
    "energy_policy": ["energy", "oil_gas", "renewable"],
    "에너지": ["energy", "oil_gas", "renewable"],
    "healthcare": ["pharma", "biotech", "healthcare"],
    "의료": ["pharma", "biotech", "healthcare"],
    "sanctions": ["finance", "energy", "commodity"],
    "제재": ["finance", "energy", "commodity"],
}


def extract_affected_sectors(prediction_text: str) -> list[str]:
    """Extract potentially affected market sectors from prediction text."""
    text_lower = prediction_text.lower()
    sectors = set()
    for keyword, sector_list in SECTOR_KEYWORDS.items():
        if keyword.lower() in text_lower:
            sectors.update(sector_list)
    return sorted(sectors)


def summarize_market_impact(predictions: list[dict]) -> dict:
    """Aggregate market impact across multiple predictions."""
    if not predictions:
        return {"overall_direction": "neutral", "high_impact_sectors": [],
                "prediction_count": 0, "avg_confidence": 0.0}

    sector_scores: dict[str, list[float]] = {}
    directions: list[str] = []
    confidences: list[float] = []

    for pred in predictions:
        impact = pred.get("market_impact", {})
        if not impact:
            continue

        direction = impact.get("direction", "mixed")
        directions.append(direction)
        confidences.append(pred.get("confidence", 0.5))

        score = {"positive": 1, "negative": -1, "mixed": 0}.get(direction, 0)
        magnitude_mult = {"high": 1.5, "medium": 1.0, "low": 0.5}.get(
            impact.get("magnitude", "medium"), 1.0
        )

        for sector in impact.get("sectors", []):
            sector_scores.setdefault(sector, []).append(score * magnitude_mult)

    if not directions:
        overall = "neutral"
    else:
        pos = directions.count("positive")
        neg = directions.count("negative")
        overall = "positive" if pos > neg else "negative" if neg > pos else "mixed"

    high_impact = []
    for sector, scores in sector_scores.items():
        avg = sum(scores) / len(scores) if scores else 0
        if abs(avg) > 0.5:
            high_impact.append({
                "sector": sector,
                "direction": "positive" if avg > 0 else "negative",
                "strength": abs(avg),
            })
    high_impact.sort(key=lambda x: x["strength"], reverse=True)

    return {
        "overall_direction": overall,
        "high_impact_sectors": high_impact[:10],
        "prediction_count": len(predictions),
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
    }
