"""Tests for app.briefing.market_briefing — helper functions."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.briefing.market_briefing import _vix_label, _fg_label


# ── _vix_label ──


class TestVixLabel:
    def test_none(self):
        assert _vix_label(None) == "N/A"

    def test_very_stable(self):
        assert _vix_label(10) == "매우 안정"

    def test_stable(self):
        assert _vix_label(15) == "안정"

    def test_caution(self):
        assert _vix_label(22) == "주의"

    def test_alert(self):
        assert _vix_label(27) == "경계"

    def test_fear(self):
        assert _vix_label(35) == "공포"

    def test_boundaries(self):
        assert _vix_label(12) == "안정"  # 12 is not < 12
        assert _vix_label(20) == "주의"  # 20 is not < 20
        assert _vix_label(25) == "경계"  # 25 is not < 25
        assert _vix_label(30) == "공포"  # 30 is not < 30


# ── _fg_label ──


class TestFgLabel:
    def test_none(self):
        assert _fg_label(None) == "N/A"

    def test_extreme_fear(self):
        assert _fg_label(10) == "극단적 공포"

    def test_fear(self):
        assert _fg_label(30) == "공포"

    def test_neutral(self):
        assert _fg_label(50) == "중립"

    def test_greed(self):
        assert _fg_label(70) == "탐욕"

    def test_extreme_greed(self):
        assert _fg_label(90) == "극단적 탐욕"

    def test_boundaries(self):
        assert _fg_label(20) == "극단적 공포"  # 20 is <= 20
        assert _fg_label(40) == "공포"          # 40 is <= 40
        assert _fg_label(60) == "중립"          # 60 is <= 60
        assert _fg_label(80) == "탐욕"          # 80 is <= 80
        assert _fg_label(81) == "극단적 탐욕"   # 81 is > 80
