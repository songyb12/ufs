"""Tests for app.backtesting.metrics — backtest metric calculations."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.backtesting.metrics import compute_backtest_metrics


class TestComputeBacktestMetricsEmpty:
    def test_empty_trades(self):
        r = compute_backtest_metrics([])
        assert r["total_trades"] == 0
        assert r["hit_rate"] is None
        assert r["avg_return"] is None
        assert r["sharpe_ratio"] is None
        assert r["max_drawdown"] is None

    def test_no_valid_returns(self):
        trades = [{"holding_days": 10}, {"holding_days": 5}]
        r = compute_backtest_metrics(trades)
        assert r["total_trades"] == 2
        assert r["hit_rate"] is None


class TestComputeBacktestMetricsSingle:
    def test_single_winning_trade(self):
        trades = [{"return_pct": 10.0, "holding_days": 20}]
        r = compute_backtest_metrics(trades)
        assert r["total_trades"] == 1
        assert r["hit_rate"] == 1.0
        assert r["avg_return"] == 10.0
        assert r["total_return"] is not None
        assert r["max_drawdown"] == 0

    def test_single_losing_trade(self):
        trades = [{"return_pct": -5.0, "holding_days": 10}]
        r = compute_backtest_metrics(trades)
        assert r["hit_rate"] == 0.0
        assert r["avg_return"] == -5.0
        assert r["max_drawdown"] is not None


class TestComputeBacktestMetricsMultiple:
    def test_mixed_trades(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 20},
            {"return_pct": -5.0, "holding_days": 15},
            {"return_pct": 8.0, "holding_days": 25},
            {"return_pct": -3.0, "holding_days": 10},
            {"return_pct": 12.0, "holding_days": 30},
        ]
        r = compute_backtest_metrics(trades)
        assert r["total_trades"] == 5
        assert r["hit_rate"] == 0.6  # 3 wins out of 5
        assert r["avg_return"] is not None
        assert r["sharpe_ratio"] is not None
        assert r["max_drawdown"] is not None
        assert r["profit_factor"] is not None
        assert r["win_loss_ratio"] is not None

    def test_all_winning(self):
        trades = [
            {"return_pct": 5.0, "holding_days": 10},
            {"return_pct": 8.0, "holding_days": 15},
            {"return_pct": 3.0, "holding_days": 20},
        ]
        r = compute_backtest_metrics(trades)
        assert r["hit_rate"] == 1.0
        assert r["profit_factor"] is not None
        assert r["max_drawdown"] == 0

    def test_all_losing(self):
        trades = [
            {"return_pct": -3.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 15},
            {"return_pct": -2.0, "holding_days": 20},
        ]
        r = compute_backtest_metrics(trades)
        assert r["hit_rate"] == 0.0
        assert r["profit_factor"] == 0
        assert r["max_drawdown"] is not None
        assert r["max_drawdown"] > 0  # max_drawdown is positive (absolute pct)

    def test_sharpe_capped(self):
        # Extreme positive returns with very low variance
        trades = [
            {"return_pct": 100.0, "holding_days": 5},
            {"return_pct": 100.0, "holding_days": 5},
            {"return_pct": 100.0, "holding_days": 5},
        ]
        r = compute_backtest_metrics(trades)
        if r["sharpe_ratio"] is not None:
            assert r["sharpe_ratio"] <= 99

    def test_total_return_compounding(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        # Compounded: (1.10)(0.95) - 1 = 0.045 = 4.5%
        assert r["total_return"] is not None
        assert abs(r["total_return"] - 4.5) < 0.5

    def test_max_drawdown_calculation(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": -15.0, "holding_days": 10},
            {"return_pct": 5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        assert r["max_drawdown"] is not None
        assert r["max_drawdown"] > 0  # max_drawdown is positive (absolute pct from peak)

    def test_profit_factor(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        assert r["profit_factor"] is not None
        assert r["profit_factor"] > 0  # gross_profit=10, gross_loss=5 → PF=2.0
        assert abs(r["profit_factor"] - 2.0) < 0.1

    def test_win_loss_ratio(self):
        trades = [
            {"return_pct": 10.0, "holding_days": 10},
            {"return_pct": -5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        assert r["win_loss_ratio"] is not None
        assert abs(r["win_loss_ratio"] - 2.0) < 0.1

    def test_zero_return_counts_as_loss(self):
        trades = [
            {"return_pct": 0.0, "holding_days": 10},
            {"return_pct": 5.0, "holding_days": 10},
        ]
        r = compute_backtest_metrics(trades)
        assert r["hit_rate"] == 0.5  # 0% is a loss (r <= 0)


# ──────────────────────────────────────────────────────────────────
# Engine-level tests (BacktestEngine helper methods and _simulate)
# ──────────────────────────────────────────────────────────────────

import math
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pandas as pd
import pytest

from app.backtesting.engine import BacktestEngine
from app.config import Settings


def _make_settings(**overrides):
    """Create a Settings instance with test defaults."""
    defaults = {
        "WEIGHT_TECHNICAL": 0.30,
        "WEIGHT_MACRO": 0.18,
        "WEIGHT_FUND_FLOW": 0.22,
        "WEIGHT_FUNDAMENTAL": 0.18,
        "RSI_HARD_LIMIT": 65.0,
        "RSI_BUY_THRESHOLD_KR": 45.0,
        "RSI_BUY_THRESHOLD_US": 50.0,
        "DISPARITY_HARD_LIMIT": 105.0,
        "BACKTEST_TRADE_EXIT_DAYS": 20,
        "BACKTEST_STOP_LOSS_PCT": -7.0,
        "SIGNAL_BUY_THRESHOLD": 15.0,
        "SIGNAL_SELL_THRESHOLD": -15.0,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestBuildPriceDataframes:
    """Tests for BacktestEngine._build_price_dataframes."""

    def test_groups_by_symbol(self):
        engine = BacktestEngine(_make_settings())
        prices = [
            {"symbol": "AAPL", "trade_date": "2025-01-01", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000},
            {"symbol": "AAPL", "trade_date": "2025-01-02", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 1200},
            {"symbol": "MSFT", "trade_date": "2025-01-01", "open": 200, "high": 210, "low": 195, "close": 205, "volume": 800},
        ]
        result = engine._build_price_dataframes(prices)
        assert "AAPL" in result
        assert "MSFT" in result
        assert len(result["AAPL"]) == 2
        assert len(result["MSFT"]) == 1

    def test_sorts_by_trade_date(self):
        engine = BacktestEngine(_make_settings())
        prices = [
            {"symbol": "AAPL", "trade_date": "2025-01-03", "open": 110, "high": 115, "low": 109, "close": 113, "volume": 1000},
            {"symbol": "AAPL", "trade_date": "2025-01-01", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000},
            {"symbol": "AAPL", "trade_date": "2025-01-02", "open": 105, "high": 108, "low": 102, "close": 107, "volume": 1000},
        ]
        result = engine._build_price_dataframes(prices)
        dates = result["AAPL"]["trade_date"].tolist()
        assert dates == ["2025-01-01", "2025-01-02", "2025-01-03"]

    def test_numeric_coercion(self):
        """String prices should be coerced to numeric."""
        engine = BacktestEngine(_make_settings())
        prices = [
            {"symbol": "AAPL", "trade_date": "2025-01-01", "open": "100", "high": "105", "low": "99", "close": "103", "volume": "1000"},
        ]
        result = engine._build_price_dataframes(prices)
        df = result["AAPL"]
        assert df["close"].dtype in (float, int, "float64", "int64")

    def test_invalid_numeric_becomes_nan(self):
        """Non-numeric strings should become NaN after coercion."""
        engine = BacktestEngine(_make_settings())
        prices = [
            {"symbol": "AAPL", "trade_date": "2025-01-01", "open": "N/A", "high": 105, "low": 99, "close": 103, "volume": 1000},
        ]
        result = engine._build_price_dataframes(prices)
        df = result["AAPL"]
        assert pd.isna(df.iloc[0]["open"])

    def test_empty_prices(self):
        engine = BacktestEngine(_make_settings())
        result = engine._build_price_dataframes([])
        assert result == {}

    def test_single_symbol_single_row(self):
        engine = BacktestEngine(_make_settings())
        prices = [
            {"symbol": "TSLA", "trade_date": "2025-06-01", "open": 250, "high": 260, "low": 245, "close": 255, "volume": 5000},
        ]
        result = engine._build_price_dataframes(prices)
        assert len(result) == 1
        assert len(result["TSLA"]) == 1

    def test_resets_index(self):
        """Index should be 0-based after sort and reset."""
        engine = BacktestEngine(_make_settings())
        prices = [
            {"symbol": "X", "trade_date": "2025-01-02", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
            {"symbol": "X", "trade_date": "2025-01-01", "open": 9, "high": 10, "low": 8, "close": 9, "volume": 100},
        ]
        result = engine._build_price_dataframes(prices)
        assert result["X"].index.tolist() == [0, 1]


class TestGetNearestMacro:
    """Tests for BacktestEngine._get_nearest_macro."""

    def test_exact_date_match(self):
        engine = BacktestEngine(_make_settings())
        macro_by_date = {
            "2025-01-01": {"vix": 15},
            "2025-01-05": {"vix": 20},
        }
        result = engine._get_nearest_macro("2025-01-05", macro_by_date)
        assert result == {"vix": 20}

    def test_returns_nearest_before(self):
        engine = BacktestEngine(_make_settings())
        macro_by_date = {
            "2025-01-01": {"vix": 15},
            "2025-01-05": {"vix": 20},
        }
        result = engine._get_nearest_macro("2025-01-03", macro_by_date)
        assert result == {"vix": 15}

    def test_no_data_before_target(self):
        engine = BacktestEngine(_make_settings())
        macro_by_date = {
            "2025-01-10": {"vix": 25},
        }
        result = engine._get_nearest_macro("2025-01-05", macro_by_date)
        assert result is None

    def test_empty_macro_data(self):
        engine = BacktestEngine(_make_settings())
        result = engine._get_nearest_macro("2025-01-01", {})
        assert result is None

    def test_many_dates_picks_closest(self):
        engine = BacktestEngine(_make_settings())
        macro_by_date = {
            "2025-01-01": {"vix": 10},
            "2025-01-03": {"vix": 12},
            "2025-01-05": {"vix": 14},
            "2025-01-07": {"vix": 16},
        }
        result = engine._get_nearest_macro("2025-01-06", macro_by_date)
        assert result == {"vix": 14}


class TestApplyOverrides:
    """Tests for BacktestEngine._apply_overrides."""

    def test_no_overrides_returns_original(self):
        config = _make_settings()
        engine = BacktestEngine(config)
        result = engine._apply_overrides(None)
        assert result is config

    def test_empty_dict_returns_original(self):
        config = _make_settings()
        engine = BacktestEngine(config)
        result = engine._apply_overrides({})
        assert result is config

    def test_override_single_field(self):
        config = _make_settings(BACKTEST_STOP_LOSS_PCT=-7.0)
        engine = BacktestEngine(config)
        result = engine._apply_overrides({"BACKTEST_STOP_LOSS_PCT": -10.0})
        assert result.BACKTEST_STOP_LOSS_PCT == -10.0
        # Original unchanged
        assert config.BACKTEST_STOP_LOSS_PCT == -7.0

    def test_override_multiple_fields(self):
        config = _make_settings()
        engine = BacktestEngine(config)
        result = engine._apply_overrides({
            "RSI_HARD_LIMIT": 70.0,
            "BACKTEST_TRADE_EXIT_DAYS": 30,
        })
        assert result.RSI_HARD_LIMIT == 70.0
        assert result.BACKTEST_TRADE_EXIT_DAYS == 30

    def test_override_preserves_other_fields(self):
        config = _make_settings(WEIGHT_TECHNICAL=0.30, WEIGHT_MACRO=0.18)
        engine = BacktestEngine(config)
        result = engine._apply_overrides({"WEIGHT_TECHNICAL": 0.50})
        assert result.WEIGHT_TECHNICAL == 0.50
        assert result.WEIGHT_MACRO == 0.18  # unchanged


def _generate_price_rows(symbol, start_date, num_days, base_price=100.0, daily_change=0.5):
    """Helper: generate synthetic price history rows."""
    rows = []
    price = base_price
    d = datetime.strptime(start_date, "%Y-%m-%d")
    for i in range(num_days):
        trade_date = (d + timedelta(days=i)).strftime("%Y-%m-%d")
        price = price + daily_change
        rows.append({
            "symbol": symbol,
            "trade_date": trade_date,
            "open": round(price - 0.5, 2),
            "high": round(price + 1.0, 2),
            "low": round(price - 1.0, 2),
            "close": round(price, 2),
            "volume": 10000 + i * 100,
        })
    return rows


class TestSimulate:
    """Tests for BacktestEngine._simulate with mocked indicator/scoring functions."""

    def _run_simulate(self, symbols, market, price_dfs, trading_days,
                      macro_by_date=None, fund_flow_by_symbol=None,
                      config=None, backtest_id="test-bt-001",
                      mock_signal="HOLD", mock_score=0.0,
                      mock_indicators=None):
        """Helper to run _simulate with standard mocks."""
        if config is None:
            config = _make_settings()
        if macro_by_date is None:
            macro_by_date = {}
        if fund_flow_by_symbol is None:
            fund_flow_by_symbol = {}
        if mock_indicators is None:
            mock_indicators = {"rsi_14": 40.0, "disparity_20": 100.0}

        engine = BacktestEngine(config)

        from app.models.enums import SignalType
        signal_enum = SignalType(mock_signal)

        with patch("app.backtesting.engine.compute_all_indicators", return_value=mock_indicators), \
             patch("app.backtesting.engine.compute_technical_score", return_value=50.0), \
             patch("app.backtesting.engine.compute_macro_score", return_value={"aggregate_score": 0.5}), \
             patch("app.backtesting.engine.compute_fund_flow_score", return_value=30.0), \
             patch("app.backtesting.engine.compute_aggregate_signal", return_value=(signal_enum, mock_score)):
            return engine._simulate(
                symbols=symbols,
                market=market,
                price_dfs=price_dfs,
                macro_by_date=macro_by_date,
                fund_flow_by_symbol=fund_flow_by_symbol,
                trading_days=trading_days,
                config=config,
                backtest_id=backtest_id,
            )

    def test_no_symbols_returns_empty(self):
        trades = self._run_simulate(
            symbols=[], market="US", price_dfs={},
            trading_days=["2025-01-01"],
        )
        assert trades == []

    def test_no_trading_days_returns_empty(self):
        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": pd.DataFrame()},
            trading_days=[],
        )
        assert trades == []

    def test_symbol_not_in_price_dfs_skipped(self):
        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={},  # AAPL not present
            trading_days=["2025-01-01"],
        )
        assert trades == []

    def test_empty_dataframe_skipped(self):
        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": pd.DataFrame()},
            trading_days=["2025-01-01"],
        )
        assert trades == []

    def test_insufficient_data_skipped(self):
        """Fewer than 30 rows in lookback window -> skip."""
        rows = _generate_price_rows("AAPL", "2025-01-01", 20, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=["2025-01-20"],
        )
        assert trades == []

    def test_buy_signal_opens_position(self):
        """BUY signal with sufficient data should open a position."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
        )
        # Position opened on last_date, then closed at backtest_end
        assert len(trades) == 1
        assert trades[0]["entry_signal"] == "BUY"
        assert trades[0]["exit_reason"] == "backtest_end"
        assert trades[0]["symbol"] == "AAPL"

    def test_hold_signal_no_position(self):
        """HOLD signal should not open any position."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="HOLD", mock_score=0.0,
        )
        assert trades == []

    def test_stop_loss_triggers(self):
        """Position should be closed when return drops below stop loss."""
        # Create price data that goes up then drops significantly
        rows = _generate_price_rows("AAPL", "2024-06-01", 200, base_price=100, daily_change=0.5)
        # Add a sharp drop at the end
        last_d = datetime.strptime("2025-02-15", "%Y-%m-%d")
        entry_price = rows[-1]["close"]
        drop_price = round(entry_price * 0.90, 2)  # -10% drop (below -7% stop loss)
        rows.append({
            "symbol": "AAPL", "trade_date": (last_d + timedelta(days=1)).strftime("%Y-%m-%d"),
            "open": entry_price, "high": entry_price,
            "low": drop_price, "close": drop_price, "volume": 20000,
        })

        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]

        entry_date = rows[-2]["trade_date"]
        exit_date = rows[-1]["trade_date"]

        from app.models.enums import SignalType
        call_count = [0]

        def mock_aggregate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return SignalType.BUY, 20.0
            return SignalType.HOLD, 0.0

        with patch("app.backtesting.engine.compute_all_indicators", return_value={"rsi_14": 40.0, "disparity_20": 100.0}), \
             patch("app.backtesting.engine.compute_technical_score", return_value=50.0), \
             patch("app.backtesting.engine.compute_macro_score", return_value={"aggregate_score": 0.5}), \
             patch("app.backtesting.engine.compute_aggregate_signal", side_effect=mock_aggregate):
            trades = engine._simulate(
                symbols=["AAPL"], market="US",
                price_dfs={"AAPL": df},
                macro_by_date={},
                fund_flow_by_symbol={},
                trading_days=[entry_date, exit_date],
                config=_make_settings(),
                backtest_id="test-sl",
            )

        assert len(trades) == 1
        assert trades[0]["exit_reason"] == "stop_loss"
        assert trades[0]["return_pct"] < -7.0

    def test_time_exit_triggers(self):
        """Position should close after BACKTEST_TRADE_EXIT_DAYS."""
        config = _make_settings(BACKTEST_TRADE_EXIT_DAYS=5)
        # Create enough data for lookback + a few trading days
        rows = _generate_price_rows("AAPL", "2024-06-01", 240, base_price=100, daily_change=0.1)
        engine = BacktestEngine(config)
        df = engine._build_price_dataframes(rows)["AAPL"]

        # Use dates that span > 5 days apart
        trading_days_all = df[df["trade_date"] >= "2025-01-01"]["trade_date"].tolist()[:10]
        if len(trading_days_all) < 7:
            pytest.skip("Not enough trading days generated")

        entry_day = trading_days_all[0]
        # Find a day that is >= 5 days after entry
        exit_candidates = [d for d in trading_days_all
                          if (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(entry_day, "%Y-%m-%d")).days >= 5]
        if not exit_candidates:
            pytest.skip("Not enough gap in trading days")

        from app.models.enums import SignalType
        first_call = [True]

        def mock_aggregate(*args, **kwargs):
            if first_call[0]:
                first_call[0] = False
                return SignalType.BUY, 20.0
            return SignalType.HOLD, 0.0

        with patch("app.backtesting.engine.compute_all_indicators", return_value={"rsi_14": 40.0, "disparity_20": 100.0}), \
             patch("app.backtesting.engine.compute_technical_score", return_value=50.0), \
             patch("app.backtesting.engine.compute_macro_score", return_value={"aggregate_score": 0.5}), \
             patch("app.backtesting.engine.compute_aggregate_signal", side_effect=mock_aggregate):
            trades = engine._simulate(
                symbols=["AAPL"], market="US",
                price_dfs={"AAPL": df},
                macro_by_date={},
                fund_flow_by_symbol={},
                trading_days=trading_days_all,
                config=config,
                backtest_id="test-time",
            )

        time_exits = [t for t in trades if t.get("exit_reason") == "time_exit"]
        assert len(time_exits) >= 1

    def test_sell_signal_closes_position(self):
        """SELL signal should close an open position."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 240, base_price=100, daily_change=0.1)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]

        trading_days_all = df[df["trade_date"] >= "2025-01-01"]["trade_date"].tolist()[:3]
        if len(trading_days_all) < 2:
            pytest.skip("Not enough trading days")

        from app.models.enums import SignalType
        call_count = [0]

        def mock_aggregate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return SignalType.BUY, 20.0
            return SignalType.SELL, -20.0

        with patch("app.backtesting.engine.compute_all_indicators", return_value={"rsi_14": 40.0, "disparity_20": 100.0}), \
             patch("app.backtesting.engine.compute_technical_score", return_value=50.0), \
             patch("app.backtesting.engine.compute_macro_score", return_value={"aggregate_score": 0.5}), \
             patch("app.backtesting.engine.compute_aggregate_signal", side_effect=mock_aggregate):
            trades = engine._simulate(
                symbols=["AAPL"], market="US",
                price_dfs={"AAPL": df},
                macro_by_date={},
                fund_flow_by_symbol={},
                trading_days=trading_days_all,
                config=_make_settings(),
                backtest_id="test-sell",
            )

        assert len(trades) == 1
        assert trades[0]["exit_reason"] == "signal_change"

    def test_hard_limit_rsi_blocks_buy(self):
        """BUY signal should be overridden to HOLD when RSI > RSI_HARD_LIMIT."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        # RSI=70 > RSI_HARD_LIMIT=65 => BUY overridden to HOLD
        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
            mock_indicators={"rsi_14": 70.0, "disparity_20": 100.0},
        )
        assert trades == []  # BUY was blocked, no position opened

    def test_hard_limit_disparity_blocks_buy(self):
        """BUY signal blocked when disparity > DISPARITY_HARD_LIMIT."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
            mock_indicators={"rsi_14": 40.0, "disparity_20": 110.0},
        )
        assert trades == []

    def test_hard_limit_kr_rsi_threshold(self):
        """KR market: BUY blocked when RSI > RSI_BUY_THRESHOLD_KR (45)."""
        rows = _generate_price_rows("005930", "2024-06-01", 250, base_price=50000)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["005930"]
        last_date = df.iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["005930"], market="KR",
            price_dfs={"005930": df},
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
            mock_indicators={"rsi_14": 50.0, "disparity_20": 100.0},  # 50 > 45
        )
        assert trades == []

    def test_hard_limit_does_not_block_sell(self):
        """Hard limit only blocks BUY, not SELL."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        # SELL should not be blocked even with high RSI
        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="SELL", mock_score=-20.0,
            mock_indicators={"rsi_14": 80.0, "disparity_20": 110.0},
        )
        # No open position to sell, so no trades
        assert trades == []

    def test_multiple_symbols_independent(self):
        """Each symbol should maintain independent position state."""
        rows_a = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        rows_b = _generate_price_rows("MSFT", "2024-06-01", 250, base_price=200)
        engine = BacktestEngine(_make_settings())
        dfs = engine._build_price_dataframes(rows_a + rows_b)
        last_date = dfs["AAPL"].iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["AAPL", "MSFT"], market="US",
            price_dfs=dfs,
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
        )
        # Both symbols get BUY, both open then close at backtest_end
        symbols_traded = {t["symbol"] for t in trades}
        assert "AAPL" in symbols_traded
        assert "MSFT" in symbols_traded
        assert len(trades) == 2

    def test_open_positions_closed_at_backtest_end(self):
        """Positions still open at end of simulation should be closed with 'backtest_end'."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
        )
        assert all(t["exit_reason"] == "backtest_end" for t in trades)

    def test_null_indicators_skipped(self):
        """If compute_all_indicators returns empty dict, symbol is skipped."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
            mock_indicators={},  # Empty => skip
        )
        assert trades == []

    def test_trade_contains_expected_fields(self):
        """Verify that closed trades have all required fields."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
        )
        assert len(trades) == 1
        trade = trades[0]
        expected_fields = {
            "backtest_id", "symbol", "market", "entry_date",
            "entry_price", "entry_signal", "entry_score",
            "exit_date", "exit_price", "exit_reason", "return_pct", "holding_days",
        }
        assert expected_fields.issubset(set(trade.keys()))

    def test_return_pct_calculation(self):
        """Verify return_pct = (exit_price - entry_price) / entry_price * 100."""
        rows = _generate_price_rows("AAPL", "2024-06-01", 250, base_price=100, daily_change=0.5)
        engine = BacktestEngine(_make_settings())
        df = engine._build_price_dataframes(rows)["AAPL"]
        last_date = df.iloc[-1]["trade_date"]

        trades = self._run_simulate(
            symbols=["AAPL"], market="US",
            price_dfs={"AAPL": df},
            trading_days=[last_date],
            mock_signal="BUY", mock_score=20.0,
        )
        assert len(trades) == 1
        trade = trades[0]
        expected_return = (trade["exit_price"] - trade["entry_price"]) / trade["entry_price"] * 100
        assert trade["return_pct"] == pytest.approx(round(expected_return, 4), abs=0.01)


