"""Technical indicator scoring engine for SOXL."""

import logging
import math
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger("vibe2.engine.technical")


@dataclass
class TechnicalScore:
    rsi_score: float = 0.0
    macd_score: float = 0.0
    bb_score: float = 0.0
    ma_score: float = 0.0
    total: float = 0.0
    details: dict = field(default_factory=dict)


def _safe_last(series: pd.Series) -> float | None:
    """Get last non-NaN value from a series."""
    if series is None or series.empty:
        return None
    val = series.iloc[-1]
    if pd.isna(val) or not math.isfinite(float(val)):
        return None
    return float(val)


def _compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """RSI(14) — Wilder's smoothed RSI."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD(12,26,9). Returns (macd_line, signal_line, histogram)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _compute_bollinger(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands(20,2). Returns (upper, middle, lower)."""
    middle = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def calculate_technical(df: pd.DataFrame) -> TechnicalScore:
    """Calculate technical indicator scores from SOXL OHLCV DataFrame.

    Args:
        df: DataFrame with columns [open, high, low, close, volume],
            indexed by date, sorted ascending.

    Returns:
        TechnicalScore with individual and total scores in -1 to +1 range.
    """
    if df is None or df.empty or len(df) < 26:
        logger.warning("Insufficient data for technical analysis (%d rows)", 0 if df is None else len(df))
        return TechnicalScore(details={"error": "insufficient_data"})

    close = df["close"].astype(float)

    # --- RSI ---
    rsi_series = _compute_rsi(close)
    rsi_val = _safe_last(rsi_series)

    if rsi_val is None:
        rsi_score = 0.0
    elif rsi_val <= 30:
        rsi_score = 1.0
    elif rsi_val <= 40:
        rsi_score = 0.5
    elif rsi_val <= 60:
        rsi_score = 0.0
    elif rsi_val <= 70:
        rsi_score = -0.5
    else:
        rsi_score = -1.0

    # --- MACD ---
    macd_line, signal_line, histogram = _compute_macd(close)
    hist_val = _safe_last(histogram)
    hist_prev = _safe_last(histogram.iloc[:-1]) if len(histogram) > 1 else None
    macd_val = _safe_last(macd_line)
    signal_val = _safe_last(signal_line)

    if hist_val is None:
        macd_score = 0.0
    elif hist_prev is not None and hist_prev <= 0 < hist_val:
        # Histogram just turned positive
        macd_score = 0.7
    elif hist_prev is not None and hist_prev >= 0 > hist_val:
        # Histogram just turned negative
        macd_score = -0.7
    elif macd_val is not None and signal_val is not None and macd_val > signal_val:
        macd_score = 0.3
    elif macd_val is not None and signal_val is not None and macd_val < signal_val:
        macd_score = -0.3
    else:
        macd_score = 0.0

    # --- Bollinger Bands ---
    bb_upper, bb_middle, bb_lower = _compute_bollinger(close)
    bb_upper_val = _safe_last(bb_upper)
    bb_middle_val = _safe_last(bb_middle)
    bb_lower_val = _safe_last(bb_lower)
    close_val = _safe_last(close)

    if close_val is None or bb_upper_val is None or bb_lower_val is None:
        bb_score = 0.0
        bb_position = None
    elif close_val <= bb_lower_val:
        bb_score = 0.8
        bb_position = "below_lower"
    elif close_val < bb_middle_val:
        bb_score = 0.2
        bb_position = "below_middle"
    elif close_val < bb_upper_val:
        bb_score = -0.2
        bb_position = "above_middle"
    else:
        bb_score = -0.8
        bb_position = "above_upper"

    # --- Moving Averages ---
    ma_20 = _safe_last(close.rolling(20).mean())
    ma_50 = _safe_last(close.rolling(50).mean())
    ma_200 = _safe_last(close.rolling(200).mean())

    ma_score = 0.0
    ma_detail = {}
    if close_val is not None:
        for label, ma_val in [("ma_20", ma_20), ("ma_50", ma_50), ("ma_200", ma_200)]:
            if ma_val is not None:
                above = close_val > ma_val
                ma_score += 0.33 if above else -0.33
                ma_detail[label] = {"value": round(ma_val, 2), "above": above}
    # Clamp to [-1, 1]
    ma_score = max(-1.0, min(1.0, ma_score))

    # --- Total ---
    total = (rsi_score + macd_score + bb_score + ma_score) / 4.0
    total = max(-1.0, min(1.0, total))

    details = {
        "rsi_value": round(rsi_val, 2) if rsi_val is not None else None,
        "macd_line": round(macd_val, 4) if macd_val is not None else None,
        "macd_signal": round(signal_val, 4) if signal_val is not None else None,
        "macd_hist": round(hist_val, 4) if hist_val is not None else None,
        "macd_hist_prev": round(hist_prev, 4) if hist_prev is not None else None,
        "bb_upper": round(bb_upper_val, 2) if bb_upper_val is not None else None,
        "bb_middle": round(bb_middle_val, 2) if bb_middle_val is not None else None,
        "bb_lower": round(bb_lower_val, 2) if bb_lower_val is not None else None,
        "bb_position": bb_position,
        "close": round(close_val, 2) if close_val is not None else None,
        "ma": ma_detail,
    }

    score = TechnicalScore(
        rsi_score=rsi_score,
        macd_score=macd_score,
        bb_score=bb_score,
        ma_score=round(ma_score, 4),
        total=round(total, 4),
        details=details,
    )
    logger.info("Technical score: %.3f (RSI=%.1f MACD=%.1f BB=%.1f MA=%.1f)",
                total, rsi_score, macd_score, bb_score, ma_score)
    return score
