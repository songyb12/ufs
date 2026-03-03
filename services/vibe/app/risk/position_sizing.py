"""Position sizing calculations."""

import logging
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.risk.sector import check_sector_limit, get_sector

logger = logging.getLogger("vibe.risk.sizing")


@dataclass
class PositionRecommendation:
    symbol: str
    recommended_pct: float       # % of portfolio (0-1)
    recommended_amount: float    # in currency
    sizing_method: str
    confidence_factor: float
    sector: str
    sector_exposure_current: float
    sector_constraint_applied: bool
    rationale: str


class PositionSizer:
    """Compute recommended position size for a signal."""

    def __init__(self, config: Settings):
        self.config = config

    def compute(
        self,
        signal: dict[str, Any],
        current_positions: dict[str, float],
    ) -> PositionRecommendation:
        """Compute position size recommendation for a BUY signal.

        Args:
            signal: Signal dict with final_signal, confidence, raw_score, etc.
            current_positions: {symbol: position_pct} of existing positions
        """
        symbol = signal["symbol"]
        confidence = signal.get("confidence", 1.0)
        raw_score = abs(signal.get("raw_score", 0))
        sector = get_sector(symbol)

        # Base allocation
        base_pct = self.config.MAX_SINGLE_POSITION_PCT

        # Confidence adjustment (scale 0.3 to 1.0)
        conf_factor = max(0.3, min(1.0, confidence))
        adjusted_pct = base_pct * conf_factor

        # Score magnitude adjustment (stronger signal = larger position)
        score_factor = min(1.0, raw_score / 30)  # Normalize: 30+ = full size
        adjusted_pct *= max(0.5, score_factor)

        # Apply sector constraint
        final_pct, constrained = check_sector_limit(
            symbol, adjusted_pct, current_positions,
            self.config.MAX_SECTOR_EXPOSURE_PCT,
        )

        # Calculate amount
        amount = self.config.PORTFOLIO_TOTAL * final_pct

        # Build rationale
        parts = [f"Base: {base_pct:.0%}"]
        parts.append(f"Conf adj: {conf_factor:.2f}")
        parts.append(f"Score adj: {score_factor:.2f}")
        if constrained:
            parts.append(f"Sector limit applied ({sector})")

        from app.risk.sector import compute_sector_exposure
        sector_exp = compute_sector_exposure(current_positions)

        return PositionRecommendation(
            symbol=symbol,
            recommended_pct=round(final_pct, 4),
            recommended_amount=round(amount),
            sizing_method=self.config.POSITION_SIZING_METHOD,
            confidence_factor=round(conf_factor, 2),
            sector=sector,
            sector_exposure_current=round(sector_exp.get(sector, 0), 4),
            sector_constraint_applied=constrained,
            rationale=" | ".join(parts),
        )
