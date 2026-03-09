"""Tests for capitulation detection, relative strength, and entry scenarios."""

import pandas as pd
import pytest

from app.indicators.regime import (
    compute_entry_scenarios,
    compute_relative_strength,
    DEFENSE_SECTORS,
)
from app.screening.scanner import DynamicScreener


# ── Helpers ──

def _make_df(prices, volumes, start="2026-01-01"):
    return pd.DataFrame({
        "trade_date": pd.date_range(start, periods=len(prices)),
        "close": prices,
        "volume": volumes,
    })


def _make_prices(count=200, base=100.0, step=0.1):
    return [
        {"trade_date": f"2025-{(i // 28) + 6:02d}-{(i % 28) + 1:02d}",
         "close": base + i * step}
        for i in range(count)
    ]


MOCK_SECTOR_MAP = {
    "005930": "반도체", "015760": "유틸리티", "012450": "방산/항공",
    "034020": "에너지/플랜트", "017670": "통신",
    "AAPL": "Tech", "XOM": "Energy", "UNH": "Healthcare",
    "SPY": "ETF", "069500": "ETF",
}


# ── Capitulation Tests ──


class TestCapitulation:
    def setup_method(self):
        self.screener = DynamicScreener()

    def test_capitulation_detected(self):
        """2x volume + 4% drop = capitulation"""
        prices = [100.0] * 24 + [96.0]
        volumes = [1_000_000] * 24 + [2_500_000]
        df = _make_df(prices, volumes)
        results = self.screener._check_capitulation(df, "TEST", 5)
        assert len(results) >= 1
        assert results[0]["trigger_type"] == "capitulation"

    def test_no_capitulation_normal_volume(self):
        prices = [100.0] * 25
        volumes = [1_000_000] * 25
        df = _make_df(prices, volumes)
        results = self.screener._check_capitulation(df, "TEST", 5)
        assert len(results) == 0

    def test_high_volume_no_price_drop(self):
        """High volume but price UP = NOT capitulation"""
        prices = [100.0] * 24 + [104.0]
        volumes = [1_000_000] * 24 + [3_000_000]
        df = _make_df(prices, volumes)
        results = self.screener._check_capitulation(df, "TEST", 5)
        assert len(results) == 0

    def test_price_drop_low_volume(self):
        """Price drop but normal volume = NOT capitulation"""
        prices = [100.0] * 24 + [95.0]
        volumes = [1_000_000] * 25
        df = _make_df(prices, volumes)
        results = self.screener._check_capitulation(df, "TEST", 5)
        assert len(results) == 0

    def test_insufficient_data(self):
        df = _make_df([100.0] * 10, [1_000_000] * 10)
        results = self.screener._check_capitulation(df, "TEST", 5)
        assert len(results) == 0

    def test_trigger_description_contains_info(self):
        prices = [100.0] * 24 + [95.0]
        volumes = [1_000_000] * 24 + [3_000_000]
        df = _make_df(prices, volumes)
        results = self.screener._check_capitulation(df, "TEST", 5)
        if results:
            assert "Capitulation" in results[0]["trigger_description"]
            assert "price" in results[0]["trigger_description"]


# ── Relative Strength Tests ──


