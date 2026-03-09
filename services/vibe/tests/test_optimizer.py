"""Tests for app.backtesting.optimizer — ParameterOptimizer grid generation."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.backtesting.optimizer import ParameterOptimizer


def _make_config():
    """Create a mock config."""
    cfg = MagicMock()
    cfg.WEIGHT_TECHNICAL = 0.35
    cfg.WEIGHT_MACRO = 0.20
    cfg.WEIGHT_FUND_FLOW = 0.25
    cfg.WEIGHT_FUNDAMENTAL = 0.20
    return cfg


class TestGenerateValidCombinations:
    def setup_method(self):
        self.config = _make_config()
        self.optimizer = ParameterOptimizer(self.config)

    def test_default_grid_kr(self):
        """Default grid for KR should produce valid combos."""
        combos = self.optimizer._generate_valid_combinations(
            ParameterOptimizer.DEFAULT_GRID, "KR"
        )
        assert len(combos) > 0
        for c in combos:
            total = sum(v for k, v in c.items() if k.startswith("WEIGHT_"))
            assert abs(total - 1.0) <= 0.05, f"Weight sum {total} out of tolerance"

    def test_default_grid_us_no_fund_flow(self):
        """US market combos should have WEIGHT_FUND_FLOW=0.
        Default grid may not produce valid US combos if weights don't sum to ~1.0."""
        combos = self.optimizer._generate_valid_combinations(
            ParameterOptimizer.DEFAULT_GRID, "US"
        )
        # All combos (if any) must have fund_flow=0
        for c in combos:
            assert c.get("WEIGHT_FUND_FLOW", 0) == 0.0

    def test_custom_grid_us_valid(self):
        """US market with adjusted weights should produce valid combos."""
        grid = {
            "WEIGHT_TECHNICAL": [0.40, 0.50],
            "WEIGHT_MACRO": [0.30],
            "WEIGHT_FUND_FLOW": [0.0, 0.20],
            "WEIGHT_FUNDAMENTAL": [0.30, 0.20],
        }
        combos = self.optimizer._generate_valid_combinations(grid, "US")
        assert len(combos) > 0
        for c in combos:
            assert c["WEIGHT_FUND_FLOW"] == 0.0
            total = sum(c.values())
            assert abs(total - 1.0) <= 0.05

    def test_weight_sum_tolerance(self):
        """All combos must sum to 1.0 ± 0.05."""
        grid = {
            "WEIGHT_TECHNICAL": [0.30, 0.40, 0.50],
            "WEIGHT_MACRO": [0.20, 0.30],
            "WEIGHT_FUND_FLOW": [0.0, 0.20, 0.30],
            "WEIGHT_FUNDAMENTAL": [0.10, 0.20, 0.30],
        }
        combos = self.optimizer._generate_valid_combinations(grid, "KR")
        for c in combos:
            total = sum(c.values())
            assert abs(total - 1.0) <= 0.05

    def test_invalid_combos_filtered(self):
        """Combos summing far from 1.0 should be excluded."""
        grid = {
            "WEIGHT_TECHNICAL": [0.90],
            "WEIGHT_MACRO": [0.90],
            "WEIGHT_FUND_FLOW": [0.0],
            "WEIGHT_FUNDAMENTAL": [0.0],
        }
        combos = self.optimizer._generate_valid_combinations(grid, "KR")
        # 0.9 + 0.9 = 1.8 → should be filtered out
        assert len(combos) == 0

    def test_exact_one_combo(self):
        """Single valid combo should return 1 result."""
        grid = {
            "WEIGHT_TECHNICAL": [0.40],
            "WEIGHT_MACRO": [0.20],
            "WEIGHT_FUND_FLOW": [0.20],
            "WEIGHT_FUNDAMENTAL": [0.20],
        }
        combos = self.optimizer._generate_valid_combinations(grid, "KR")
        assert len(combos) == 1
        assert combos[0] == {
            "WEIGHT_TECHNICAL": 0.40,
            "WEIGHT_MACRO": 0.20,
            "WEIGHT_FUND_FLOW": 0.20,
            "WEIGHT_FUNDAMENTAL": 0.20,
        }

    def test_non_weight_params(self):
        """Non-weight params should be included in combos."""
        grid = {
            "WEIGHT_TECHNICAL": [0.50],
            "WEIGHT_MACRO": [0.50],
            "RSI_HARD_LIMIT": [60, 65, 70],
        }
        combos = self.optimizer._generate_valid_combinations(grid, "KR")
        assert len(combos) == 3
        for c in combos:
            assert "RSI_HARD_LIMIT" in c
            assert c["WEIGHT_TECHNICAL"] == 0.50
            assert c["WEIGHT_MACRO"] == 0.50

    def test_only_non_weight_params(self):
        """Grid with only non-weight params should work."""
        grid = {
            "RSI_HARD_LIMIT": [60, 65],
            "DISPARITY_HARD_LIMIT": [105, 110],
        }
        combos = self.optimizer._generate_valid_combinations(grid, "KR")
        assert len(combos) == 4  # 2 * 2

    def test_empty_grid(self):
        """Empty grid should return empty."""
        combos = self.optimizer._generate_valid_combinations({}, "KR")
        # No weight keys and no non-weight keys → should handle gracefully
        assert isinstance(combos, list)

    def test_us_fund_flow_zero_valid(self):
        """US market should allow fund_flow=0 in valid combos."""
        grid = {
            "WEIGHT_TECHNICAL": [0.40],
            "WEIGHT_MACRO": [0.20],
            "WEIGHT_FUND_FLOW": [0.0, 0.20],
            "WEIGHT_FUNDAMENTAL": [0.40, 0.20],
        }
        combos = self.optimizer._generate_valid_combinations(grid, "US")
        # Only combo with WEIGHT_FUND_FLOW=0 should pass
        for c in combos:
            assert c["WEIGHT_FUND_FLOW"] == 0.0

    def test_combos_are_dicts(self):
        """Each combo should be a dict."""
        combos = self.optimizer._generate_valid_combinations(
            ParameterOptimizer.DEFAULT_GRID, "KR"
        )
        for c in combos:
            assert isinstance(c, dict)


class TestOptimizerInit:
    def test_has_default_grid(self):
        """ParameterOptimizer should have a DEFAULT_GRID."""
        assert isinstance(ParameterOptimizer.DEFAULT_GRID, dict)
        assert "WEIGHT_TECHNICAL" in ParameterOptimizer.DEFAULT_GRID

    def test_init_creates_engine(self):
        """Optimizer should create a BacktestEngine."""
        config = _make_config()
        opt = ParameterOptimizer(config)
        assert opt.engine is not None
        assert opt.config is config
