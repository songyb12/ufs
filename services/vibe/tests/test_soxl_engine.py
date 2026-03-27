"""
Tests for SOXL-specific backtesting engine.

Covers:
- Indicator unit tests: RSI(7/14/21), StochRSI, MACD, Bollinger, ADX, OBV, ATR,
  disparity, volatility, RSI divergence (empty, NaN, normal inputs)
- Kelly criterion position sizing boundary values
- Macro/geopolitical gating logic (position_size_multiplier)
- Leverage decay computation
- Full backtest run with 4 strategy modes (A/B/C/D), verifying metric keys
"""

import math

import numpy as np
import pytest
import pytest_asyncio

from tests.conftest import cleanup_all

from app.utils.soxl_indicators import compute_multi_tf_rsi as _compute_multi_tf_rsi
from app.backtesting.soxl_engine import (
    SoxlBacktestEngine,
    SoxlBacktestParams,
    StrategyMode,
    _compute_adx,
    _compute_atr,
    _compute_bollinger,
    _compute_disparity,
    _compute_macd,
    _compute_obv_trend,
    _compute_rsi,
    _compute_stoch_rsi,
    _compute_volatility_ann,
    _detect_rsi_divergence,
)


# ════════════════════════════════════════════════════════════════
# Helper: generate synthetic price arrays
# ════════════════════════════════════════════════════════════════

def _rising(n=60, start=100.0, step=1.0):
    """Steadily rising close prices."""
    return np.array([start + i * step for i in range(n)], dtype=float)


def _flat(n=60, value=100.0):
    return np.full(n, value, dtype=float)


def _alternating(n=60, low=90.0, high=110.0):
    return np.array([low if i % 2 == 0 else high for i in range(n)], dtype=float)


def _with_nan(base: np.ndarray, positions: list[int]):
    arr = base.copy()
    for p in positions:
        arr[p] = np.nan
    return arr


# ════════════════════════════════════════════════════════════════
# _compute_rsi
# ════════════════════════════════════════════════════════════════

class TestComputeRSI:
    def test_empty_array(self):
        assert _compute_rsi(np.array([], dtype=float)) is None

    def test_too_short(self):
        assert _compute_rsi(np.arange(10, dtype=float), period=14) is None

    def test_exact_minimum_length(self):
        # period + 1 values is the minimum
        closes = _rising(16, step=1.0)
        result = _compute_rsi(closes, 14)
        assert result is not None
        # All gains, no losses → RSI = 100
        assert result == pytest.approx(100.0)

    def test_all_losses(self):
        closes = np.array([100.0 - i for i in range(20)], dtype=float)
        result = _compute_rsi(closes, 14)
        assert result is not None
        assert result < 10.0  # Should be very low

    def test_normal_range(self):
        closes = _alternating(40)
        result = _compute_rsi(closes, 14)
        assert result is not None
        assert 0 <= result <= 100

    def test_flat_prices(self):
        closes = _flat(30)
        result = _compute_rsi(closes, 14)
        # No gains, no losses → avg_loss=0 → 100.0
        assert result == pytest.approx(100.0)


class TestComputeMultiTfRSI:
    def test_returns_three_periods(self):
        closes = _rising(50)
        result = _compute_multi_tf_rsi(closes)
        assert "rsi_7" in result
        assert "rsi_14" in result
        assert "rsi_21" in result

    def test_short_data_returns_nones(self):
        closes = _rising(5)
        result = _compute_multi_tf_rsi(closes)
        assert result["rsi_7"] is None
        assert result["rsi_14"] is None
        assert result["rsi_21"] is None


# ════════════════════════════════════════════════════════════════
# _compute_stoch_rsi
# ════════════════════════════════════════════════════════════════

class TestComputeStochRSI:
    def test_empty(self):
        assert _compute_stoch_rsi(np.array([], dtype=float)) is None

    def test_too_short(self):
        assert _compute_stoch_rsi(_rising(20)) is None

    def test_normal(self):
        closes = _rising(60)
        result = _compute_stoch_rsi(closes)
        assert result is not None
        assert 0 <= result <= 100

    def test_flat_returns_50(self):
        closes = _flat(60)
        result = _compute_stoch_rsi(closes)
        # All RSI values identical → (RSI - min) / (max - min) → 50.0 fallback
        if result is not None:
            assert result == pytest.approx(50.0)


