"""SOXL-Specific Backtesting Engine.

Supports 4 strategy modes with 3x leverage ETF characteristics:
  A: Technical only (RSI/MACD/BB/StochRSI/ADX)
  B: Technical + Macro (VIX/yield/oil gating)
  C: Technical + Macro + Geopolitical risk
  D: Full (+ volatility scaling + leverage decay + slippage)
"""

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4

import numpy as np

from app.backtesting.metrics import (
    compute_backtest_metrics,
    compute_drawdown_periods,
    compute_exit_reason_stats,
    compute_monthly_returns,
)

logger = logging.getLogger("vibe.soxl_backtest")

# Macro data key mapping: DB column names → compute_macro_score expected keys
_MACRO_KEY_MAP = {
    "vix": "vix",
    "dxy": "dxy_index",
    "yield_spread": "us_yield_spread",
    "wti": "wti_crude",
    "gold": "gold_price",
    "copper": "copper_price",
    "usd_krw": "usd_krw",
}


class StrategyMode(str, Enum):
    TECHNICAL = "A"
    TECH_MACRO = "B"
    TECH_MACRO_GEO = "C"
    FULL = "D"


# Modes that require macro data
_MACRO_MODES = frozenset({StrategyMode.TECH_MACRO, StrategyMode.TECH_MACRO_GEO, StrategyMode.FULL})
# Modes that require geo data
_GEO_MODES = frozenset({StrategyMode.TECH_MACRO_GEO, StrategyMode.FULL})


@dataclass
class SoxlBacktestParams:
    """Tunable parameters for SOXL backtest."""
    # Entry
    rsi_entry: float = 35.0
    rsi_hard_limit: float = 65.0
    macd_golden_cross: bool = True
    volume_min_ratio: float = 1.5
    vix_max_entry: float = 30.0
    macro_score_min: float = -0.3
    adx_min_trend: float = 20.0          # [NEW] ADX minimum for trend confirmation
    stoch_rsi_entry: float = 20.0        # [NEW] StochRSI oversold threshold
    # Exit
    rsi_exit_partial: float = 65.0
    disparity_exit: float = 108.0
    stop_loss_pct: float = -7.0
    take_profit_pct: float = 20.0
    trailing_stop_pct: float = 5.0       # Trailing stop from peak
    atr_stop_multiplier: float = 2.5     # [NEW] ATR-based stop loss multiplier
    max_hold_days: int = 20
    # Position sizing
    max_portfolio_pct: float = 0.15
    vol_reduction_threshold: float = 80.0
    vix_reduction_threshold: float = 30.0
    geo_reduce_threshold: float = 70.0
    geo_block_threshold: float = 90.0
    use_kelly_sizing: bool = False       # [NEW] Kelly criterion position sizing
    consecutive_loss_scale: int = 3      # [NEW] Reduce size after N consecutive losses
    # Leverage decay
    leverage_factor: float = 3.0
    # Same-day re-entry prevention
    cooldown_days: int = 1               # Min days after exit before re-entry
    # Transaction costs
    slippage_bps: float = 5.0            # [NEW] Slippage in basis points (0.05%)
    commission_bps: float = 0.0          # [NEW] Commission in basis points


# ── Default parameter presets ──
PARAM_PRESETS: dict[str, dict] = {
    "default": {},
    "aggressive": {
        "rsi_entry": 40.0, "stop_loss_pct": -10.0, "take_profit_pct": 30.0,
        "max_hold_days": 30, "trailing_stop_pct": 8.0, "cooldown_days": 0,
    },
    "conservative": {
        "rsi_entry": 30.0, "stop_loss_pct": -5.0, "take_profit_pct": 15.0,
        "max_hold_days": 15, "trailing_stop_pct": 3.0, "vix_max_entry": 25.0,
        "cooldown_days": 2,
    },
    "scalper": {
        "rsi_entry": 35.0, "stop_loss_pct": -3.0, "take_profit_pct": 8.0,
        "max_hold_days": 5, "trailing_stop_pct": 2.0, "cooldown_days": 0,
    },
    "swing": {
        "rsi_entry": 30.0, "stop_loss_pct": -8.0, "take_profit_pct": 25.0,
        "max_hold_days": 40, "trailing_stop_pct": 6.0, "cooldown_days": 2,
    },
}


# ── Indicator computations (numpy-based, matching soxl_live.py) ──

def _compute_rsi(closes: np.ndarray, period: int = 14) -> float | None:
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


