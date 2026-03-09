"""Backtesting Engine - Replays scoring logic on historical price data."""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pandas as pd

from app.backtesting.metrics import compute_backtest_metrics
from app.config import Settings
from app.database import repositories as repo
from app.indicators.macro import compute_macro_score
from app.indicators.scoring import (
    compute_aggregate_signal,
    compute_fund_flow_score,
    compute_technical_score,
)
from app.indicators.technical import compute_all_indicators

logger = logging.getLogger("vibe.backtest")


class BacktestEngine:
    """Replays scoring logic on historical price data to validate parameters."""

    def __init__(self, config: Settings):
        self.config = config

    async def run(
        self,
        market: str,
        start_date: str,
        end_date: str,
        config_overrides: dict | None = None,
    ) -> dict[str, Any]:
        """Run backtest for a market over a date range.

        Returns dict with backtest_id, metrics, trades.
        """
        backtest_id = str(uuid4())

        # Apply config overrides (for parameter optimization)
        effective_config = self._apply_overrides(config_overrides)

        # Save run to DB
        config_snapshot = {
            "WEIGHT_TECHNICAL": effective_config.WEIGHT_TECHNICAL,
            "WEIGHT_MACRO": effective_config.WEIGHT_MACRO,
            "WEIGHT_FUND_FLOW": effective_config.WEIGHT_FUND_FLOW,
            "WEIGHT_FUNDAMENTAL": effective_config.WEIGHT_FUNDAMENTAL,
            "RSI_HARD_LIMIT": effective_config.RSI_HARD_LIMIT,
            "RSI_BUY_THRESHOLD_KR": effective_config.RSI_BUY_THRESHOLD_KR,
            "RSI_BUY_THRESHOLD_US": effective_config.RSI_BUY_THRESHOLD_US,
            "DISPARITY_HARD_LIMIT": effective_config.DISPARITY_HARD_LIMIT,
            "BACKTEST_TRADE_EXIT_DAYS": effective_config.BACKTEST_TRADE_EXIT_DAYS,
            "BACKTEST_STOP_LOSS_PCT": effective_config.BACKTEST_STOP_LOSS_PCT,
        }
        await repo.insert_backtest_run(backtest_id, market, start_date, end_date, config_snapshot)

        try:
            # Load data
            symbols = await repo.get_active_symbols(market)
            if not symbols:
                await repo.update_backtest_run(backtest_id, "failed")
                return {"backtest_id": backtest_id, "error": "No active symbols"}

            # Need 200 days before start_date for indicator calculation lookback
            lookback_date = (
                datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=300)
            ).strftime("%Y-%m-%d")

            logger.info(
                "Backtest starting: id=%s market=%s range=[%s, %s] symbols=%d",
                backtest_id[:8], market, start_date, end_date, len(symbols),
            )

            # Load all price data in bulk
            all_prices = await repo.get_all_price_range(market, lookback_date, end_date)
            if not all_prices:
                await repo.update_backtest_run(backtest_id, "failed")
                return {"backtest_id": backtest_id, "error": "No price data available"}

            # Group by symbol → DataFrame
            price_dfs = self._build_price_dataframes(all_prices)

            # Load macro data
            macro_rows = await repo.get_macro_range(start_date, end_date)
            macro_by_date = {r["indicator_date"]: r for r in macro_rows}

            # Load fund flow (KR only)
            fund_flow_by_symbol: dict[str, dict[str, dict]] = {}
            if market == "KR":
                for symbol in symbols:
                    ff_rows = await repo.get_fund_flow_range(symbol, start_date, end_date)
                    fund_flow_by_symbol[symbol] = {r["trade_date"]: r for r in ff_rows}

            # Get trading days (dates that appear in price data within test range)
            trading_days = sorted(set(
                r["trade_date"] for r in all_prices
                if start_date <= r["trade_date"] <= end_date
            ))

            logger.info("Backtest has %d trading days to process", len(trading_days))

            # Run simulation
            all_trades = self._simulate(
                symbols=symbols,
                market=market,
                price_dfs=price_dfs,
                macro_by_date=macro_by_date,
                fund_flow_by_symbol=fund_flow_by_symbol,
                trading_days=trading_days,
                config=effective_config,
                backtest_id=backtest_id,
            )

            # Compute metrics
            closed_trades = [t for t in all_trades if t.get("exit_date")]
            metrics = compute_backtest_metrics(closed_trades)

            # Store trades
            if all_trades:
                await repo.insert_backtest_trades(all_trades)

            # Update run with results
            await repo.update_backtest_run(backtest_id, "completed", metrics)

            logger.info(
                "Backtest completed: id=%s trades=%d hit_rate=%.2f%% sharpe=%.2f",
                backtest_id[:8],
                metrics.get("total_trades", 0),
                (metrics.get("hit_rate") if metrics.get("hit_rate") is not None else 0) * 100,
                metrics.get("sharpe_ratio") if metrics.get("sharpe_ratio") is not None else 0,
            )

            return {
                "backtest_id": backtest_id,
                "market": market,
                "start_date": start_date,
                "end_date": end_date,
                "metrics": metrics,
                "trades_count": len(all_trades),
                "closed_trades": len(closed_trades),
            }

        except Exception as e:
            logger.exception("Backtest failed: %s", e)
            await repo.update_backtest_run(backtest_id, "failed")
            return {"backtest_id": backtest_id, "error": "Backtest execution failed. Check server logs."}

    def _simulate(
        self,
        symbols: list[str],
        market: str,
        price_dfs: dict[str, pd.DataFrame],
        macro_by_date: dict[str, dict],
        fund_flow_by_symbol: dict[str, dict[str, dict]],
        trading_days: list[str],
        config: Settings,
        backtest_id: str,
    ) -> list[dict]:
        """Core simulation loop. Returns list of trade dicts."""
        # Track open positions: {symbol: trade_dict}
        open_positions: dict[str, dict] = {}
        all_trades: list[dict] = []

        for day_str in trading_days:
            # Get latest macro for this day
            macro_data = macro_by_date.get(day_str) or self._get_nearest_macro(
                day_str, macro_by_date
            )
            macro_score_result = compute_macro_score(macro_data) if macro_data else {}
            macro_score = macro_score_result.get("aggregate_score", 0) * 100

            for symbol in symbols:
                df = price_dfs.get(symbol)
                if df is None or df.empty:
                    continue

                # Build lookback window up to current day
                window = df[df["trade_date"] <= day_str].tail(200)
                if len(window) < 30:
                    continue  # Not enough data

                current_price = window.iloc[-1]["close"]

                # Skip if price is invalid (NaN from coercion or zero)
                if pd.isna(current_price) or current_price <= 0:
                    continue

                # Compute technical indicators
                indicators = compute_all_indicators(window)
                if not indicators:
                    continue
                indicators["close"] = current_price

                # Compute scores
                tech_score = compute_technical_score(indicators)

                fund_flow_score = None
                if market == "KR" and symbol in fund_flow_by_symbol:
                    ff_data = fund_flow_by_symbol[symbol].get(day_str)
                    if ff_data:
                        fund_flow_score = compute_fund_flow_score(ff_data)

                signal, raw_score = compute_aggregate_signal(
                    tech_score, macro_score, fund_flow_score, market, config,
                )

                # Apply Hard Limit checks
                rsi = indicators.get("rsi_14")
                disparity = indicators.get("disparity_20")
                hard_limit = False

                if rsi is not None and rsi > config.RSI_HARD_LIMIT:
                    hard_limit = True
                if market == "KR" and rsi is not None and rsi > config.RSI_BUY_THRESHOLD_KR:
                    hard_limit = True
                if market == "US" and rsi is not None and rsi > config.RSI_BUY_THRESHOLD_US:
                    hard_limit = True
                if disparity is not None and disparity > config.DISPARITY_HARD_LIMIT:
                    hard_limit = True

                if hard_limit and signal.value == "BUY":
                    signal_str = "HOLD"
                else:
                    signal_str = signal.value

                # ── Trade logic ──

                # Check open position for stop loss / time exit
                if symbol in open_positions:
                    pos = open_positions[symbol]
                    entry_price = pos["entry_price"]
                    if entry_price is None or entry_price <= 0:
                        continue  # Skip invalid entry price
                    current_return = (current_price - entry_price) / entry_price * 100
                    holding_days = (
                        datetime.strptime(day_str, "%Y-%m-%d")
                        - datetime.strptime(pos["entry_date"], "%Y-%m-%d")
                    ).days

                    close_reason = None
                    if current_return <= config.BACKTEST_STOP_LOSS_PCT:
                        close_reason = "stop_loss"
                    elif holding_days >= config.BACKTEST_TRADE_EXIT_DAYS:
                        close_reason = "time_exit"
                    elif signal_str == "SELL":
                        close_reason = "signal_change"

                    if close_reason:
                        pos["exit_date"] = day_str
                        pos["exit_price"] = current_price
                        pos["exit_reason"] = close_reason
                        pos["return_pct"] = round(current_return, 4)
                        pos["holding_days"] = holding_days
                        all_trades.append(pos)
                        del open_positions[symbol]

                # Open new position on BUY (if no existing position)
                elif signal_str == "BUY" and symbol not in open_positions:
                    open_positions[symbol] = {
                        "backtest_id": backtest_id,
                        "symbol": symbol,
                        "market": market,
                        "entry_date": day_str,
                        "entry_price": current_price,
                        "entry_signal": "BUY",
                        "entry_score": raw_score,
                    }

        # Close remaining open positions at last available price
        for symbol, pos in open_positions.items():
            df = price_dfs.get(symbol)
            if df is not None and not df.empty:
                last_row = df.iloc[-1]
                last_price = last_row["close"]
                last_date = last_row["trade_date"]
                entry_price = pos["entry_price"]
                if entry_price is None or entry_price <= 0 or pd.isna(last_price) or last_price <= 0:
                    continue  # Skip positions with invalid prices
                current_return = (last_price - entry_price) / entry_price * 100
                holding_days = (
                    datetime.strptime(last_date, "%Y-%m-%d")
                    - datetime.strptime(pos["entry_date"], "%Y-%m-%d")
                ).days
                pos["exit_date"] = last_date
                pos["exit_price"] = last_price
                pos["exit_reason"] = "backtest_end"
                pos["return_pct"] = round(current_return, 4)
                pos["holding_days"] = holding_days
                all_trades.append(pos)

        return all_trades

    def _build_price_dataframes(self, all_prices: list[dict]) -> dict[str, pd.DataFrame]:
        """Group price rows by symbol into DataFrames."""
        from collections import defaultdict

        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in all_prices:
            grouped[row["symbol"]].append(row)

        result = {}
        for symbol, rows in grouped.items():
            df = pd.DataFrame(rows)
            df = df.sort_values("trade_date").reset_index(drop=True)
            # Ensure numeric columns
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            result[symbol] = df

        return result

    def _get_nearest_macro(self, target_date: str, macro_by_date: dict) -> dict | None:
        """Find the nearest macro data on or before target_date."""
        candidates = [d for d in macro_by_date.keys() if d <= target_date]
        if candidates:
            nearest = max(candidates)
            return macro_by_date[nearest]
        return None

    def _apply_overrides(self, overrides: dict | None) -> Settings:
        """Create an effective config with overrides applied."""
        if not overrides:
            return self.config

        # Create a copy with overrides
        config_dict = {}
        for field in self.config.__class__.model_fields:
            config_dict[field] = getattr(self.config, field)
        config_dict.update(overrides)

        return Settings(**config_dict)