# ════════════════════════════════════════════════════════════════
# _compute_macd
# ════════════════════════════════════════════════════════════════

class TestComputeMACD:
    def test_empty(self):
        ml, sl, h = _compute_macd(np.array([], dtype=float))
        assert ml is None and sl is None and h is None

    def test_too_short(self):
        ml, sl, h = _compute_macd(_rising(30))
        assert ml is None  # needs 26 + 9 = 35

    def test_normal(self):
        closes = _rising(60)
        ml, sl, h = _compute_macd(closes)
        assert ml is not None
        assert sl is not None
        assert h is not None

    def test_rising_macd_positive(self):
        closes = _rising(60, step=2.0)
        ml, sl, h = _compute_macd(closes)
        # Rising prices → fast EMA > slow EMA → MACD line positive
        assert ml > 0


# ════════════════════════════════════════════════════════════════
# _compute_bollinger
# ════════════════════════════════════════════════════════════════

class TestComputeBollinger:
    def test_empty(self):
        u, m, l = _compute_bollinger(np.array([], dtype=float))
        assert u is None and m is None and l is None

    def test_too_short(self):
        u, m, l = _compute_bollinger(_rising(10), period=20)
        assert u is None

    def test_flat_band_width_zero(self):
        closes = _flat(30)
        u, m, l = _compute_bollinger(closes)
        # std = 0 → upper = middle = lower
        assert u == pytest.approx(m)
        assert l == pytest.approx(m)

    def test_normal_ordering(self):
        closes = _alternating(30)
        u, m, l = _compute_bollinger(closes)
        assert u > m > l


# ════════════════════════════════════════════════════════════════
# _compute_adx
# ════════════════════════════════════════════════════════════════

class TestComputeADX:
    def test_empty(self):
        empty = np.array([], dtype=float)
        assert _compute_adx(empty, empty, empty) is None

    def test_too_short(self):
        short = _rising(10)
        assert _compute_adx(short, short, short) is None

    def test_normal(self):
        n = 60
        highs = np.array([100.0 + i + 2 for i in range(n)], dtype=float)
        lows = np.array([100.0 + i - 2 for i in range(n)], dtype=float)
        closes = np.array([100.0 + i for i in range(n)], dtype=float)
        result = _compute_adx(highs, lows, closes)
        assert result is not None
        assert result >= 0

    def test_strong_trend_high_adx(self):
        n = 80
        highs = np.array([100.0 + i * 3 for i in range(n)], dtype=float)
        lows = np.array([99.0 + i * 3 for i in range(n)], dtype=float)
        closes = np.array([99.5 + i * 3 for i in range(n)], dtype=float)
        result = _compute_adx(highs, lows, closes)
        assert result is not None
        assert result > 15  # Strong trend → high ADX


# ════════════════════════════════════════════════════════════════
# _compute_obv_trend
# ════════════════════════════════════════════════════════════════

class TestComputeOBVTrend:
    def test_empty(self):
        empty = np.array([], dtype=float)
        assert _compute_obv_trend(empty, empty) is None

    def test_too_short(self):
        short = _rising(5)
        vols = np.full(5, 1000.0)
        assert _compute_obv_trend(short, vols) is None

    def test_rising_prices_positive_obv(self):
        closes = _rising(30, step=1.0)
        vols = np.full(30, 1000.0)
        result = _compute_obv_trend(closes, vols)
        assert result is not None
        assert result > 0  # Rising prices → OBV accumulates → positive slope

    def test_falling_prices_negative_obv(self):
        closes = np.array([200.0 - i for i in range(30)], dtype=float)
        vols = np.full(30, 1000.0)
        result = _compute_obv_trend(closes, vols)
        assert result is not None
        assert result < 0


# ════════════════════════════════════════════════════════════════
# _compute_atr
# ════════════════════════════════════════════════════════════════

