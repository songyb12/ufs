"""Tests for app.risk.position_sizing — position size computation."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from types import SimpleNamespace

from app.risk.position_sizing import PositionRecommendation, PositionSizer


def _make_config(**overrides):
    """Build a minimal Settings-like object with defaults."""
    defaults = {
        "MAX_SINGLE_POSITION_PCT": 0.10,
        "MAX_SECTOR_EXPOSURE_PCT": 0.30,
        "PORTFOLIO_TOTAL": 100_000_000,
        "POSITION_SIZING_METHOD": "fixed_fraction",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_signal(symbol="AAPL", confidence=1.0, raw_score=30, final_signal="BUY"):
    return {
        "symbol": symbol,
        "confidence": confidence,
        "raw_score": raw_score,
        "final_signal": final_signal,
    }


# ── PositionRecommendation dataclass ──


class TestPositionRecommendation:
    def test_dataclass_fields(self):
        rec = PositionRecommendation(
            symbol="AAPL",
            recommended_pct=0.10,
            recommended_amount=10_000_000,
            sizing_method="fixed_fraction",
            confidence_factor=1.0,
            sector="Tech",
            sector_exposure_current=0.10,
            sector_constraint_applied=False,
            rationale="test",
        )
        assert rec.symbol == "AAPL"
        assert rec.recommended_pct == 0.10
        assert rec.recommended_amount == 10_000_000
        assert rec.sizing_method == "fixed_fraction"
        assert rec.sector_constraint_applied is False

    def test_dataclass_equality(self):
        kwargs = dict(
            symbol="X", recommended_pct=0.05, recommended_amount=5000,
            sizing_method="kelly", confidence_factor=0.8, sector="Tech",
            sector_exposure_current=0.0, sector_constraint_applied=False,
            rationale="r",
        )
        a = PositionRecommendation(**kwargs)
        b = PositionRecommendation(**kwargs)
        assert a == b


# ── PositionSizer.compute — confidence adjustment ──


class TestPositionSizerConfidence:
    """Test confidence factor clamping: max(0.3, min(1.0, confidence))."""

    def test_full_confidence(self):
        """confidence=1.0 -> factor=1.0, full base allocation."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=1.0, raw_score=30), {})
        assert rec.confidence_factor == 1.0
        assert rec.recommended_pct == 0.10

    def test_half_confidence(self):
        """confidence=0.5 -> factor=0.5."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=0.5, raw_score=30), {})
        assert rec.confidence_factor == 0.5
        assert rec.recommended_pct == 0.05

    def test_low_confidence_clamped_to_floor(self):
        """confidence=0.1 -> clamped to 0.3 (floor)."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=0.1, raw_score=30), {})
        assert rec.confidence_factor == 0.30
        assert rec.recommended_pct == 0.03

    def test_zero_confidence_clamped_to_floor(self):
        """confidence=0.0 -> clamped to 0.3."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=0.0, raw_score=30), {})
        assert rec.confidence_factor == 0.30

    def test_negative_confidence_clamped_to_floor(self):
        """confidence=-0.5 -> clamped to 0.3."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=-0.5, raw_score=30), {})
        assert rec.confidence_factor == 0.30

    def test_above_one_clamped_to_ceiling(self):
        """confidence=2.0 -> clamped to 1.0."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=2.0, raw_score=30), {})
        assert rec.confidence_factor == 1.0
        assert rec.recommended_pct == 0.10

    def test_exactly_at_floor_boundary(self):
        """confidence=0.3 -> factor=0.3 (exactly at floor)."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=0.3, raw_score=30), {})
        assert rec.confidence_factor == 0.30
        assert rec.recommended_pct == 0.03

    def test_missing_confidence_defaults_to_1(self):
        """Signal without 'confidence' key -> defaults to 1.0."""
        sizer = PositionSizer(_make_config())
        signal = {"symbol": "AAPL", "raw_score": 30, "final_signal": "BUY"}
        rec = sizer.compute(signal, {})
        assert rec.confidence_factor == 1.0
        assert rec.recommended_pct == 0.10


# ── PositionSizer.compute — score magnitude adjustment ──


