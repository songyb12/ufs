"""Tests for position sizing and sector exposure calculations."""

import pytest
from unittest.mock import MagicMock

from app.risk.position_sizing import PositionSizer, PositionRecommendation
from app.risk.sector import get_sector, compute_sector_exposure, check_sector_limit


# ── Sector Tests ──

class TestGetSector:
    """Test sector classification."""

    def test_kr_stock_known(self):
        assert get_sector("005930") == "반도체"  # Samsung

    def test_us_stock_known(self):
        assert get_sector("AAPL") == "Tech"

    def test_etf_kr(self):
        assert get_sector("069500") == "ETF"

    def test_etf_us(self):
        assert get_sector("SPY") == "ETF"

    def test_unknown_symbol(self):
        assert get_sector("UNKNOWN123") == "Unknown"


class TestComputeSectorExposure:
    """Test sector exposure calculation."""

    def test_single_sector(self):
        positions = {"005930": 0.10, "000660": 0.08}
        exposure = compute_sector_exposure(positions)
        assert exposure["반도체"] == pytest.approx(0.18)

    def test_multiple_sectors(self):
        positions = {"005930": 0.10, "AAPL": 0.05}
        exposure = compute_sector_exposure(positions)
        assert "반도체" in exposure
        assert "Tech" in exposure

    def test_empty_positions(self):
        exposure = compute_sector_exposure({})
        assert exposure == {}


class TestCheckSectorLimit:
    """Test sector limit enforcement."""

    def test_within_limit(self):
        positions = {"005930": 0.10}
        pct, constrained = check_sector_limit("000660", 0.08, positions, 0.30)
        assert pct == 0.08
        assert constrained is False

    def test_exceeds_limit(self):
        positions = {"005930": 0.15, "000660": 0.10}
        pct, constrained = check_sector_limit("000660", 0.10, positions, 0.30)
        # 반도체 already at 0.25, limit 0.30, remaining 0.05
        assert pct == pytest.approx(0.05)
        assert constrained is True

    def test_at_limit_returns_zero(self):
        positions = {"005930": 0.15, "000660": 0.15}
        pct, constrained = check_sector_limit("000660", 0.10, positions, 0.30)
        assert pct == 0.0
        assert constrained is True

    def test_different_sector_no_constraint(self):
        positions = {"005930": 0.25}  # 반도체 at 0.25
        pct, constrained = check_sector_limit("AAPL", 0.10, positions, 0.30)
        # AAPL is Tech, no existing Tech exposure
        assert pct == 0.10
        assert constrained is False


# ── Position Sizer Tests ──

def _make_config(**overrides):
    config = MagicMock()
    config.MAX_SINGLE_POSITION_PCT = 0.10
    config.MAX_SECTOR_EXPOSURE_PCT = 0.30
    config.PORTFOLIO_TOTAL = 100_000_000
    config.POSITION_SIZING_METHOD = "fixed_fraction"
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


class TestPositionSizer:
    """Test PositionSizer.compute()."""

    def test_basic_recommendation(self):
        sizer = PositionSizer(_make_config())
        signal = {"symbol": "005930", "confidence": 1.0, "raw_score": 30}
        result = sizer.compute(signal, {})

        assert isinstance(result, PositionRecommendation)
        assert result.symbol == "005930"
        assert result.recommended_pct > 0
        assert result.recommended_amount > 0
        assert result.sector == "반도체"

    def test_low_confidence_reduces_size(self):
        sizer = PositionSizer(_make_config())
        high_conf = sizer.compute({"symbol": "005930", "confidence": 1.0, "raw_score": 30}, {})
        low_conf = sizer.compute({"symbol": "005930", "confidence": 0.5, "raw_score": 30}, {})

        assert low_conf.recommended_pct < high_conf.recommended_pct
        assert low_conf.recommended_amount < high_conf.recommended_amount

    def test_low_score_reduces_size(self):
        sizer = PositionSizer(_make_config())
        high_score = sizer.compute({"symbol": "005930", "confidence": 1.0, "raw_score": 40}, {})
        low_score = sizer.compute({"symbol": "005930", "confidence": 1.0, "raw_score": 5}, {})

        assert low_score.recommended_pct < high_score.recommended_pct

    def test_sector_constraint_applied(self):
        sizer = PositionSizer(_make_config())
        # 반도체 already at 25% (005930=15%, 000660=10%)
        existing = {"005930": 0.15, "000660": 0.10}
        result = sizer.compute(
            {"symbol": "000660", "confidence": 1.0, "raw_score": 30},
            existing,
        )

        assert result.sector_constraint_applied is True
        assert result.recommended_pct <= 0.05  # Max 30% - 25% = 5% remaining

    def test_max_single_position_respected(self):
        sizer = PositionSizer(_make_config(MAX_SINGLE_POSITION_PCT=0.05))
        result = sizer.compute(
            {"symbol": "005930", "confidence": 1.0, "raw_score": 50},
            {},
        )

        assert result.recommended_pct <= 0.05

    def test_confidence_floor_at_0_3(self):
        sizer = PositionSizer(_make_config())
        result = sizer.compute(
            {"symbol": "005930", "confidence": 0.1, "raw_score": 30},
            {},
        )

        assert result.confidence_factor == 0.3  # Floored at 0.3

    def test_amount_matches_pct(self):
        sizer = PositionSizer(_make_config())
        result = sizer.compute(
            {"symbol": "005930", "confidence": 1.0, "raw_score": 30},
            {},
        )

        expected_amount = 100_000_000 * result.recommended_pct
        assert abs(result.recommended_amount - expected_amount) < 1

    def test_rationale_not_empty(self):
        sizer = PositionSizer(_make_config())
        result = sizer.compute(
            {"symbol": "005930", "confidence": 0.8, "raw_score": 25},
            {},
        )

        assert len(result.rationale) > 0
        assert "Base" in result.rationale