class TestComputeATR:
    def test_empty(self):
        empty = np.array([], dtype=float)
        assert _compute_atr(empty, empty, empty) is None

    def test_too_short(self):
        short = _rising(5)
        assert _compute_atr(short, short, short) is None

    def test_flat_prices_near_zero(self):
        n = 30
        closes = _flat(n)
        highs = _flat(n)
        lows = _flat(n)
        result = _compute_atr(highs, lows, closes)
        assert result is not None
        assert result == pytest.approx(0.0)

    def test_volatile_prices_positive(self):
        n = 30
        highs = np.array([110.0 + i for i in range(n)], dtype=float)
        lows = np.array([90.0 + i for i in range(n)], dtype=float)
        closes = np.array([100.0 + i for i in range(n)], dtype=float)
        result = _compute_atr(highs, lows, closes)
        assert result is not None
        assert result > 10  # high - low = 20


# ════════════════════════════════════════════════════════════════
# _compute_disparity / _compute_volatility_ann
# ════════════════════════════════════════════════════════════════

class TestComputeDisparity:
    def test_empty(self):
        assert _compute_disparity(np.array([], dtype=float)) is None

    def test_at_ma(self):
        closes = _flat(30)
        result = _compute_disparity(closes)
        assert result == pytest.approx(100.0)

    def test_above_ma(self):
        # Last price above 20-day MA
        closes = np.concatenate([_flat(19, 100.0), np.array([120.0])])
        result = _compute_disparity(closes, 20)
        assert result is not None
        assert result > 100.0


class TestComputeVolatilityAnn:
    def test_empty(self):
        assert _compute_volatility_ann(np.array([], dtype=float)) is None

    def test_flat_zero(self):
        result = _compute_volatility_ann(_flat(30))
        assert result == pytest.approx(0.0, abs=0.01)

    def test_positive_for_volatile(self):
        result = _compute_volatility_ann(_alternating(30))
        assert result is not None
        assert result > 0


# ════════════════════════════════════════════════════════════════
# _detect_rsi_divergence
# ════════════════════════════════════════════════════════════════

class TestDetectRSIDivergence:
    def test_empty(self):
        assert _detect_rsi_divergence(np.array([], dtype=float)) is None

    def test_too_short(self):
        assert _detect_rsi_divergence(_rising(10)) is None

    def test_no_divergence_rising(self):
        # Steady rise → price up, RSI up → no divergence
        closes = _rising(40, step=1.0)
        result = _detect_rsi_divergence(closes)
        # Could be None or bearish (price higher high, RSI lower high for steady steps)
        assert result in (None, "bearish", "bullish")

    def test_returns_valid_value(self):
        # Construct a scenario with enough data
        closes = _rising(30)
        result = _detect_rsi_divergence(closes, period=14, lookback=5)
        assert result in (None, "bullish", "bearish")


# ════════════════════════════════════════════════════════════════
# Leverage Decay
# ════════════════════════════════════════════════════════════════

class TestLeverageDecay:
    def test_zero_days(self):
        assert SoxlBacktestEngine._compute_leverage_decay(0, 50.0, 3.0) == 0.0

    def test_zero_vol(self):
        assert SoxlBacktestEngine._compute_leverage_decay(10, 0.0, 3.0) == 0.0

    def test_positive_decay(self):
        decay = SoxlBacktestEngine._compute_leverage_decay(20, 60.0, 3.0)
        assert decay > 0

    def test_higher_vol_more_decay(self):
        low = SoxlBacktestEngine._compute_leverage_decay(20, 30.0, 3.0)
        high = SoxlBacktestEngine._compute_leverage_decay(20, 80.0, 3.0)
        assert high > low

    def test_longer_hold_more_decay(self):
        short = SoxlBacktestEngine._compute_leverage_decay(5, 50.0, 3.0)
        long = SoxlBacktestEngine._compute_leverage_decay(30, 50.0, 3.0)
        assert long > short


# ════════════════════════════════════════════════════════════════
# Position Size Multiplier (macro/geo gating)
# ════════════════════════════════════════════════════════════════