class TestPositionSizerScoreFactor:
    """Test score_factor = min(1.0, raw_score/30) then max(0.5, score_factor)."""

    def test_score_30_full_factor(self):
        """raw_score=30 -> score_factor=1.0."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(raw_score=30), {})
        assert rec.recommended_pct == 0.10  # 10% * 1.0 * 1.0

    def test_score_above_30_capped(self):
        """raw_score=60 -> min(1.0, 2.0)=1.0."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(raw_score=60), {})
        assert rec.recommended_pct == 0.10

    def test_score_15_factor_at_floor(self):
        """raw_score=15 -> 15/30=0.5, max(0.5, 0.5)=0.5."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(raw_score=15), {})
        assert rec.recommended_pct == 0.05

    def test_score_5_factor_floored(self):
        """raw_score=5 -> 5/30=0.167, max(0.5, 0.167)=0.5."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(raw_score=5), {})
        assert rec.recommended_pct == 0.05

    def test_score_0_factor_floored(self):
        """raw_score=0 -> 0/30=0.0, max(0.5, 0.0)=0.5."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(raw_score=0), {})
        assert rec.recommended_pct == 0.05

    def test_negative_score_uses_abs(self):
        """raw_score=-20 -> abs(-20)=20, 20/30=0.667, max(0.5, 0.667)=0.667."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(raw_score=-20), {})
        expected = round(0.10 * 1.0 * (20 / 30), 4)
        assert rec.recommended_pct == expected

    def test_score_20_above_floor(self):
        """raw_score=20 -> 20/30=0.667, above 0.5 floor."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(raw_score=20), {})
        expected = round(0.10 * (20 / 30), 4)
        assert rec.recommended_pct == expected

    def test_missing_raw_score_defaults_to_0(self):
        """Signal without 'raw_score' -> defaults to 0, floored at 0.5."""
        sizer = PositionSizer(_make_config())
        signal = {"symbol": "AAPL", "confidence": 1.0, "final_signal": "BUY"}
        rec = sizer.compute(signal, {})
        assert rec.recommended_pct == 0.05  # 10% * 1.0 * 0.5


# ── PositionSizer.compute — combined adjustments ──


class TestPositionSizerCombined:
    """Test combinations of confidence and score adjustments."""

    def test_low_confidence_low_score(self):
        """confidence=0.5, raw_score=10 -> 10%*0.5*0.5=2.5%."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=0.5, raw_score=10), {})
        # score_factor = 10/30 = 0.333, floored at 0.5
        assert rec.recommended_pct == 0.025

    def test_low_confidence_high_score(self):
        """confidence=0.4, raw_score=40 -> 10%*0.4*1.0=4%."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=0.4, raw_score=40), {})
        assert rec.recommended_pct == 0.04

    def test_minimum_allocation(self):
        """Floor confidence (0.3) + floor score (0.5) -> 10%*0.3*0.5=1.5%."""
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=0.0, raw_score=0), {})
        assert rec.recommended_pct == 0.015


# ── PositionSizer.compute — sector constraints ──


class TestPositionSizerSectorConstraint:
    """Test sector limit interaction inside compute."""

    def test_no_existing_positions(self):
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(symbol="AAPL"), {})
        assert rec.sector_constraint_applied is False
        assert rec.sector == "Tech"

    def test_sector_constraint_applied(self):
        """Sector already at 25%, adding 10% exceeds 30%."""
        sizer = PositionSizer(_make_config())
        existing = {"MSFT": 0.10, "GOOGL": 0.10, "META": 0.05}  # Tech: 25%
        rec = sizer.compute(_make_signal(symbol="AAPL"), existing)
        assert rec.recommended_pct == 0.05
        assert rec.sector_constraint_applied is True
        assert "Sector limit applied" in rec.rationale

    def test_sector_fully_exhausted(self):
        """Sector at limit -> 0% allocation."""
        sizer = PositionSizer(_make_config())
        existing = {"MSFT": 0.15, "GOOGL": 0.15}  # Tech: 30%
        rec = sizer.compute(_make_signal(symbol="AAPL"), existing)
        assert rec.recommended_pct == 0.0
        assert rec.recommended_amount == 0
        assert rec.sector_constraint_applied is True

    def test_different_sector_no_constraint(self):
        """Full Tech does not affect Semiconductor."""
        sizer = PositionSizer(_make_config())
        existing = {"AAPL": 0.15, "MSFT": 0.15}  # Tech: 30%
        rec = sizer.compute(_make_signal(symbol="NVDA"), existing)
        assert rec.recommended_pct == 0.10
        assert rec.sector == "Semiconductor"
        assert rec.sector_constraint_applied is False

    def test_sector_exposure_current_reflects_existing(self):
        """sector_exposure_current should show existing exposure for the sector."""
        sizer = PositionSizer(_make_config())
        existing = {"MSFT": 0.10, "GOOGL": 0.05}  # Tech: 15%
        rec = sizer.compute(_make_signal(symbol="AAPL"), existing)
        assert rec.sector_exposure_current == 0.15


# ── PositionSizer.compute — config variations ──


class TestPositionSizerConfig:
    """Test that config overrides are correctly applied."""

    def test_custom_portfolio_total(self):
        config = _make_config(PORTFOLIO_TOTAL=50_000_000)
        sizer = PositionSizer(config)
        rec = sizer.compute(_make_signal(confidence=1.0, raw_score=30), {})
        assert rec.recommended_pct == 0.10
        assert rec.recommended_amount == 5_000_000

    def test_custom_max_single_position(self):
        config = _make_config(MAX_SINGLE_POSITION_PCT=0.20)
        sizer = PositionSizer(config)
        rec = sizer.compute(_make_signal(confidence=1.0, raw_score=30), {})
        assert rec.recommended_pct == 0.20

    def test_small_max_position(self):
        config = _make_config(MAX_SINGLE_POSITION_PCT=0.02)
        sizer = PositionSizer(config)
        rec = sizer.compute(_make_signal(confidence=1.0, raw_score=30), {})
        assert rec.recommended_pct == 0.02

    def test_sizing_method_in_result(self):
        config = _make_config(POSITION_SIZING_METHOD="kelly")
        sizer = PositionSizer(config)
        rec = sizer.compute(_make_signal(), {})
        assert rec.sizing_method == "kelly"

    def test_amount_proportional_to_pct(self):
        """recommended_amount should be roughly PORTFOLIO_TOTAL * recommended_pct.

        Note: amount is computed from the pre-rounded final_pct, while
        recommended_pct is round(final_pct, 4), so small differences are expected.
        """
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=1.0, raw_score=30), {})
        expected_amount = round(100_000_000 * rec.recommended_pct)
        assert abs(rec.recommended_amount - expected_amount) <= 1


# ── PositionSizer.compute — symbol variations ──


class TestPositionSizerSymbols:
    """Test various symbol types."""

    def test_kr_stock(self):
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(symbol="005930", confidence=0.8, raw_score=25), {})
        assert rec.sector == "반도체"
        assert rec.symbol == "005930"
        assert rec.confidence_factor == 0.80

    def test_us_etf(self):
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(symbol="SPY"), {})
        assert rec.sector == "ETF"

    def test_unknown_sector_symbol(self):
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(symbol="ZZZZ"), {})
        assert rec.sector == "Unknown"


# ── PositionSizer.compute — rationale ──


class TestPositionSizerRationale:
    """Test rationale string contents."""

    def test_rationale_contains_base_parts(self):
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(confidence=0.7, raw_score=20), {})
        assert "Base:" in rec.rationale
        assert "Conf adj:" in rec.rationale
        assert "Score adj:" in rec.rationale

    def test_rationale_includes_sector_limit_when_constrained(self):
        sizer = PositionSizer(_make_config())
        existing = {"MSFT": 0.25}  # Tech: 25%
        rec = sizer.compute(_make_signal(symbol="AAPL"), existing)
        assert "Sector limit applied" in rec.rationale
        assert "Tech" in rec.rationale

    def test_rationale_no_sector_limit_when_unconstrained(self):
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(), {})
        assert "Sector limit applied" not in rec.rationale

    def test_rationale_pipe_separated(self):
        sizer = PositionSizer(_make_config())
        rec = sizer.compute(_make_signal(), {})
        parts = rec.rationale.split(" | ")
        assert len(parts) >= 3
