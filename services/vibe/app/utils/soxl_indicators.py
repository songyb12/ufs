"""Shared technical indicator computations for SOXL modules.

Used by:
- app/routers/soxl_live.py (real-time indicators)
- app/backtesting/soxl_engine.py (backtest simulation)

All functions are pure numpy computations with no DB/IO dependencies.
"""

import math

import numpy as np


def compute_rsi(closes: np.ndarray, period: int = 14) -> float | None:
    """Wilder's smoothing RSI."""
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_multi_tf_rsi(closes: np.ndarray) -> dict:
    """Compute RSI across multiple timeframes (7, 14, 21)."""
    return {
        "rsi_7": compute_rsi(closes, 7),
        "rsi_14": compute_rsi(closes, 14),
        "rsi_21": compute_rsi(closes, 21),
    }


def compute_stoch_rsi(
    closes: np.ndarray, rsi_period: int = 14, stoch_period: int = 14,
) -> float | None:
    """Stochastic RSI: (RSI - min_RSI) / (max_RSI - min_RSI) * 100."""
    if len(closes) < rsi_period + stoch_period + 1:
        return None
    rsi_values = []
    for i in range(stoch_period + 1):
        end_idx = len(closes) - stoch_period + i
        if end_idx < rsi_period + 1:
            return None
        rsi_val = compute_rsi(closes[:end_idx], rsi_period)
        if rsi_val is None:
            return None
        rsi_values.append(rsi_val)
    if not rsi_values:
        return None
    min_rsi = min(rsi_values)
    max_rsi = max(rsi_values)
    if max_rsi == min_rsi:
        return 50.0
    return (rsi_values[-1] - min_rsi) / (max_rsi - min_rsi) * 100


def compute_macd(
    closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9,
) -> tuple[float | None, float | None, float | None]:
    """MACD line, signal line, histogram."""
    if len(closes) < slow + signal:
        return None, None, None

    def ema(data: np.ndarray, period: int) -> np.ndarray:
        alpha = 2.0 / (period + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return float(macd_line[-1]), float(signal_line[-1]), float(histogram[-1])


def compute_bollinger(
    closes: np.ndarray, period: int = 20, std_dev: float = 2.0,
) -> tuple[float | None, float | None, float | None]:
    """Bollinger Bands (upper, middle, lower)."""
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    middle = float(np.mean(window))
    std = float(np.std(window))
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def compute_adx(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14,
) -> float | None:
    """Average Directional Index (ADX) for trend strength."""
    if len(closes) < period * 2 + 1:
        return None
    n = len(closes)
    tr_list = []
    plus_dm_list = []
    minus_dm_list = []
    for i in range(1, n):
        high_diff = highs[i] - highs[i - 1]
        low_diff = lows[i - 1] - lows[i]
        plus_dm = max(high_diff, 0) if high_diff > low_diff else 0
        minus_dm = max(low_diff, 0) if low_diff > high_diff else 0
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)

    if len(tr_list) < period:
        return None

    atr = sum(tr_list[:period])
    plus_di_smooth = sum(plus_dm_list[:period])
    minus_di_smooth = sum(minus_dm_list[:period])
    dx_values = []

    for i in range(period, len(tr_list)):
        atr = atr - (atr / period) + tr_list[i]
        plus_di_smooth = plus_di_smooth - (plus_di_smooth / period) + plus_dm_list[i]
        minus_di_smooth = minus_di_smooth - (minus_di_smooth / period) + minus_dm_list[i]

        if atr == 0:
            continue
        plus_di = (plus_di_smooth / atr) * 100
        minus_di = (minus_di_smooth / atr) * 100
        di_sum = plus_di + minus_di
        if di_sum == 0:
            continue
        dx = abs(plus_di - minus_di) / di_sum * 100
        dx_values.append(dx)

    if len(dx_values) < period:
        return None
    adx = sum(dx_values[:period]) / period
    for i in range(period, len(dx_values)):
        adx = (adx * (period - 1) + dx_values[i]) / period
    return float(adx)


def compute_obv_trend(
    closes: np.ndarray, volumes: np.ndarray, period: int = 20,
) -> float | None:
    """On-Balance Volume trend slope (normalized)."""
    if len(closes) < period + 1 or len(volumes) < period + 1:
        return None
    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    obv_window = np.array(obv[-period:], dtype=float)
    x = np.arange(period, dtype=float)
    x_mean = np.mean(x)
    obv_mean = np.mean(obv_window)
    num = np.sum((x - x_mean) * (obv_window - obv_mean))
    den = np.sum((x - x_mean) ** 2)
    if den == 0:
        return 0.0
    slope = num / den
    avg_vol = np.mean(volumes[-period:])
    return float(slope / avg_vol) if avg_vol > 0 else 0.0


def compute_atr(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14,
) -> float | None:
    """Average True Range."""
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return float(atr)


def compute_volatility_ann(closes: np.ndarray, period: int = 20) -> float | None:
    """Annualized volatility (%)."""
    if len(closes) < period + 1:
        return None
    returns = np.diff(closes[-period - 1:]) / closes[-period - 1:-1]
    return float(np.std(returns) * math.sqrt(252) * 100)


def compute_disparity(closes: np.ndarray, period: int = 20) -> float | None:
    """Price disparity from MA (%)."""
    if len(closes) < period:
        return None
    ma = float(np.mean(closes[-period:]))
    if ma == 0:
        return None
    return float(closes[-1] / ma * 100)


def detect_rsi_divergence(
    closes: np.ndarray, period: int = 14, lookback: int = 5,
) -> str | None:
    """Detect RSI divergence (bullish/bearish).

    Bullish: price lower low, RSI higher low
    Bearish: price higher high, RSI lower high
    """
    if len(closes) < period + lookback + 1:
        return None
    rsi_vals = []
    for i in range(lookback + 1):
        end_idx = len(closes) - lookback + i
        rsi = compute_rsi(closes[:end_idx], period)
        if rsi is None:
            return None
        rsi_vals.append(rsi)

    price_window = closes[-lookback - 1:]
    if price_window[-1] < price_window[0] and rsi_vals[-1] > rsi_vals[0]:
        return "bullish"
    if price_window[-1] > price_window[0] and rsi_vals[-1] < rsi_vals[0]:
        return "bearish"
    return None


def detect_gap(prices: list[dict], idx: int) -> dict | None:
    """Detect overnight gap at given index."""
    if idx < 1:
        return None
    prev_close = prices[idx - 1]["close"]
    cur_open = prices[idx].get("open", prev_close)
    if prev_close == 0:
        return None
    gap_pct = (cur_open - prev_close) / prev_close * 100
    if abs(gap_pct) >= 1.0:
        return {"gap_pct": round(gap_pct, 2), "direction": "up" if gap_pct > 0 else "down"}
    return None