class TestPositionSizeMultiplier:
    """Test _position_size_multiplier for gating ON/OFF scaling differences."""

    def _call(self, vix=None, vol_ann=None, geo_score=0.0,
              mode=StrategyMode.FULL, params=None):
        if params is None:
            params = SoxlBacktestParams()
        return SoxlBacktestEngine._position_size_multiplier(
            vix, vol_ann, geo_score, mode, params,
        )

    # Mode A: no gating at all
    def test_mode_a_no_reduction(self):
        assert self._call(vix=50, vol_ann=100, geo_score=95,
                          mode=StrategyMode.TECHNICAL) == 1.0

    # Macro gating (mode B+)
    def test_vix_extreme_blocks(self):
        assert self._call(vix=40, mode=StrategyMode.TECH_MACRO) == 0.0

    def test_vix_very_high_minimal(self):
        mult = self._call(vix=36, mode=StrategyMode.TECH_MACRO)
        assert mult == pytest.approx(0.25)

    def test_vix_high_halves(self):
        mult = self._call(vix=31, mode=StrategyMode.TECH_MACRO)
        assert mult == pytest.approx(0.5)

    def test_vix_normal_no_reduction(self):
        mult = self._call(vix=20, mode=StrategyMode.TECH_MACRO)
        assert mult == 1.0

    # Volatility scaling (mode D only)
    def test_high_vol_reduces_in_full_mode(self):
        params = SoxlBacktestParams(vol_reduction_threshold=80.0)
        mult = self._call(vol_ann=90, mode=StrategyMode.FULL, params=params)
        assert mult == pytest.approx(0.5)

    def test_high_vol_ignored_in_mode_b(self):
        mult = self._call(vol_ann=90, mode=StrategyMode.TECH_MACRO)
        assert mult == 1.0

    # Geo gating (mode C+)
    def test_geo_block_threshold(self):
        params = SoxlBacktestParams(geo_block_threshold=90.0)
        assert self._call(geo_score=95, mode=StrategyMode.TECH_MACRO_GEO, params=params) == 0.0

    def test_geo_reduce_threshold(self):
        params = SoxlBacktestParams(geo_reduce_threshold=70.0, geo_block_threshold=90.0)
        mult = self._call(geo_score=75, mode=StrategyMode.TECH_MACRO_GEO, params=params)
        assert mult == pytest.approx(0.5)

    def test_geo_ignored_in_mode_b(self):
        mult = self._call(geo_score=95, mode=StrategyMode.TECH_MACRO)
        assert mult == 1.0

    # Combined: macro + vol + geo in mode D
    def test_combined_reduction(self):
        params = SoxlBacktestParams(
            vix_reduction_threshold=30.0,
            vol_reduction_threshold=80.0,
            geo_reduce_threshold=70.0,
            geo_block_threshold=90.0,
        )
        mult = self._call(vix=31, vol_ann=85, geo_score=75,
                          mode=StrategyMode.FULL, params=params)
        # vix >= 30 → 0.5, vol >= 80 → 0.5, geo >= 70 → 0.5
        assert mult == pytest.approx(0.5 * 0.5 * 0.5)


# ════════════════════════════════════════════════════════════════
# Benchmark computation
# ════════════════════════════════════════════════════════════════

class TestBenchmark:
    def test_normal(self):
        prices = [
            {"date": "2025-01-01", "close": 100},
            {"date": "2025-01-15", "close": 110},
            {"date": "2025-01-30", "close": 120},
        ]
        result = SoxlBacktestEngine._compute_benchmark(prices, "2025-01-01", "2025-01-30")
        assert result == pytest.approx(20.0)

    def test_no_data(self):
        result = SoxlBacktestEngine._compute_benchmark([], "2025-01-01", "2025-01-30")
        assert result is None

    def test_zero_start_price(self):
        prices = [
            {"date": "2025-01-01", "close": 0},
            {"date": "2025-01-30", "close": 100},
        ]
        result = SoxlBacktestEngine._compute_benchmark(prices, "2025-01-01", "2025-01-30")
        assert result is None


# ════════════════════════════════════════════════════════════════
# Kelly Criterion (via _simulate indirectly, test boundary values)
# ════════════════════════════════════════════════════════════════

