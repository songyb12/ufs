"""Stock Similarity — Feature-vector based cosine similarity.

Uses existing technical/fundamental indicators to compute similarity
between stocks without requiring any external API calls.

Feature vector per stock:
  [RSI_norm, disparity_norm, technical_score_norm, macro_score_norm,
   fundamental_score_norm, sector_onehot...]
"""

import logging
import math
from typing import Any

from app.database import repositories as repo
from app.risk.sector import get_sector

logger = logging.getLogger("vibe.indicators.similarity")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalize(value: float | None, min_val: float, max_val: float) -> float:
    """Min-max normalize a value to [0, 1]."""
    if value is None:
        return 0.5  # neutral default
    if max_val == min_val:
        return 0.5
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


# Known sectors for one-hot encoding
SECTORS = [
    "반도체", "자동차", "바이오", "금융", "화학", "철강",
    "IT", "통신", "에너지", "소비재", "산업재", "유틸리티",
    "Technology", "Healthcare", "Finance", "Consumer", "Energy",
    "Industrials", "Materials", "Communication", "Utilities", "Real Estate",
    "기타",
]
_SECTOR_INDEX = {s: i for i, s in enumerate(SECTORS)}


def _build_feature_vector(signal: dict, sector: str) -> list[float]:
    """Build a normalized feature vector from signal data."""
    features = [
        _normalize(signal.get("rsi_value"), 0, 100),
        _normalize(signal.get("disparity_value"), 90, 110),
        _normalize(signal.get("technical_score"), -100, 100),
        _normalize(signal.get("macro_score"), -100, 100),
        _normalize(signal.get("raw_score"), -100, 100),
        _normalize(signal.get("confidence"), 0, 1),
    ]

    # Sector one-hot
    sector_vec = [0.0] * len(SECTORS)
    idx = _SECTOR_INDEX.get(sector, _SECTOR_INDEX.get("기타", len(SECTORS) - 1))
    sector_vec[idx] = 1.0

    # Weight sector influence (reduce to 0.3x to avoid sector-dominated similarity)
    sector_vec = [v * 0.3 for v in sector_vec]

    return features + sector_vec


async def find_similar_stocks(
    symbol: str,
    market: str | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Find stocks most similar to the given symbol based on signal features.

    Returns:
        dict with target stock info, similar stocks ranked by similarity score.
    """
    # Get all latest signals
    signals = await repo.get_latest_signals(market=market)
    if not signals:
        return {"error": "No signals available. Run pipeline first."}

    # Find target signal
    target = None
    others = []
    for s in signals:
        if s["symbol"] == symbol:
            target = s
        else:
            others.append(s)

    if target is None:
        return {"error": f"Symbol '{symbol}' not found in latest signals."}

    # Build feature vectors
    target_sector = get_sector(symbol)
    target_vec = _build_feature_vector(target, target_sector)

    similarities = []
    for s in others:
        s_sector = get_sector(s["symbol"])
        s_vec = _build_feature_vector(s, s_sector)
        sim = _cosine_similarity(target_vec, s_vec)
        similarities.append({
            "symbol": s["symbol"],
            "name": s.get("name", s["symbol"]),
            "market": s.get("market", ""),
            "similarity": round(sim, 4),
            "signal": s.get("final_signal", "HOLD"),
            "score": round(s.get("raw_score", 0), 1),
            "rsi": round(s.get("rsi_value", 0), 1) if s.get("rsi_value") is not None else None,
            "sector": s_sector,
        })

    # Sort by similarity descending
    similarities.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "target": {
            "symbol": symbol,
            "name": target.get("name", symbol),
            "market": target.get("market", ""),
            "signal": target.get("final_signal", "HOLD"),
            "score": round(target.get("raw_score", 0), 1),
            "rsi": round(target.get("rsi_value", 0), 1) if target.get("rsi_value") is not None else None,
            "sector": target_sector,
        },
        "similar": similarities[:top_n],
        "total_compared": len(similarities),
    }
