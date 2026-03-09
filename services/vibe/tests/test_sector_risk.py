"""Tests for app.risk.sector — sector classification and exposure."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.risk.sector import get_sector, compute_sector_exposure, check_sector_limit


class TestGetSector:
    def test_known_kr_symbol(self):
        assert get_sector("005930") == "반도체"

    def test_known_us_symbol(self):
        assert get_sector("AAPL") == "Tech"

    def test_etf(self):
        assert get_sector("SPY") == "ETF"

    def test_unknown_symbol(self):
        assert get_sector("ZZZZZ") == "Unknown"

    def test_empty_string(self):
        assert get_sector("") == "Unknown"

    def test_all_sectors_non_empty(self):
        for symbol, sector in [
            ("005930", "반도체"), ("373220", "배터리"), ("207940", "바이오"),
            ("005380", "자동차"), ("035420", "인터넷"), ("105560", "금융"),
            ("NVDA", "Semiconductor"), ("TSLA", "Auto"), ("UNH", "Healthcare"),
            ("XOM", "Energy"), ("BRK-B", "Finance"), ("AMZN", "Consumer"),
        ]:
            assert get_sector(symbol) == sector


class TestComputeSectorExposure:
    def test_empty_positions(self):
        assert compute_sector_exposure({}) == {}

    def test_single_position(self):
        result = compute_sector_exposure({"AAPL": 25.0})
        assert result == {"Tech": 25.0}

    def test_same_sector_aggregation(self):
        result = compute_sector_exposure({"AAPL": 15.0, "MSFT": 10.0, "GOOGL": 5.0})
        assert result["Tech"] == 30.0

    def test_multiple_sectors(self):
        result = compute_sector_exposure({
            "AAPL": 15.0,
            "NVDA": 10.0,
            "XOM": 8.0,
        })
        assert result["Tech"] == 15.0
        assert result["Semiconductor"] == 10.0
        assert result["Energy"] == 8.0

    def test_unknown_sector(self):
        result = compute_sector_exposure({"ZZZZ": 5.0})
        assert result["Unknown"] == 5.0


class TestCheckSectorLimit:
    def test_no_existing_positions(self):
        pct, constrained = check_sector_limit("AAPL", 20.0, {}, max_sector_pct=30.0)
        assert pct == 20.0
        assert constrained is False

    def test_within_limit(self):
        pct, constrained = check_sector_limit("MSFT", 10.0, {"AAPL": 15.0}, max_sector_pct=30.0)
        assert pct == 10.0
        assert constrained is False

    def test_constrained(self):
        pct, constrained = check_sector_limit("MSFT", 20.0, {"AAPL": 15.0, "GOOGL": 10.0}, max_sector_pct=30.0)
        # Tech already at 25%, max=30 → remaining=5
        assert pct == 5.0
        assert constrained is True

    def test_sector_at_limit(self):
        pct, constrained = check_sector_limit("MSFT", 10.0, {"AAPL": 15.0, "GOOGL": 15.0}, max_sector_pct=30.0)
        assert pct == 0.0
        assert constrained is True

    def test_different_sector_not_affected(self):
        pct, constrained = check_sector_limit("NVDA", 20.0, {"AAPL": 25.0}, max_sector_pct=30.0)
        # NVDA is Semiconductor, not Tech
        assert pct == 20.0
        assert constrained is False

    def test_cross_kr_us_sectors(self):
        pct, constrained = check_sector_limit(
            "005930", 15.0,
            {"000660": 20.0},  # Both 반도체
            max_sector_pct=30.0,
        )
        assert pct == 10.0
        assert constrained is True
