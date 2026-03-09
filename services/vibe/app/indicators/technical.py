"""Technical indicator calculations using ta library + pandas."""

import math

import pandas as pd
import ta


def compute_all_indicators(df: pd.DataFrame) -> dict:
    """Compute all technical indicators from OHLCV DataFrame.

    Args:
        df: DataFrame with columns [open, high, low, close, volume],
            sorted by date ascending (oldest first).

    Returns:
        dict with indicator values for the latest row.
    """
    if df.empty or len(df) < 20:
        return {}

    close = df["close"]
    high = df["high"] if "high" in df.columns else close
    low = df["low"] if "low" in df.columns else close
    volume = df["volume"] if "volume" in df.columns else pd.Series(0, index=df.index)

    # RSI (14-period)
    rsi_14 = ta.momentum.RSIIndicator(close=close, window=14).rsi()

    # Moving Averages
    ma_5 = close.rolling(window=5).mean()
    ma_20 = close.rolling(window=20).mean()
    ma_60 = close.rolling(window=60).mean()
    ma_120 = close.rolling(window=120).mean()

    # MACD (12, 26, 9)
    macd_indicator = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    macd = macd_indicator.macd()
    macd_signal = macd_indicator.macd_signal()
    macd_histogram = macd_indicator.macd_diff()

    # Bollinger Bands (20, 2)
    bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
    bb_upper = bb.bollinger_hband()
    bb_middle = bb.bollinger_mavg()
    bb_lower = bb.bollinger_lband()

    # Disparity (20-day) = (close / MA20) * 100
    disparity_20 = (close / ma_20.replace(0, float("nan"))) * 100

    # Volume Ratio = today volume / 20-day avg volume
    vol_avg_20 = volume.rolling(window=20).mean()
    volume_ratio = volume / vol_avg_20.replace(0, float("nan"))

    # Get latest values
    idx = -1
    result = {
        "rsi_14": _safe_float(rsi_14, idx),
        "ma_5": _safe_float(ma_5, idx),
        "ma_20": _safe_float(ma_20, idx),
        "ma_60": _safe_float(ma_60, idx),
        "ma_120": _safe_float(ma_120, idx),
        "macd": _safe_float(macd, idx),
        "macd_signal": _safe_float(macd_signal, idx),
        "macd_histogram": _safe_float(macd_histogram, idx),
        "bollinger_upper": _safe_float(bb_upper, idx),
        "bollinger_middle": _safe_float(bb_middle, idx),
        "bollinger_lower": _safe_float(bb_lower, idx),
        "disparity_20": _safe_float(disparity_20, idx),
        "volume_ratio": _safe_float(volume_ratio, idx),
    }

    return result


def compute_indicators_series(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all indicators as a full series DataFrame (for storage)."""
    if df.empty or len(df) < 20:
        return pd.DataFrame()

    close = df["close"]
    high = df["high"] if "high" in df.columns else close
    low = df["low"] if "low" in df.columns else close
    volume = df["volume"] if "volume" in df.columns else pd.Series(0, index=df.index)

    result = pd.DataFrame(index=df.index)

    result["rsi_14"] = ta.momentum.RSIIndicator(close=close, window=14).rsi()
    result["ma_5"] = close.rolling(window=5).mean()
    result["ma_20"] = close.rolling(window=20).mean()
    result["ma_60"] = close.rolling(window=60).mean()
    result["ma_120"] = close.rolling(window=120).mean()

    macd_ind = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    result["macd"] = macd_ind.macd()
    result["macd_signal"] = macd_ind.macd_signal()
    result["macd_histogram"] = macd_ind.macd_diff()

    bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
    result["bollinger_upper"] = bb.bollinger_hband()
    result["bollinger_middle"] = bb.bollinger_mavg()
    result["bollinger_lower"] = bb.bollinger_lband()

    disparity = (close / result["ma_20"]) * 100
    disparity = disparity.replace([float("inf"), float("-inf")], pd.NA)
    result["disparity_20"] = disparity

    vol_avg_20 = volume.rolling(window=20).mean()
    vol_ratio = volume / vol_avg_20
    vol_ratio = vol_ratio.replace([float("inf"), float("-inf")], pd.NA)
    result["volume_ratio"] = vol_ratio

    return result


def _safe_float(series: pd.Series, idx: int) -> float | None:
    """Safely extract a float value from a series at given index."""
    try:
        val = series.iloc[idx]
        if pd.isna(val):
            return None
        fval = float(val)
        if not math.isfinite(fval):
            return None
        return round(fval, 4)
    except (IndexError, TypeError, ValueError, OverflowError):
        return None
