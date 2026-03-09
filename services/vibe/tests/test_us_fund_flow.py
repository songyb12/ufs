"""Tests for app.pipeline.stages.s4b_us_fund_flow — _score_short_interest."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.pipeline.stages.s4b_us_fund_flow import _score_short_interest


class TestScoreShortInterest:
    """Test short interest scoring logic."""

    def test_empty_data(self):
        """Empty dict should return 0."""
        assert _score_short_interest({}) == 0.0

    def test_very_high_short(self):
        """Short > 20% should score +30 base."""
        score = _score_short_interest({"short_pct_float": 25.0})
        assert score >= 30.0

    def test_high_short(self):
        """Short 10-20% should score +15."""
        score = _score_short_interest({"short_pct_float": 15.0})
        assert score == 15.0

    def test_moderate_short(self):
        """Short 5-10% should score +5."""
        score = _score_short_interest({"short_pct_float": 7.0})
        assert score == 5.0

    def test_low_short(self):
        """Short < 5% should score 0 base."""
        score = _score_short_interest({"short_pct_float": 3.0})
        assert score == 0.0

    def test_rising_shorts_bearish(self):
        """Rising short change > 20% should subtract 15."""
        score = _score_short_interest({
            "short_pct_float": 15.0,
            "short_change_pct": 25.0,
        })
        assert score == 0.0  # 15 - 15

    def test_covering_shorts_bullish(self):
        """Shorts covering (change < -20%) should add 15."""
        score = _score_short_interest({
            "short_pct_float": 15.0,
            "short_change_pct": -25.0,
        })
        assert score == 30.0  # 15 + 15

    def test_very_high_with_covering(self):
        """Very high short + covering = very bullish."""
        score = _score_short_interest({
            "short_pct_float": 25.0,
            "short_change_pct": -30.0,
        })
        assert score == 45.0  # 30 + 15

    def test_capped_at_50(self):
        """Score should not exceed 50."""
        score = _score_short_interest({
            "short_pct_float": 100.0,
            "short_change_pct": -100.0,
        })
        assert score <= 50.0

    def test_capped_at_minus_50(self):
        """Score should not go below -50."""
        score = _score_short_interest({
            "short_pct_float": 0.0,
            "short_change_pct": 200.0,
        })
        assert score >= -50.0

    def test_zero_short(self):
        """Zero short interest should score 0 base."""
        score = _score_short_interest({"short_pct_float": 0.0})
        assert score == 0.0

    def test_missing_keys(self):
        """Missing keys should default to 0."""
        score = _score_short_interest({"some_other_key": 99})
        assert score == 0.0

    def test_moderate_change_neutral(self):
        """Change within -20% to +20% should not affect score."""
        score_base = _score_short_interest({"short_pct_float": 15.0})
        score_with_change = _score_short_interest({
            "short_pct_float": 15.0,
            "short_change_pct": 10.0,
        })
        assert score_base == score_with_change

    def test_return_type(self):
        """Score should be a float, rounded to 2 decimals."""
        score = _score_short_interest({"short_pct_float": 12.5})
        assert isinstance(score, float)

    def test_boundary_20_percent(self):
        """Exactly 20% short should score +15 (not +30)."""
        score = _score_short_interest({"short_pct_float": 20.0})
        assert score == 15.0  # 10-20 range, not > 20

    def test_boundary_10_percent(self):
        """Exactly 10% should score +5 (not +15)."""
        score = _score_short_interest({"short_pct_float": 10.0})
        assert score == 5.0  # 5-10 range, not > 10

    def test_boundary_5_percent(self):
        """Exactly 5% should score 0 (not +5)."""
        score = _score_short_interest({"short_pct_float": 5.0})
        assert score == 0.0  # < 5 range doesn't apply, 5-10 range uses > 5
