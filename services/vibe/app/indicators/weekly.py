"""Weekly timeframe analysis - Daily→Weekly resample + trend alignment."""

import logging

import pandas as pd
import ta

logger = logging.getLogger("vibe.indicators.weekly")


def compute_weekly_indicators(daily_df: pd.DataFrame) -> dict | None:
    """Resample daily OHLCV to weekly and compute weekly indicators.

    Args:
        daily_df: DataFrame with date index, columns: open, high, low, close, volume

    Returns:
        dict with weekly indicators or None if insufficient data
    """
    if daily_df is None or daily_df.empty or len(daily_df) < 30:
        return None

    df = daily_df.copy()

    # Ensure datetime index for resampling
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Resample to weekly (Friday close)
    weekly = df.resample("W-FRI").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    if len(weekly) < 10:
        return None

    close = weekly["close"]

    # Weekly RSI (14-period)
    rsi_14_weekly = ta.momentum.RSIIndicator(close=close, window=14).rsi()

    # Weekly Moving Averages
    ma_5_weekly = close.rolling(window=5).mean()
    ma_20_weekly = close.rolling(window=20).mean()

    # Weekly MACD
    if len(close) >= 26:
        macd_ind = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
        macd_weekly = macd_ind.macd_diff()
    else:
        macd_weekly = pd.Series([None] * len(close), index=close.index)

    # Determine weekly trend direction
    trend_direction = _determine_trend(close, ma_5_weekly, ma_20_weekly)

    # Get latest values
    result = {
        "rsi_14_weekly": _safe_float(rsi_14_weekly),
        "ma_5_weekly": _safe_float(ma_5_weekly),
        "ma_20_weekly": _safe_float(ma_20_weekly),
        "macd_weekly": _safe_float(macd_weekly),
        "trend_direction": trend_direction,
        "week_ending": str(weekly.index[-1].date()),
    }

    return result


def compute_timeframe_multiplier(
    daily_signal: str,
    weekly_trend: str,
) -> float:
    """Compute timeframe alignment multiplier.

    When daily and weekly trends align → boost.
    When they conflict → penalty.

    Returns multiplier (0.7 to 1.2)
    """
    if daily_signal == "BUY":
        if weekly_trend == "bullish":
            return 1.2  # Strong alignment
        elif weekly_trend == "neutral":
            return 1.0  # No effect
        else:  # bearish
            return 0.7  # Counter-trend penalty

    elif daily_signal == "SELL":
        if weekly_trend == "bearish":
            return 1.2  # Strong alignment
        elif weekly_trend == "neutral":
            return 1.0
        else:  # bullish
            return 0.7  # Counter-trend penalty

    # HOLD - no multiplier effect
    return 1.0


def _determine_trend(
    close: pd.Series,
    ma_5: pd.Series,
    ma_20: pd.Series,
) -> str:
    """Determine weekly trend from price and MAs."""
    latest_close = close.iloc[-1] if not close.empty else None
    latest_ma5 = _safe_float(ma_5)
    latest_ma20 = _safe_float(ma_20)

    if latest_close is None or latest_ma5 is None or latest_ma20 is None:
        return "neutral"

    bullish_signals = 0
    bearish_signals = 0

    # Price vs MA5
    if latest_close > latest_ma5:
        bullish_signals += 1
    else:
        bearish_signals += 1

    # MA5 vs MA20 (golden/death cross)
    if latest_ma5 > latest_ma20:
        bullish_signals += 1
    else:
        bearish_signals += 1

    # Price momentum (last 4 weeks)
    if len(close) >= 4 and close.iloc[-4] != 0:
        recent_return = (close.iloc[-1] - close.iloc[-4]) / close.iloc[-4] * 100
        if recent_return > 3:
            bullish_signals += 1
        elif recent_return < -3:
            bearish_signals += 1

    if bullish_signals >= 2:
        return "bullish"
    elif bearish_signals >= 2:
        return "bearish"
    return "neutral"


def _safe_float(series: pd.Series) -> float | None:
    """Get last non-NaN value from series."""
    try:
        val = series.iloc[-1]
        if pd.isna(val):
            return None
        return round(float(val), 4)
    except (IndexError, TypeError):
        return None