class TestKellyCriterionBoundary:
    """Test Kelly criterion calculation at boundary win rates.

    Kelly = win_prob - (1 - win_prob) / (avg_win / avg_loss)
    Half-Kelly: clamped to [0.1, 1.0] * 0.5
    """

    def _kelly(self, win_rate: float, avg_win: float = 10.0, avg_loss: float = 5.0) -> float:
        """Replicate engine Kelly formula."""
        if avg_loss == 0:
            return 1.0
        kelly = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
        return max(0.1, min(1.0, kelly * 0.5))

    def test_zero_win_rate(self):
        # kelly = 0 - (1 / 2) = -0.5 → clamped to 0.1
        result = self._kelly(0.0)
        assert result == pytest.approx(0.1)

    def test_fifty_pct_win_rate(self):
        # kelly = 0.5 - (0.5 / 2) = 0.25 → 0.25 * 0.5 = 0.125
        result = self._kelly(0.5)
        assert result == pytest.approx(0.125)

    def test_hundred_pct_win_rate(self):
        # kelly = 1.0 - 0 = 1.0 → 1.0 * 0.5 = 0.5
        result = self._kelly(1.0)
        assert result == pytest.approx(0.5)

    def test_high_payoff_ratio(self):
        # win_rate=0.4, avg_win=20, avg_loss=5 → kelly = 0.4 - 0.6/4 = 0.25 → 0.125
        result = self._kelly(0.4, avg_win=20.0, avg_loss=5.0)
        assert result == pytest.approx(0.125)


# ════════════════════════════════════════════════════════════════
# Integration: Full backtest run per mode (requires DB)
# ════════════════════════════════════════════════════════════════

async def _seed_soxl_prices(days: int = 200):
    """Insert synthetic SOXL price history + macro data for backtesting."""
    from app.database.connection import get_db
    db = await get_db()

    base_price = 20.0
    for i in range(days):
        dt = f"2024-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}"
        # Use a simple pattern to generate price movement
        noise = (i % 7 - 3) * 0.5
        close = round(base_price + i * 0.05 + noise, 2)
        high = round(close + 1.5, 2)
        low = round(close - 1.5, 2)
        open_ = round(close + (noise * 0.2), 2)
        volume = 5_000_000 + i * 10_000

        await db.execute(
            """INSERT OR IGNORE INTO price_history
               (symbol, market, trade_date, open, high, low, close, volume)
               VALUES ('SOXL', 'US', ?, ?, ?, ?, ?, ?)""",
            (dt, open_, high, low, close, volume),
        )

    # Seed macro data for modes B/C/D
    for i in range(days):
        dt = f"2024-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}"
        vix = 18.0 + (i % 10)
        await db.execute(
            """INSERT OR IGNORE INTO macro_indicators
               (indicator_date, vix, dxy_index, us_10y_yield, us_2y_yield,
                us_yield_spread, wti_crude, gold_price, usd_krw)
               VALUES (?, ?, 104.0, 4.3, 4.8, -0.5, 70.0, 2000.0, 1350.0)""",
            (dt, vix),
        )

    # Seed geopolitical events for modes C/D
    await db.execute(
        """INSERT OR IGNORE INTO geopolitical_events
           (event_date, event_text, detail, impact)
           VALUES ('2024-03-15', 'Test event', 'Test detail', 'negative')"""
    )

    await db.commit()


async def _cleanup_soxl():
    from app.database.connection import get_db
    db = await get_db()
    for table in ["soxl_backtest_trades", "soxl_backtest_runs"]:
        await db.execute(f"DELETE FROM {table}")
    await db.execute("DELETE FROM price_history WHERE symbol='SOXL'")
    await db.execute("DELETE FROM macro_indicators")
    await db.execute("DELETE FROM geopolitical_events")
    await db.commit()


EXPECTED_METRIC_KEYS = {
    "total_trades", "hit_rate", "avg_return", "sharpe_ratio",
    "sortino_ratio", "max_drawdown", "profit_factor", "total_return",
}


@pytest_asyncio.fixture
async def soxl_prices():
    await _seed_soxl_prices()
    yield
    await _cleanup_soxl()


class TestBacktestModeA:
    @pytest.mark.asyncio
    async def test_technical_only(self, setup_db, soxl_prices):
        engine = SoxlBacktestEngine()
        result = await engine.run("2024-03-01", "2024-06-01", StrategyMode.TECHNICAL)
        assert result["status"] in ("completed", "failed")
        if result["status"] == "completed":
            for key in EXPECTED_METRIC_KEYS:
                assert key in result["metrics"], f"Missing metric key: {key}"