def _compute_multi_tf_rsi(closes: np.ndarray) -> dict:
    """Compute RSI across multiple timeframes (7, 14, 21)."""
    return {
        "rsi_7": _compute_rsi(closes, 7),
        "rsi_14": _compute_rsi(closes, 14),
        "rsi_21": _compute_rsi(closes, 21),
    }


def _compute_stoch_rsi(closes: np.ndarray, rsi_period: int = 14, stoch_period: int = 14) -> float | None:
    """Stochastic RSI: (RSI - min_RSI) / (max_RSI - min_RSI) × 100."""
    if len(closes) < rsi_period + stoch_period + 1:
        return None
    # Compute RSI series
    rsi_values = []
    for i in range(stoch_period + 1):
        end_idx = len(closes) - stoch_period + i
        if end_idx < rsi_period + 1:
            return None
        rsi_val = _compute_rsi(closes[:end_idx], rsi_period)
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


def _compute_adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float | None:
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

    # Smoothed averages
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
    # ADX = smoothed average of DX
    adx = sum(dx_values[:period]) / period
    for i in range(period, len(dx_values)):
        adx = (adx * (period - 1) + dx_values[i]) / period
    return float(adx)


def _compute_obv_trend(closes: np.ndarray, volumes: np.ndarray, period: int = 20) -> float | None:
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
    # Linear regression slope of last N OBV values
    obv_window = np.array(obv[-period:], dtype=float)
    x = np.arange(period, dtype=float)
    x_mean = np.mean(x)
    obv_mean = np.mean(obv_window)
    num = np.sum((x - x_mean) * (obv_window - obv_mean))
    den = np.sum((x - x_mean) ** 2)
    if den == 0:
        return 0.0
    slope = num / den
    # Normalize by average volume
    avg_vol = np.mean(volumes[-period:])
    return float(slope / avg_vol) if avg_vol > 0 else 0.0


def _compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float | None:
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


def _compute_macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    """MACD line, signal line, histogram."""
    if len(closes) < slow + signal:
        return None, None, None

    def ema(data, period):
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


def _compute_bollinger(closes: np.ndarray, period=20, std_dev=2.0):
    """Bollinger Bands (upper, middle, lower)."""
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    middle = float(np.mean(window))
    std = float(np.std(window))
    return middle + std_dev * std, middle, middle - std_dev * std


def _compute_volatility_ann(closes: np.ndarray, period=20) -> float | None:
    """Annualized volatility (%)."""
    if len(closes) < period + 1:
        return None
    returns = np.diff(closes[-period - 1:]) / closes[-period - 1:-1]
    return float(np.std(returns) * math.sqrt(252) * 100)


def _compute_disparity(closes: np.ndarray, period=20) -> float | None:
    """Price disparity from MA (%)."""
    if len(closes) < period:
        return None
    ma = float(np.mean(closes[-period:]))
    if ma == 0:
        return None
    return float(closes[-1] / ma * 100)


def _detect_rsi_divergence(closes: np.ndarray, period: int = 14, lookback: int = 5) -> str | None:
    """Detect RSI divergence (bullish/bearish).

    Bullish: price lower low, RSI higher low
    Bearish: price higher high, RSI lower high
    """
    if len(closes) < period + lookback + 1:
        return None
    rsi_vals = []
    for i in range(lookback + 1):
        end_idx = len(closes) - lookback + i
        rsi = _compute_rsi(closes[:end_idx], period)
        if rsi is None:
            return None
        rsi_vals.append(rsi)

    price_window = closes[-lookback - 1:]
    # Bullish divergence: price makes new low but RSI doesn't
    if price_window[-1] < price_window[0] and rsi_vals[-1] > rsi_vals[0]:
        return "bullish"
    # Bearish divergence: price makes new high but RSI doesn't
    if price_window[-1] > price_window[0] and rsi_vals[-1] < rsi_vals[0]:
        return "bearish"
    return None


def _detect_gap(prices: list[dict], idx: int) -> dict | None:
    """Detect overnight gap at given index."""
    if idx < 1:
        return None
    prev_close = prices[idx - 1]["close"]
    cur_open = prices[idx].get("open", prev_close)
    if prev_close == 0:
        return None
    gap_pct = (cur_open - prev_close) / prev_close * 100
    if abs(gap_pct) >= 1.0:  # 1% minimum gap
        return {"gap_pct": round(gap_pct, 2), "direction": "up" if gap_pct > 0 else "down"}
    return None


