"""Macro environment scoring engine."""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("vibe2.engine.macro_score")


@dataclass
class MacroScore:
    vix_score: float = 0.0
    rate_score: float = 0.0
    dollar_score: float = 0.0
    fear_greed_score: float = 0.0
    total: float = 0.0
    details: dict = field(default_factory=dict)


def _vix_score(vix: float | None) -> float:
    """VIX score — same scale as leverage engine."""
    if vix is None:
        return 0.0
    if vix < 15:
        return 0.8
    if vix < 20:
        return 0.3
    if vix < 25:
        return -0.3
    if vix < 35:
        return -0.7
    return -1.0


def _rate_score(us_10y: float | None, rate_change_5d: float | None) -> float:
    """Treasury yield direction score.

    Args:
        us_10y: Current 10-year yield.
        rate_change_5d: 5-day change in yield (current - 5d ago).
    """
    if rate_change_5d is None:
        return 0.0
    if rate_change_5d <= -0.1:
        return 0.8
    if rate_change_5d <= -0.05:
        return 0.3
    if rate_change_5d <= 0.05:
        return 0.0
    if rate_change_5d <= 0.1:
        return -0.3
    return -0.8


def _dollar_score(dxy: float | None) -> float:
    """DXY dollar index score."""
    if dxy is None:
        return 0.0
    if dxy < 100:
        return 0.5
    if dxy < 103:
        return 0.2
    if dxy < 106:
        return -0.2
    return -0.5


def _fear_greed_score(fg: float | None) -> float:
    """Fear & Greed Index score — contrarian logic."""
    if fg is None:
        return 0.0
    if fg <= 20:
        return 0.8
    if fg <= 40:
        return 0.3
    if fg <= 60:
        return 0.0
    if fg <= 80:
        return -0.3
    return -0.8


def calculate_macro(
    macro_data: dict | None,
    fear_greed: float | None = None,
) -> MacroScore:
    """Calculate macro environment scores.

    Args:
        macro_data: Dict from get_latest_macro() with keys like
            vix, dxy, us_10y_yield, yield_spread, etc.
            May also include 'us_10y_yield_5d_ago' for rate change calculation.
        fear_greed: Fear & Greed index value (0-100) or None.

    Returns:
        MacroScore with individual and total scores.
    """
    if macro_data is None:
        macro_data = {}

    details: dict = {}

    # VIX
    vix = macro_data.get("vix")
    vix_s = _vix_score(vix)
    details["vix"] = vix

    # Rate direction (5-day change)
    us_10y = macro_data.get("us_10y_yield")
    us_10y_5d = macro_data.get("us_10y_yield_5d_ago")
    rate_change = None
    if us_10y is not None and us_10y_5d is not None:
        rate_change = us_10y - us_10y_5d
    rate_s = _rate_score(us_10y, rate_change)
    details["us_10y_yield"] = us_10y
    details["us_10y_yield_5d_ago"] = us_10y_5d
    details["rate_change_5d"] = round(rate_change, 4) if rate_change is not None else None

    # Dollar
    dxy = macro_data.get("dxy")
    dollar_s = _dollar_score(dxy)
    details["dxy"] = dxy

    # Fear & Greed
    fg_s = _fear_greed_score(fear_greed)
    details["fear_greed"] = fear_greed

    # Total
    total = (vix_s + rate_s + dollar_s + fg_s) / 4.0
    total = max(-1.0, min(1.0, total))

    score = MacroScore(
        vix_score=vix_s,
        rate_score=rate_s,
        dollar_score=dollar_s,
        fear_greed_score=fg_s,
        total=round(total, 4),
        details=details,
    )
    logger.info("Macro score: %.3f (VIX=%.1f rate=%.1f DXY=%.1f F&G=%.1f)",
                total, vix_s, rate_s, dollar_s, fg_s)
    return score