class TestRunAsync:
    """Tests for BacktestEngine.run() (async entry point)."""

    @pytest.mark.asyncio
    async def test_no_active_symbols_returns_error(self):
        config = _make_settings()
        engine = BacktestEngine(config)

        with patch("app.backtesting.engine.repo") as mock_repo:
            mock_repo.insert_backtest_run = AsyncMock()
            mock_repo.get_active_symbols = AsyncMock(return_value=[])
            mock_repo.update_backtest_run = AsyncMock()

            result = await engine.run("US", "2025-01-01", "2025-06-01")

        assert "error" in result
        assert "No active symbols" in result["error"]
        mock_repo.update_backtest_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_price_data_returns_error(self):
        config = _make_settings()
        engine = BacktestEngine(config)

        with patch("app.backtesting.engine.repo") as mock_repo:
            mock_repo.insert_backtest_run = AsyncMock()
            mock_repo.get_active_symbols = AsyncMock(return_value=["AAPL"])
            mock_repo.get_all_price_range = AsyncMock(return_value=[])
            mock_repo.update_backtest_run = AsyncMock()

            result = await engine.run("US", "2025-01-01", "2025-06-01")

        assert "error" in result
        assert "No price data" in result["error"]

    @pytest.mark.asyncio
    async def test_exception_returns_error_and_marks_failed(self):
        config = _make_settings()
        engine = BacktestEngine(config)

        with patch("app.backtesting.engine.repo") as mock_repo:
            mock_repo.insert_backtest_run = AsyncMock()
            mock_repo.get_active_symbols = AsyncMock(side_effect=RuntimeError("db error"))
            mock_repo.update_backtest_run = AsyncMock()

            result = await engine.run("US", "2025-01-01", "2025-06-01")

        assert "error" in result
        mock_repo.update_backtest_run.assert_called_once()
        # Should be marked as "failed"
        call_args = mock_repo.update_backtest_run.call_args
        assert call_args[0][1] == "failed"