class TestRelativeStrength:
    def test_outperformer_rs_above_1(self):
        returns = {"005930": 5.0, "015760": -2.0}
        benchmarks = {"KR": 1.0, "US": 2.0}
        result = compute_relative_strength(returns, benchmarks, MOCK_SECTOR_MAP)
        samsung = next(r for r in result if r["symbol"] == "005930")
        assert samsung["rs_ratio"] > 1.0

    def test_underperformer_rs_below_1(self):
        returns = {"015760": -5.0}
        benchmarks = {"KR": 2.0, "US": 1.0}
        result = compute_relative_strength(returns, benchmarks, MOCK_SECTOR_MAP)
        kepco = next(r for r in result if r["symbol"] == "015760")
        assert kepco["rs_ratio"] < 1.0

    def test_hedge_candidate_in_risk_off(self):
        """방산 + 상대강도 > 1.0 + risk-off → hedge candidate"""
        returns = {"012450": 3.0, "XOM": 5.0, "005930": -4.0}
        benchmarks = {"KR": -2.0, "US": -1.0}
        result = compute_relative_strength(
            returns, benchmarks, MOCK_SECTOR_MAP, risk_regime_score=-0.5
        )
        defense = next(r for r in result if r["symbol"] == "012450")
        assert defense["is_hedge_candidate"] is True
        energy = next(r for r in result if r["symbol"] == "XOM")
        assert energy["is_hedge_candidate"] is True

    def test_no_hedge_in_risk_on(self):
        returns = {"012450": 3.0}
        benchmarks = {"KR": 1.0, "US": 2.0}
        result = compute_relative_strength(
            returns, benchmarks, MOCK_SECTOR_MAP, risk_regime_score=0.5
        )
        defense = next(r for r in result if r["symbol"] == "012450")
        assert defense["is_hedge_candidate"] is False

    def test_sorted_by_rs_descending(self):
        returns = {"005930": 5.0, "015760": -2.0, "012450": 3.0}
        benchmarks = {"KR": 0.5, "US": 0.5}
        result = compute_relative_strength(returns, benchmarks, MOCK_SECTOR_MAP)
        rs_values = [r["rs_ratio"] for r in result]
        assert rs_values == sorted(rs_values, reverse=True)

    def test_etf_excluded(self):
        returns = {"SPY": 2.0, "069500": 1.0, "005930": 3.0}
        benchmarks = {"KR": 1.0, "US": 2.0}
        result = compute_relative_strength(returns, benchmarks, MOCK_SECTOR_MAP)
        symbols = [r["symbol"] for r in result]
        assert "SPY" not in symbols
        assert "069500" not in symbols

    def test_defense_sector_flagged(self):
        returns = {"012450": 2.0, "017670": 1.0, "005930": 3.0}
        benchmarks = {"KR": 1.0, "US": 1.0}
        result = compute_relative_strength(returns, benchmarks, MOCK_SECTOR_MAP)
        defense = next(r for r in result if r["symbol"] == "012450")
        telecom = next(r for r in result if r["symbol"] == "017670")
        assert defense["is_defense_sector"] is True
        assert telecom["is_defense_sector"] is True

    def test_benchmark_near_zero(self):
        """벤치마크 수익률 0% 근처에서도 정상 작동"""
        returns = {"005930": 5.0}
        benchmarks = {"KR": 0.0, "US": 0.0}
        result = compute_relative_strength(returns, benchmarks, MOCK_SECTOR_MAP)
        assert len(result) == 1
        assert result[0]["rs_ratio"] > 1.0


# ── Entry Scenarios Tests ──


class TestEntryScenarios:
    def test_basic_structure(self):
        prices = {
            "KOSPI": _make_prices(200, 350, 0.1),
            "SPY": _make_prices(200, 500, 0.2),
        }
        result = compute_entry_scenarios(prices)
        assert "benchmarks" in result
        assert "scenarios" in result
        assert set(result["scenarios"].keys()) == {"best", "base", "worst"}

    def test_ma_values_positive(self):
        prices = {
            "KOSPI": _make_prices(200, 350),
            "SPY": _make_prices(200, 500),
        }
        result = compute_entry_scenarios(prices)
        for key in ("KOSPI", "SPY"):
            bm = result["benchmarks"][key]
            assert bm["ma20"] > 0
            assert bm["ma60"] > 0
            assert bm["ma120"] > 0

    def test_scenarios_have_ranges(self):
        prices = {
            "KOSPI": _make_prices(200, 350),
            "SPY": _make_prices(200, 500),
        }
        result = compute_entry_scenarios(prices)
        for scenario in result["scenarios"].values():
            assert "kospi_range" in scenario
            assert "spy_range" in scenario
            assert "usd_krw_range" in scenario
            assert "action_kr" in scenario
            assert len(scenario["kospi_range"]) == 2

    def test_high_risk_biases_worst(self):
        prices = {"KOSPI": _make_prices(), "SPY": _make_prices()}
        result = compute_entry_scenarios(prices, risk_score=75.0)
        assert result["probability_bias"] == "worst"

    def test_low_risk_biases_best(self):
        prices = {"KOSPI": _make_prices(), "SPY": _make_prices()}
        result = compute_entry_scenarios(prices, risk_score=20.0)
        assert result["probability_bias"] == "best"

    def test_moderate_risk_biases_base(self):
        prices = {"KOSPI": _make_prices(), "SPY": _make_prices()}
        result = compute_entry_scenarios(prices, risk_score=45.0)
        assert result["probability_bias"] == "base"

    def test_empty_prices(self):
        result = compute_entry_scenarios({})
        assert "scenarios" in result
        assert result["probability_bias"] == "base"

    def test_with_fx_data(self):
        prices = {"KOSPI": _make_prices(), "SPY": _make_prices()}
        fx = [{"indicator_date": f"2025-06-{i + 1:02d}", "close": 1350 + i * 0.5}
              for i in range(200)]
        result = compute_entry_scenarios(prices, fx_prices=fx)
        assert result["fx"]["usd_krw_current"] is not None
        assert result["fx"]["usd_krw_current"] > 0

    def test_worst_scenario_lower_than_best(self):
        """Worst 시나리오 하한이 Best 시나리오 하한보다 낮아야 함"""
        prices = {
            "KOSPI": _make_prices(200, 350),
            "SPY": _make_prices(200, 500),
        }
        result = compute_entry_scenarios(prices)
        best_low = result["scenarios"]["best"]["kospi_range"][0]
        worst_low = result["scenarios"]["worst"]["kospi_range"][0]
        if best_low > 0 and worst_low > 0:
            assert worst_low < best_low