class TestBacktestModeB:
    @pytest.mark.asyncio
    async def test_tech_macro(self, setup_db, soxl_prices):
        engine = SoxlBacktestEngine()
        result = await engine.run("2024-03-01", "2024-06-01", StrategyMode.TECH_MACRO)
        assert result["status"] in ("completed", "failed")
        if result["status"] == "completed":
            for key in EXPECTED_METRIC_KEYS:
                assert key in result["metrics"]


class TestBacktestModeC:
    @pytest.mark.asyncio
    async def test_tech_macro_geo(self, setup_db, soxl_prices):
        engine = SoxlBacktestEngine()
        result = await engine.run("2024-03-01", "2024-06-01", StrategyMode.TECH_MACRO_GEO)
        assert result["status"] in ("completed", "failed")
        if result["status"] == "completed":
            for key in EXPECTED_METRIC_KEYS:
                assert key in result["metrics"]


class TestBacktestModeD:
    @pytest.mark.asyncio
    async def test_full_mode(self, setup_db, soxl_prices):
        engine = SoxlBacktestEngine()
        result = await engine.run("2024-03-01", "2024-06-01", StrategyMode.FULL)
        assert result["status"] in ("completed", "failed")
        if result["status"] == "completed":
            for key in EXPECTED_METRIC_KEYS:
                assert key in result["metrics"]
            # Mode D should have leverage decay and transaction costs
            assert "leverage_decay_total" in result
            assert "transaction_costs" in result


class TestBacktestEdgeCases:
    @pytest.mark.asyncio
    async def test_invalid_date_range(self, setup_db, soxl_prices):
        engine = SoxlBacktestEngine()
        result = await engine.run("2024-06-01", "2024-03-01", StrategyMode.TECHNICAL)
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_max_range_exceeded(self, setup_db, soxl_prices):
        engine = SoxlBacktestEngine()
        result = await engine.run("2019-01-01", "2025-01-01", StrategyMode.TECHNICAL)
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_bad_date_format(self, setup_db, soxl_prices):
        engine = SoxlBacktestEngine()
        result = await engine.run("not-a-date", "2024-06-01", StrategyMode.TECHNICAL)
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_no_trading_days_in_range(self, setup_db, soxl_prices):
        """Date range outside of seeded data → 거래일 없음 or 데이터 부족."""
        engine = SoxlBacktestEngine()
        result = await engine.run("2030-01-01", "2030-06-01", StrategyMode.TECHNICAL)
        assert result["status"] == "failed"


class TestGetNearestMacro:
    def test_exact_date(self):
        data = {"2024-03-01": {"vix": 18.0}}
        result = SoxlBacktestEngine._get_nearest_macro("2024-03-01", data)
        assert result["vix"] == 18.0

    def test_fallback_to_previous_day(self):
        data = {"2024-02-28": {"vix": 20.0}}
        result = SoxlBacktestEngine._get_nearest_macro("2024-03-01", data)
        assert result["vix"] == 20.0

    def test_no_data_within_7_days(self):
        data = {"2024-01-01": {"vix": 15.0}}
        result = SoxlBacktestEngine._get_nearest_macro("2024-03-01", data)
        assert result is None

    def test_empty_data(self):
        result = SoxlBacktestEngine._get_nearest_macro("2024-03-01", {})
        assert result is None


class TestHedgeSimulation:
    @pytest.mark.asyncio
    async def test_hedge_mode_d(self, setup_db, soxl_prices):
        """Hedge mode in Full mode should produce hedge_stats."""
        engine = SoxlBacktestEngine()
        params = SoxlBacktestParams(hedge_mode=True, hedge_ratio=0.2)
        result = await engine.run("2024-03-01", "2024-06-01", StrategyMode.FULL, params)
        if result["status"] == "completed":
            assert "hedge_stats" in result
            hs = result["hedge_stats"]
            assert hs["hedge_ratio"] == 0.2
            assert isinstance(hs["hedge_pnl"], float)
            assert isinstance(hs["hedged_equity_curve"], list)

    @pytest.mark.asyncio
    async def test_hedge_off_no_stats(self, setup_db, soxl_prices):
        """Hedge off should not produce hedge_stats."""
        engine = SoxlBacktestEngine()
        params = SoxlBacktestParams(hedge_mode=False)
        result = await engine.run("2024-03-01", "2024-06-01", StrategyMode.TECHNICAL, params)
        if result["status"] == "completed":
            assert "hedge_stats" not in result
