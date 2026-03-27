"""Leverage ETF analysis engine — SOXL-specific decay and volatility scoring."""

import logging
import math
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger("vibe2.engine.leverage")


@dataclass
class LeverageScore:
    decay_score: float = 0.0
    volatility_score: float = 0.0
    divergence_score: float = 0.0
    total: float = 0.0
    details: dict = field(default_factory=dict)


def _safe_last(series: pd.Series) -> float | None:
    """Get last non-NaN value."""
    if series is None or series.empty:
        return None
    val = series.iloc[-1]
    if pd.isna(val) or not math.isfinite(float(val)):
        return None
    return float(val)


def _vix_score(vix: float | None) -> float:
    """VIX-based volatility score. Low VIX = leverage-friendly."""
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


def calculate_leverage(
    soxl_df: pd.DataFrame,
    soxx_df: pd.DataFrame,
    vix: float | None,
) -> LeverageScore:
    """Calculate leverage ETF-specific scores.

    Args:
        soxl_df: SOXL OHLCV DataFrame (indexed by date, ascending).
        soxx_df: SOXX OHLCV DataFrame (same format).
        vix: Current VIX value (float or None).

    Returns:
        LeverageScore with decay, volatility, and divergence scores.
    """
    details: dict = {}

    # --- Tracking Difference (Decay) ---
    decay_score = 0.0
    tracking_diff_pct = None

    if (soxl_df is not None and soxx_df is not None
            and len(soxl_df) >= 20 and len(soxx_df) >= 20):
        soxl_close = soxl_df["close"].astype(float)
        soxx_close = soxx_df["close"].astype(float)

        # 20-day return
        soxl_ret = (soxl_close.iloc[-1] / soxl_close.iloc[-20] - 1) * 100
        soxx_ret = (soxx_close.iloc[-1] / soxx_close.iloc[-20] - 1) * 100
        expected_ret = soxx_ret * 3  # 3x leveraged

        if abs(expected_ret) > 0.001:
            tracking_diff_pct = soxl_ret - expected_ret
        else:
            tracking_diff_pct = 0.0

        if tracking_diff_pct <= -5:
            decay_score = -1.0
        elif tracking_diff_pct <= -2:
            decay_score = -0.5
        elif tracking_diff_pct <= 2:
            decay_score = 0.0
        else:
            decay_score = 0.5

        details["soxl_20d_return_pct"] = round(soxl_ret, 2)
        details["soxx_20d_return_pct"] = round(soxx_ret, 2)
        details["expected_3x_return_pct"] = round(expected_ret, 2)
        details["tracking_diff_pct"] = round(tracking_diff_pct, 2)
    else:
        details["tracking_diff_error"] = "insufficient_data"

    # --- VIX-based Volatility Score ---
    volatility_score = _vix_score(vix)
    details["vix"] = vix

    # --- Daily Volatility (Divergence) ---
    divergence_score = 0.0
    daily_vol_pct = None

    if soxl_df is not None and len(soxl_df) >= 20:
        soxl_close = soxl_df["close"].astype(float)
        daily_returns = soxl_close.pct_change().dropna()

        if len(daily_returns) >= 20:
            daily_vol_pct = daily_returns.iloc[-20:].std() * 100
            details["daily_volatility_pct"] = round(daily_vol_pct, 2)

            if daily_vol_pct <= 3:
                divergence_score = 0.5
            elif daily_vol_pct <= 5:
                divergence_score = 0.0
            elif daily_vol_pct <= 8:
                divergence_score = -0.5
            else:
                divergence_score = -1.0

    # --- Total ---
    total = (decay_score + volatility_score + divergence_score) / 3.0
    total = max(-1.0, min(1.0, total))

    score = LeverageScore(
        decay_score=decay_score,
        volatility_score=volatility_score,
        divergence_score=divergence_score,
        total=round(total, 4),
        details=details,
    )
    logger.info("Leverage score: %.3f (decay=%.1f vol=%.1f div=%.1f)",
                total, decay_score, volatility_score, divergence_score)
    return score