def _map_macro_keys(macro: dict) -> dict:
    """Map stored macro keys to compute_macro_score expected keys."""
    return {target: macro.get(source) for source, target in _MACRO_KEY_MAP.items()}


class SoxlBacktestEngine:
    """SOXL-specific backtesting with leverage decay, macro gating, geo risk."""

    async def run(
        self,
        start_date: str,
        end_date: str,
        mode: StrategyMode = StrategyMode.FULL,
        params: SoxlBacktestParams | None = None,
    ) -> dict:
        """Run SOXL-only backtest."""
        from app.database.connection import get_db

        if params is None:
            params = SoxlBacktestParams()

        # Validate date range
        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d")
            dt_end = datetime.strptime(end_date, "%Y-%m-%d")
            if dt_end <= dt_start:
                return {"status": "failed", "error": "end_date는 start_date보다 뒤여야 합니다."}
            # [NEW] Max range validation (5 years)
            if (dt_end - dt_start).days > 1826:
                return {"status": "failed", "error": "백테스트 기간은 최대 5년입니다."}
        except ValueError as e:
            return {"status": "failed", "error": f"날짜 형식 오류: {e}"}

        backtest_id = str(uuid4())
        db = await get_db()

        # Save run record
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO soxl_backtest_runs
               (backtest_id, start_date, end_date, mode, params_json, status, started_at)
               VALUES (?, ?, ?, ?, ?, 'running', ?)""",
            (backtest_id, start_date, end_date, mode.value, json.dumps(asdict(params)), now_iso),
        )
        await db.commit()

        try:
            # Load price data (300-day lookback for indicator warmup)
            lookback_date = (dt_start - timedelta(days=300)).strftime("%Y-%m-%d")
            cursor = await db.execute(
                """SELECT trade_date, open, high, low, close, volume
                   FROM price_history
                   WHERE symbol='SOXL' AND market='US'
                   AND trade_date BETWEEN ? AND ?
                   ORDER BY trade_date ASC""",
                (lookback_date, end_date),
            )
            price_rows = await cursor.fetchall()
            if len(price_rows) < 60:
                msg = f"SOXL 가격 데이터 부족 ({len(price_rows)}일, 최소 60일 필요)"
                await self._update_run(db, backtest_id, "failed", error=msg)
                return {"backtest_id": backtest_id, "status": "failed", "error": msg}

            prices = [
                {"date": r[0], "open": r[1], "high": r[2], "low": r[3],
                 "close": r[4], "volume": r[5] or 0}
                for r in price_rows
            ]

            # Load macro data (modes B/C/D only)
            macro_by_date = {}
            if mode in _MACRO_MODES:
                cursor = await db.execute(
                    """SELECT indicator_date, vix, dxy_index, us_10y_yield, us_2y_yield,
                              us_yield_spread, wti_crude, gold_price, copper_price, usd_krw
                       FROM macro_indicators
                       WHERE indicator_date BETWEEN ? AND ?
                       ORDER BY indicator_date ASC""",
                    (lookback_date, end_date),
                )
                for r in await cursor.fetchall():
                    macro_by_date[r[0]] = {
                        "vix": r[1], "dxy": r[2], "us_10y": r[3], "us_2y": r[4],
                        "yield_spread": r[5], "wti": r[6], "gold": r[7],
                        "copper": r[8], "usd_krw": r[9],
                    }

            # Load geo risk scores (modes C/D only)
            geo_scores = {}
            if mode in _GEO_MODES:
                geo_scores = await self._load_geo_scores(db, start_date, end_date)

            # Find trading days within backtest range
            trading_days = [p["date"] for p in prices if start_date <= p["date"] <= end_date]
            if not trading_days:
                await self._update_run(db, backtest_id, "failed", error="백테스트 범위에 거래일 없음")
                return {"backtest_id": backtest_id, "status": "failed", "error": "거래일 없음"}

            # Run simulation
            trades, equity_curve = self._simulate(
                prices, macro_by_date, geo_scores, trading_days, mode, params,
            )

            # [NEW] Compute benchmark (buy-and-hold) return
            benchmark_return = self._compute_benchmark(prices, start_date, end_date)

            # Compute metrics using decay-adjusted returns for mode D
            closed = [t for t in trades if t.get("exit_date")]
            if mode == StrategyMode.FULL:
                metrics_trades = []
                for t in closed:
                    t_copy = dict(t)
                    t_copy["return_pct"] = t.get("return_pct_with_decay", t["return_pct"])
                    metrics_trades.append(t_copy)
                metrics = compute_backtest_metrics(metrics_trades, start_date, end_date)
            else:
                metrics = compute_backtest_metrics(closed, start_date, end_date)

            # [NEW] Compute extended analytics
            monthly_returns = compute_monthly_returns(closed)
            exit_stats = compute_exit_reason_stats(closed)
            drawdown_periods = compute_drawdown_periods(closed)

            # Leverage decay total
            decay_total = sum(
                abs(t.get("return_pct", 0) - t.get("return_pct_with_decay", t.get("return_pct", 0)))
                for t in closed
            )

            # [NEW] Total transaction costs
            total_slippage = len(closed) * 2 * params.slippage_bps / 100  # entry + exit
            total_commission = len(closed) * 2 * params.commission_bps / 100

            # Persist trades
            for t in closed:
                await db.execute(
                    """INSERT INTO soxl_backtest_trades
                       (backtest_id, entry_date, entry_price, entry_signal, entry_score,
                        entry_rsi, entry_vix, entry_macro_score, entry_geo_score,
                        exit_date, exit_price, exit_reason, return_pct, return_pct_with_decay,
                        holding_days, position_size_mult)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (backtest_id, t["entry_date"], t["entry_price"], t["entry_signal"],
                     t.get("entry_score"), t.get("entry_rsi"), t.get("entry_vix"),
                     t.get("entry_macro_score"), t.get("entry_geo_score"),
                     t["exit_date"], t["exit_price"], t["exit_reason"],
                     t["return_pct"], t.get("return_pct_with_decay"),
                     t["holding_days"], t.get("position_size_mult", 1.0)),
                )

            # Update run record
            await db.execute(
                """UPDATE soxl_backtest_runs SET
                   status='completed', total_trades=?, hit_rate=?, avg_return=?,
                   sharpe_ratio=?, max_drawdown=?, profit_factor=?, total_return=?,
                   leverage_decay_total=?, equity_curve_json=?,
                   completed_at=datetime('now')
                   WHERE backtest_id=?""",
                (metrics["total_trades"], metrics["hit_rate"], metrics["avg_return"],
                 metrics["sharpe_ratio"], metrics["max_drawdown"], metrics["profit_factor"],
                 metrics["total_return"], round(decay_total, 2),
                 json.dumps(equity_curve[-200:]),  # More data points for charting
                 backtest_id),
            )
            await db.commit()

            logger.info(
                "SOXL backtest done: id=%s mode=%s trades=%d hit=%.1f%% sharpe=%.2f "
                "sortino=%.2f total=%.1f%% vs_bnh=%.1f%%",
                backtest_id[:8], mode.value, metrics["total_trades"],
                (metrics["hit_rate"] or 0) * 100, metrics["sharpe_ratio"] or 0,
                metrics.get("sortino_ratio") or 0,
                (metrics["total_return"] or 0) * 100, benchmark_return or 0,
            )

            return {
                "backtest_id": backtest_id,
                "status": "completed",
                "mode": mode.value,
                "period": f"{start_date} ~ {end_date}",
                "trading_days": len(trading_days),
                "metrics": metrics,
                "leverage_decay_total": round(decay_total, 2),
                "transaction_costs": {
                    "slippage_total": round(total_slippage, 2),
                    "commission_total": round(total_commission, 2),
                },
                "benchmark_return": benchmark_return,
                "monthly_returns": monthly_returns,
                "exit_reason_stats": exit_stats,
                "drawdown_periods": drawdown_periods[:5],  # Top 5
                "trades": closed,
                "equity_curve": equity_curve,
            }

        except Exception as e:
            logger.error("SOXL backtest failed: %s", e, exc_info=True)
            await self._update_run(db, backtest_id, "failed", error=str(e))
            return {"backtest_id": backtest_id, "status": "failed", "error": str(e)}

    def _simulate(
        self, prices, macro_by_date, geo_scores, trading_days, mode, params,
    ):
        """Core simulation loop for single SOXL symbol."""
        # Build date→index map
        date_idx = {p["date"]: i for i, p in enumerate(prices)}
        trades = []
        equity_curve = []
        position = None
        equity = 100.0  # Start with $100
        last_exit_date = None  # Track for cooldown
        consecutive_losses = 0  # [NEW] Track consecutive losses for sizing

        for day in trading_days:
            idx = date_idx.get(day)
            if idx is None or idx < 60:
                continue

            close = prices[idx]["close"]
            high = prices[idx]["high"]
            low = prices[idx]["low"]

            # Pre-slice windows (200 days max for MACD warmup)
            start_idx = max(0, idx - 199)
            window_closes = np.array(
                [p["close"] for p in prices[start_idx:idx + 1]], dtype=float
            )
            window_highs = np.array(
                [p["high"] for p in prices[start_idx:idx + 1]], dtype=float
            )
            window_lows = np.array(
                [p["low"] for p in prices[start_idx:idx + 1]], dtype=float
            )
            window_volumes = np.array(
                [p["volume"] for p in prices[start_idx:idx + 1]], dtype=float
            )

            # Compute technicals
            rsi = _compute_rsi(window_closes, 14)
            macd_l, macd_s, macd_h = _compute_macd(window_closes)
            bb_u, bb_m, bb_l = _compute_bollinger(window_closes)
            vol_ann = _compute_volatility_ann(window_closes, 20)
            disparity = _compute_disparity(window_closes, 20)

            # [NEW] Extended indicators
            stoch_rsi = _compute_stoch_rsi(window_closes)
            adx = _compute_adx(window_highs, window_lows, window_closes)
            obv_trend = _compute_obv_trend(window_closes, window_volumes)
            atr = _compute_atr(window_highs, window_lows, window_closes)
            rsi_divergence = _detect_rsi_divergence(window_closes)
            gap = _detect_gap(prices, idx)

            # Volume ratio
            vol_ratio = None
            if len(window_volumes) >= 20:
                avg_v = float(np.mean(window_volumes[-20:]))
                if avg_v > 0:
                    vol_ratio = float(window_volumes[-1] / avg_v)

            # Get macro data (nearest available date)
            macro = self._get_nearest_macro(day, macro_by_date) if macro_by_date else None
            vix = macro.get("vix") if macro else None
            geo_score = geo_scores.get(day, 0.0)

            # Compute macro score (modes B/C/D)
            macro_score = 0.0
            if mode in _MACRO_MODES and macro:
                from app.indicators.macro import compute_macro_score
                macro_mapped = _map_macro_keys(macro)
                macro_result = compute_macro_score(macro_mapped)
                macro_score = (
                    macro_result.get("aggregate_score", 0.0)
                    if isinstance(macro_result, dict) else float(macro_result or 0.0)
                )

            # Position sizing multiplier
            pos_mult = self._position_size_multiplier(vix, vol_ann, geo_score, mode, params)

            # [NEW] Consecutive loss reduction
            if consecutive_losses >= params.consecutive_loss_scale:
                pos_mult *= max(0.25, 1.0 - (consecutive_losses - params.consecutive_loss_scale + 1) * 0.25)

            # ── Position management (exit checks first) ──
            if position is not None:
                ret = (close - position["entry_price"]) / position["entry_price"] * 100
                peak_ret = position.get("_peak_ret", ret)
                days_held = (
                    datetime.strptime(day, "%Y-%m-%d") -
                    datetime.strptime(position["entry_date"], "%Y-%m-%d")
                ).days
                exit_reason = None

                # Update peak return for trailing stop
                if ret > peak_ret:
                    peak_ret = ret
                    position["_peak_ret"] = peak_ret

                # [NEW] ATR-based dynamic stop loss
                atr_stop = None
                if atr and mode == StrategyMode.FULL:
                    atr_stop_price = position["entry_price"] - (atr * params.atr_stop_multiplier)
                    atr_stop_pct = (atr_stop_price - position["entry_price"]) / position["entry_price"] * 100
                    atr_stop = atr_stop_pct

                # Exit conditions (priority order)
                effective_stop = params.stop_loss_pct
                if atr_stop is not None:
                    effective_stop = max(params.stop_loss_pct, atr_stop)  # Use less aggressive

                if ret <= effective_stop:
                    exit_reason = "stop_loss"
                elif ret >= params.take_profit_pct:
                    exit_reason = "take_profit"
                elif peak_ret > 5.0 and (peak_ret - ret) >= params.trailing_stop_pct:
                    exit_reason = "trailing_stop"
                elif rsi is not None and rsi >= params.rsi_exit_partial:
                    exit_reason = "rsi_exit"
                elif disparity is not None and disparity >= params.disparity_exit:
                    exit_reason = "disparity_exit"
                elif macd_h is not None and macd_h < 0 and position.get("_prev_macd_h", 0) >= 0:
                    exit_reason = "macd_dead_cross"
                elif days_held >= params.max_hold_days:
                    exit_reason = "time_exit"
                # [NEW] Bearish RSI divergence exit
                elif rsi_divergence == "bearish" and ret > 3.0:
                    exit_reason = "rsi_divergence"
                # Mode C/D: Force exit if geo risk spikes during hold
                elif mode in _GEO_MODES and geo_score >= params.geo_block_threshold:
                    exit_reason = "geo_risk_exit"
                # [NEW] Gap down exit (emergency)
                elif gap and gap["direction"] == "down" and gap["gap_pct"] <= -3.0:
                    exit_reason = "gap_down_exit"

                if exit_reason:
                    # [NEW] Apply slippage
                    slippage_cost = params.slippage_bps / 100 * 2  # entry + exit
                    commission_cost = params.commission_bps / 100 * 2

                    # Apply leverage decay for mode D
                    decay = 0.0
                    ret_with_decay = ret - slippage_cost - commission_cost
                    if mode == StrategyMode.FULL and vol_ann:
                        decay = self._compute_leverage_decay(
                            days_held, vol_ann, params.leverage_factor
                        )
                        ret_with_decay = ret - decay - slippage_cost - commission_cost

                    trade = {
                        **position,
                        "exit_date": day,
                        "exit_price": close,
                        "exit_reason": exit_reason,
                        "return_pct": round(ret, 2),
                        "return_pct_with_decay": round(ret_with_decay, 2),
                        "holding_days": days_held,
                        "gap_on_exit": gap,
                    }
                    trades.append(trade)
                    equity *= (1 + ret_with_decay / 100)
                    position = None
                    last_exit_date = day

                    # [NEW] Track consecutive losses
                    if ret_with_decay <= 0:
                        consecutive_losses += 1
                    else:
                        consecutive_losses = 0
                else:
                    # Track MACD histogram for dead cross detection
                    if macd_h is not None:
                        position["_prev_macd_h"] = macd_h

            # ── Entry signal ──
            if position is None and rsi is not None:
                # Cooldown check
                if last_exit_date and params.cooldown_days > 0:
                    exit_dt = datetime.strptime(last_exit_date, "%Y-%m-%d")
                    cur_dt = datetime.strptime(day, "%Y-%m-%d")
                    if (cur_dt - exit_dt).days < params.cooldown_days:
                        equity_curve.append({"date": day, "equity": round(equity, 2)})
                        continue

                buy_signals = 0
                signal_details = []

                # Technical signals
                if rsi <= params.rsi_entry:
                    buy_signals += 2
                    signal_details.append(f"RSI={rsi:.1f}<={params.rsi_entry}")
                elif rsi <= 40:
                    buy_signals += 1
                    signal_details.append(f"RSI={rsi:.1f}<=40")

                if macd_h is not None and macd_h > 0:
                    buy_signals += 1
                    signal_details.append("MACD+")

                if bb_l is not None and close <= bb_l * 1.02:
                    buy_signals += 1
                    signal_details.append("BB_low")

                if vol_ratio is not None and vol_ratio >= params.volume_min_ratio:
                    buy_signals += 1
                    signal_details.append(f"Vol={vol_ratio:.1f}x")

                # BB bandwidth squeeze (low volatility → potential breakout)
                if bb_u is not None and bb_l is not None and bb_m and bb_m > 0:
                    bb_width = (bb_u - bb_l) / bb_m
                    if bb_width < 0.04:  # Tight squeeze
                        buy_signals += 1
                        signal_details.append("BB_squeeze")

                # [NEW] StochRSI oversold
                if stoch_rsi is not None and stoch_rsi <= params.stoch_rsi_entry:
                    buy_signals += 1
                    signal_details.append(f"StochRSI={stoch_rsi:.0f}")

                # [NEW] ADX trend confirmation
                if adx is not None and adx >= params.adx_min_trend:
                    buy_signals += 1
                    signal_details.append(f"ADX={adx:.0f}")

                # [NEW] OBV positive trend
                if obv_trend is not None and obv_trend > 0.1:
                    buy_signals += 1
                    signal_details.append("OBV+")

                # [NEW] Bullish RSI divergence
                if rsi_divergence == "bullish":
                    buy_signals += 2
                    signal_details.append("RSI_bull_div")

                # [NEW] Gap up momentum
                if gap and gap["direction"] == "up" and gap["gap_pct"] >= 2.0:
                    buy_signals += 1
                    signal_details.append(f"Gap+{gap['gap_pct']:.1f}%")

                # Hard limits
                if rsi >= params.rsi_hard_limit:
                    buy_signals = 0

                # Mode B+: Macro gating
                if mode in _MACRO_MODES:
                    if vix is not None and vix > params.vix_max_entry:
                        buy_signals = 0  # Block entry in high-VIX
                    if macro_score < params.macro_score_min:
                        buy_signals = max(0, buy_signals - 1)

                # Mode C+: Geo risk gating
                if mode in _GEO_MODES:
                    if geo_score >= params.geo_block_threshold:
                        buy_signals = 0  # Block entry
                    elif geo_score >= params.geo_reduce_threshold:
                        buy_signals = max(0, buy_signals - 1)  # Reduce signals

                # Enter if enough signals and position sizing allows
                if buy_signals >= 2 and pos_mult > 0:
                    score = buy_signals * 10 + (50 - (rsi or 50))

                    # [NEW] Kelly criterion position sizing
                    kelly_mult = 1.0
                    if params.use_kelly_sizing and len(trades) >= 10:
                        win_trades = [t for t in trades if t.get("return_pct", 0) > 0]
                        if win_trades and len(trades) > 0:
                            win_prob = len(win_trades) / len(trades)
                            avg_w = sum(t["return_pct"] for t in win_trades) / len(win_trades)
                            loss_trades = [t for t in trades if t.get("return_pct", 0) <= 0]
                            avg_l = abs(sum(t["return_pct"] for t in loss_trades) / len(loss_trades)) if loss_trades else 1
                            if avg_l > 0:
                                kelly = win_prob - ((1 - win_prob) / (avg_w / avg_l))
                                kelly_mult = max(0.1, min(1.0, kelly * 0.5))  # Half-Kelly

                    position = {
                        "entry_date": day,
                        "entry_price": close,
                        "entry_signal": "BUY",
                        "entry_score": round(score, 1),
                        "entry_rsi": round(rsi, 1) if rsi else None,
                        "entry_vix": round(vix, 1) if vix else None,
                        "entry_macro_score": round(macro_score, 2),
                        "entry_geo_score": round(geo_score, 1),
                        "entry_adx": round(adx, 1) if adx else None,
                        "entry_stoch_rsi": round(stoch_rsi, 1) if stoch_rsi else None,
                        "entry_atr": round(atr, 2) if atr else None,
                        "position_size_mult": round(pos_mult * kelly_mult, 2),
                        "signal_details": signal_details,
                        "_prev_macd_h": macd_h or 0,
                        "_peak_ret": 0.0,
                    }

            equity_curve.append({"date": day, "equity": round(equity, 2)})

        # Force close any open position at backtest end
        if position is not None:
            last_price = prices[-1]["close"]
            last_date = prices[-1]["date"]
            entry_price = position["entry_price"]
            ret = (last_price - entry_price) / entry_price * 100
            days_held = (
                datetime.strptime(last_date, "%Y-%m-%d") -
                datetime.strptime(position["entry_date"], "%Y-%m-%d")
            ).days
            decay = 0.0
            slippage_cost = params.slippage_bps / 100 * 2
            commission_cost = params.commission_bps / 100 * 2
            ret_with_decay = ret - slippage_cost - commission_cost
            if mode == StrategyMode.FULL:
                end_closes = np.array(
                    [p["close"] for p in prices[-30:]], dtype=float
                )
                end_vol = _compute_volatility_ann(end_closes, 20)
                if end_vol:
                    decay = self._compute_leverage_decay(
                        days_held, end_vol, params.leverage_factor
                    )
                    ret_with_decay = ret - decay - slippage_cost - commission_cost

            trades.append({
                **position,
                "exit_date": last_date,
                "exit_price": last_price,
                "exit_reason": "backtest_end",
                "return_pct": round(ret, 2),
                "return_pct_with_decay": round(ret_with_decay, 2),
                "holding_days": days_held,
            })
            equity *= (1 + ret_with_decay / 100)
            equity_curve.append({"date": last_date, "equity": round(equity, 2)})

        # Clean internal tracking keys from trades before returning
        _internal_keys = ("_prev_macd_h", "_peak_ret")
        for t in trades:
            for k in _internal_keys:
                t.pop(k, None)

        return trades, equity_curve

    @staticmethod
    def _compute_leverage_decay(holding_days: int, vol_ann: float, leverage: float) -> float:
        """Estimate 3x daily rebalancing decay.

        decay_per_day ≈ (L² - L) × daily_variance / 2
        For L=3: decay_per_day ≈ 3 × daily_vol²
        """
        if holding_days <= 0 or not vol_ann:
            return 0.0
        daily_vol = vol_ann / (100 * math.sqrt(252))
        daily_decay = (leverage ** 2 - leverage) * daily_vol ** 2 / 2
        return daily_decay * holding_days * 100  # Convert to pct

    @staticmethod
    def _position_size_multiplier(vix, vol_ann, geo_score, mode, params):
        """Return 0.0-1.0 multiplier for position sizing based on risk factors."""
        mult = 1.0

        if mode in _MACRO_MODES:
            if vix is not None:
                if vix >= 40:
                    return 0.0  # Extreme VIX → block entirely
                elif vix >= 35:
                    mult *= 0.25  # Very high VIX → minimal
                elif vix >= params.vix_reduction_threshold:
                    mult *= 0.5  # High VIX → half

        if mode == StrategyMode.FULL:
            if vol_ann is not None and vol_ann >= params.vol_reduction_threshold:
                mult *= 0.5

        if mode in _GEO_MODES:
            if geo_score >= params.geo_block_threshold:
                return 0.0
            elif geo_score >= params.geo_reduce_threshold:
                mult *= 0.5

        return mult

    @staticmethod
    def _compute_benchmark(prices: list[dict], start_date: str, end_date: str) -> float | None:
        """Compute buy-and-hold return for SOXL over the period."""
        start_price = None
        end_price = None
        for p in prices:
            if p["date"] >= start_date and start_price is None:
                start_price = p["close"]
            if p["date"] <= end_date:
                end_price = p["close"]
        if start_price and end_price and start_price > 0:
            return round((end_price - start_price) / start_price * 100, 2)
        return None

    @staticmethod
    def _get_nearest_macro(target_date, macro_by_date):
        """Get macro data for the nearest available date (up to 7 days back)."""
        if target_date in macro_by_date:
            return macro_by_date[target_date]
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        for i in range(1, 8):
            d = (dt - timedelta(days=i)).strftime("%Y-%m-%d")
            if d in macro_by_date:
                return macro_by_date[d]
        return None

    async def _load_geo_scores(self, db, start_date, end_date):
        """Compute daily geopolitical risk score (0-100) from events.

        Uses severity weighting + recency decay:
        - severe_negative: weight=25
        - negative: weight=15
        - neutral: weight=5
        - positive: weight=-10

        Recency: full (≤7d), 0.5× (≤14d), 0.25× (≤30d)
        """
        cursor = await db.execute(
            """SELECT event_date, impact FROM geopolitical_events
               WHERE event_date BETWEEN ? AND ?
               ORDER BY event_date ASC""",
            (
                (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d"),
                (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"),
            ),
        )
        events = await cursor.fetchall()
        if not events:
            return {}

        impact_weight = {
            "severe_negative": 25, "negative": 15, "neutral": 5, "positive": -10,
        }

        # Pre-parse event dates
        parsed_events = []
        for evt_date, impact in events:
            try:
                parsed_events.append((datetime.strptime(evt_date, "%Y-%m-%d"), impact))
            except (ValueError, TypeError):
                continue

        scores = {}
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")
        current = dt_start

        while current <= dt_end:
            day_str = current.strftime("%Y-%m-%d")
            score = 0.0
            for evt_dt, impact in parsed_events:
                delta = abs((current - evt_dt).days)
                if delta > 30:
                    continue
                w = impact_weight.get(impact, 5)
                if delta <= 7:
                    recency = 1.0
                elif delta <= 14:
                    recency = 0.5
                else:
                    recency = 0.25
                score += w * recency

            scores[day_str] = max(0, min(100, score))
            current += timedelta(days=1)

        return scores

    @staticmethod
    async def _update_run(db, backtest_id, status, error=None):
        await db.execute(
            """UPDATE soxl_backtest_runs SET status=?, results_json=?,
               completed_at=datetime('now') WHERE backtest_id=?""",
            (status, json.dumps({"error": error}) if error else None, backtest_id),
        )
        await db.commit()
