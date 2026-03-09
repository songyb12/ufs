"""Tests for the geopolitical event dashboard router.

Validates static data structures (timeline, market impact, sector impact,
semiconductor risks, historical precedents, key variables, hedging strategies)
and the /geopolitical/iran-us API endpoint.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.routers.geopolitical import (
    HEDGING_STRATEGIES,
    HISTORICAL_PRECEDENTS,
    IRAN_US_TIMELINE,
    KEY_VARIABLES,
    MARKET_IMPACT,
    SECTOR_IMPACT,
    SEMICONDUCTOR_RISKS,
)


# ── Timeline Tests ──


class TestIranUsTimeline:
    """Validate IRAN_US_TIMELINE entries."""

    REQUIRED_KEYS = {"date", "event", "impact", "detail"}
    VALID_IMPACTS = {"neutral", "positive", "negative", "severe_negative"}

    def test_timeline_not_empty(self):
        assert len(IRAN_US_TIMELINE) > 0

    def test_timeline_count(self):
        assert len(IRAN_US_TIMELINE) == 6

    def test_all_entries_have_required_keys(self):
        for i, entry in enumerate(IRAN_US_TIMELINE):
            missing = self.REQUIRED_KEYS - set(entry.keys())
            assert not missing, f"Entry {i} missing keys: {missing}"

    def test_all_impacts_valid(self):
        for i, entry in enumerate(IRAN_US_TIMELINE):
            assert entry["impact"] in self.VALID_IMPACTS, (
                f"Entry {i} has invalid impact: {entry['impact']}"
            )

    def test_dates_are_valid_iso_format(self):
        for i, entry in enumerate(IRAN_US_TIMELINE):
            try:
                datetime.strptime(entry["date"], "%Y-%m-%d")
            except ValueError:
                pytest.fail(f"Entry {i} has invalid date format: {entry['date']}")

    def test_dates_chronological_order(self):
        dates = [datetime.strptime(e["date"], "%Y-%m-%d") for e in IRAN_US_TIMELINE]
        for i in range(1, len(dates)):
            assert dates[i] >= dates[i - 1], (
                f"Date {IRAN_US_TIMELINE[i]['date']} is before "
                f"{IRAN_US_TIMELINE[i - 1]['date']}"
            )

    def test_no_empty_event_strings(self):
        for i, entry in enumerate(IRAN_US_TIMELINE):
            assert entry["event"].strip(), f"Entry {i} has empty event"

    def test_no_empty_detail_strings(self):
        for i, entry in enumerate(IRAN_US_TIMELINE):
            assert entry["detail"].strip(), f"Entry {i} has empty detail"

    def test_first_event_date(self):
        assert IRAN_US_TIMELINE[0]["date"] == "2026-02-06"

    def test_last_event_date(self):
        assert IRAN_US_TIMELINE[-1]["date"] == "2026-03-08"

    def test_conflict_start_event_present(self):
        """The Feb 28 airstrike start should be in the timeline."""
        dates = [e["date"] for e in IRAN_US_TIMELINE]
        assert "2026-02-28" in dates

    def test_severe_negative_events_exist(self):
        severe = [e for e in IRAN_US_TIMELINE if e["impact"] == "severe_negative"]
        assert len(severe) >= 2, "Expected at least 2 severe_negative events"

    def test_no_duplicate_dates_with_same_event(self):
        seen = set()
        for entry in IRAN_US_TIMELINE:
            key = (entry["date"], entry["event"])
            assert key not in seen, f"Duplicate entry: {key}"
            seen.add(key)


# ── Market Impact Tests ──


class TestMarketImpact:
    """Validate MARKET_IMPACT dictionary."""

    EXPECTED_CATEGORIES = {"oil", "gold", "usd", "equities"}

    def test_market_impact_not_empty(self):
        assert len(MARKET_IMPACT) > 0

    def test_expected_categories_present(self):
        assert set(MARKET_IMPACT.keys()) == self.EXPECTED_CATEGORIES

    def test_all_entries_have_title(self):
        for key, val in MARKET_IMPACT.items():
            assert "title" in val, f"Category '{key}' missing 'title'"
            assert val["title"].strip(), f"Category '{key}' has empty title"

    def test_all_entries_have_detail(self):
        for key, val in MARKET_IMPACT.items():
            assert "detail" in val, f"Category '{key}' missing 'detail'"
            assert val["detail"].strip(), f"Category '{key}' has empty detail"

    def test_oil_has_before_after(self):
        assert "before" in MARKET_IMPACT["oil"]
        assert "after" in MARKET_IMPACT["oil"]

    def test_oil_has_change_pct(self):
        assert "change_pct" in MARKET_IMPACT["oil"]

    def test_gold_has_before_after(self):
        assert "before" in MARKET_IMPACT["gold"]
        assert "after" in MARKET_IMPACT["gold"]

    def test_gold_has_change_pct(self):
        assert "change_pct" in MARKET_IMPACT["gold"]

    def test_usd_has_change_pct(self):
        assert "change_pct" in MARKET_IMPACT["usd"]

    def test_equities_has_major_indices(self):
        eq = MARKET_IMPACT["equities"]
        for idx in ("sp500", "nikkei", "dax", "kospi"):
            assert idx in eq, f"Missing index: {idx}"

    def test_category_count(self):
        assert len(MARKET_IMPACT) == 4


# ── Sector Impact Tests ──


class TestSectorImpact:
    """Validate SECTOR_IMPACT list."""

    REQUIRED_KEYS = {"sector", "direction", "magnitude", "tickers", "reason"}
    VALID_DIRECTIONS = {"up", "down"}
    VALID_MAGNITUDES = {"low", "medium", "high", "very_high"}

    def test_sector_impact_not_empty(self):
        assert len(SECTOR_IMPACT) > 0

    def test_sector_impact_count(self):
        assert len(SECTOR_IMPACT) == 10

    def test_all_entries_have_required_keys(self):
        for i, entry in enumerate(SECTOR_IMPACT):
            missing = self.REQUIRED_KEYS - set(entry.keys())
            assert not missing, f"Entry {i} missing keys: {missing}"

    def test_all_directions_valid(self):
        for i, entry in enumerate(SECTOR_IMPACT):
            assert entry["direction"] in self.VALID_DIRECTIONS, (
                f"Entry {i} has invalid direction: {entry['direction']}"
            )

    def test_all_magnitudes_valid(self):
        for i, entry in enumerate(SECTOR_IMPACT):
            assert entry["magnitude"] in self.VALID_MAGNITUDES, (
                f"Entry {i} has invalid magnitude: {entry['magnitude']}"
            )

    def test_tickers_are_lists(self):
        for i, entry in enumerate(SECTOR_IMPACT):
            assert isinstance(entry["tickers"], list), (
                f"Entry {i} tickers is not a list"
            )

    def test_no_empty_sector_names(self):
        for i, entry in enumerate(SECTOR_IMPACT):
            assert entry["sector"].strip(), f"Entry {i} has empty sector"

    def test_no_empty_reasons(self):
        for i, entry in enumerate(SECTOR_IMPACT):
            assert entry["reason"].strip(), f"Entry {i} has empty reason"

    def test_up_sectors_exist(self):
        up = [s for s in SECTOR_IMPACT if s["direction"] == "up"]
        assert len(up) >= 1

    def test_down_sectors_exist(self):
        down = [s for s in SECTOR_IMPACT if s["direction"] == "down"]
        assert len(down) >= 1

    def test_up_sector_count(self):
        up = [s for s in SECTOR_IMPACT if s["direction"] == "up"]
        assert len(up) == 5

    def test_down_sector_count(self):
        down = [s for s in SECTOR_IMPACT if s["direction"] == "down"]
        assert len(down) == 5

    def test_semiconductor_in_sectors(self):
        sectors = [s["sector"] for s in SECTOR_IMPACT]
        semi = [s for s in sectors if "반도체" in s]
        assert len(semi) >= 1, "Semiconductor sector not found"

    def test_energy_in_sectors(self):
        sectors = [s["sector"] for s in SECTOR_IMPACT]
        energy = [s for s in sectors if "에너지" in s]
        assert len(energy) >= 1, "Energy sector not found"

    def test_no_duplicate_sectors(self):
        sectors = [s["sector"] for s in SECTOR_IMPACT]
        assert len(sectors) == len(set(sectors)), "Duplicate sector names found"

    def test_very_high_magnitude_sectors(self):
        vh = [s for s in SECTOR_IMPACT if s["magnitude"] == "very_high"]
        assert len(vh) >= 1, "Expected at least one very_high magnitude sector"


# ── Semiconductor Risks Tests ──


class TestSemiconductorRisks:
    """Validate SEMICONDUCTOR_RISKS list."""

    REQUIRED_KEYS = {"risk", "severity", "detail"}
    VALID_SEVERITIES = {"critical", "high", "medium", "low"}

    def test_risks_not_empty(self):
        assert len(SEMICONDUCTOR_RISKS) > 0

    def test_risk_count(self):
        assert len(SEMICONDUCTOR_RISKS) == 6

    def test_all_entries_have_required_keys(self):
        for i, entry in enumerate(SEMICONDUCTOR_RISKS):
            missing = self.REQUIRED_KEYS - set(entry.keys())
            assert not missing, f"Entry {i} missing keys: {missing}"

    def test_all_severities_valid(self):
        for i, entry in enumerate(SEMICONDUCTOR_RISKS):
            assert entry["severity"] in self.VALID_SEVERITIES, (
                f"Entry {i} has invalid severity: {entry['severity']}"
            )

    def test_no_empty_risk_strings(self):
        for i, entry in enumerate(SEMICONDUCTOR_RISKS):
            assert entry["risk"].strip(), f"Entry {i} has empty risk"

    def test_no_empty_detail_strings(self):
        for i, entry in enumerate(SEMICONDUCTOR_RISKS):
            assert entry["detail"].strip(), f"Entry {i} has empty detail"

    def test_critical_severity_exists(self):
        critical = [r for r in SEMICONDUCTOR_RISKS if r["severity"] == "critical"]
        assert len(critical) >= 1

    def test_high_severity_exists(self):
        high = [r for r in SEMICONDUCTOR_RISKS if r["severity"] == "high"]
        assert len(high) >= 1

    def test_medium_severity_exists(self):
        medium = [r for r in SEMICONDUCTOR_RISKS if r["severity"] == "medium"]
        assert len(medium) >= 1

    def test_no_duplicate_risk_names(self):
        names = [r["risk"] for r in SEMICONDUCTOR_RISKS]
        assert len(names) == len(set(names)), "Duplicate risk names found"

    def test_helium_risk_present(self):
        risks = [r["risk"] for r in SEMICONDUCTOR_RISKS]
        helium = [r for r in risks if "헬륨" in r]
        assert len(helium) >= 1, "Helium supply risk not found"

    def test_energy_cost_risk_present(self):
        risks = [r["risk"] for r in SEMICONDUCTOR_RISKS]
        energy = [r for r in risks if "에너지" in r]
        assert len(energy) >= 1, "Energy cost risk not found"


# ── Historical Precedents Tests ──


class TestHistoricalPrecedents:
    """Validate HISTORICAL_PRECEDENTS list."""

    REQUIRED_KEYS = {"event", "market_decline", "recovery", "key_factor"}

    def test_precedents_not_empty(self):
        assert len(HISTORICAL_PRECEDENTS) > 0

    def test_precedent_count(self):
        assert len(HISTORICAL_PRECEDENTS) == 4

    def test_all_entries_have_required_keys(self):
        for i, entry in enumerate(HISTORICAL_PRECEDENTS):
            missing = self.REQUIRED_KEYS - set(entry.keys())
            assert not missing, f"Entry {i} missing keys: {missing}"

    def test_no_empty_event_strings(self):
        for i, entry in enumerate(HISTORICAL_PRECEDENTS):
            assert entry["event"].strip(), f"Entry {i} has empty event"

    def test_no_empty_market_decline_strings(self):
        for i, entry in enumerate(HISTORICAL_PRECEDENTS):
            assert entry["market_decline"].strip(), f"Entry {i} has empty market_decline"

    def test_no_empty_recovery_strings(self):
        for i, entry in enumerate(HISTORICAL_PRECEDENTS):
            assert entry["recovery"].strip(), f"Entry {i} has empty recovery"

    def test_no_empty_key_factor_strings(self):
        for i, entry in enumerate(HISTORICAL_PRECEDENTS):
            assert entry["key_factor"].strip(), f"Entry {i} has empty key_factor"

    def test_gulf_war_present(self):
        events = [p["event"] for p in HISTORICAL_PRECEDENTS]
        gulf = [e for e in events if "걸프" in e]
        assert len(gulf) >= 1, "Gulf War precedent not found"

    def test_iraq_invasion_present(self):
        events = [p["event"] for p in HISTORICAL_PRECEDENTS]
        iraq = [e for e in events if "이라크" in e and "침공" in e]
        assert len(iraq) >= 1, "Iraq invasion precedent not found"

    def test_oil_embargo_present(self):
        events = [p["event"] for p in HISTORICAL_PRECEDENTS]
        embargo = [e for e in events if "금수" in e or "석유" in e]
        assert len(embargo) >= 1, "Oil embargo precedent not found"

    def test_historical_average_present(self):
        events = [p["event"] for p in HISTORICAL_PRECEDENTS]
        avg = [e for e in events if "평균" in e]
        assert len(avg) >= 1, "Historical average entry not found"

    def test_no_duplicate_events(self):
        events = [p["event"] for p in HISTORICAL_PRECEDENTS]
        assert len(events) == len(set(events)), "Duplicate events found"


# ── Key Variables Tests ──


class TestKeyVariables:
    """Validate KEY_VARIABLES list."""

    REQUIRED_KEYS = {"variable", "current", "bullish", "bearish"}

    def test_variables_not_empty(self):
        assert len(KEY_VARIABLES) > 0

    def test_variable_count(self):
        assert len(KEY_VARIABLES) == 5

    def test_all_entries_have_required_keys(self):
        for i, entry in enumerate(KEY_VARIABLES):
            missing = self.REQUIRED_KEYS - set(entry.keys())
            assert not missing, f"Entry {i} missing keys: {missing}"

    def test_no_empty_variable_names(self):
        for i, entry in enumerate(KEY_VARIABLES):
            assert entry["variable"].strip(), f"Entry {i} has empty variable"

    def test_no_empty_current_values(self):
        for i, entry in enumerate(KEY_VARIABLES):
            assert entry["current"].strip(), f"Entry {i} has empty current"

    def test_no_empty_bullish_values(self):
        for i, entry in enumerate(KEY_VARIABLES):
            assert entry["bullish"].strip(), f"Entry {i} has empty bullish"

    def test_no_empty_bearish_values(self):
        for i, entry in enumerate(KEY_VARIABLES):
            assert entry["bearish"].strip(), f"Entry {i} has empty bearish"

    def test_hormuz_strait_variable_present(self):
        variables = [v["variable"] for v in KEY_VARIABLES]
        hormuz = [v for v in variables if "호르무즈" in v]
        assert len(hormuz) >= 1, "Hormuz strait variable not found"

    def test_oil_price_variable_present(self):
        variables = [v["variable"] for v in KEY_VARIABLES]
        oil = [v for v in variables if "유가" in v]
        assert len(oil) >= 1, "Oil price variable not found"

    def test_conflict_duration_variable_present(self):
        variables = [v["variable"] for v in KEY_VARIABLES]
        duration = [v for v in variables if "기간" in v]
        assert len(duration) >= 1, "Conflict duration variable not found"

    def test_fed_response_variable_present(self):
        variables = [v["variable"] for v in KEY_VARIABLES]
        fed = [v for v in variables if "연준" in v]
        assert len(fed) >= 1, "Fed response variable not found"

    def test_escalation_variable_present(self):
        variables = [v["variable"] for v in KEY_VARIABLES]
        escalation = [v for v in variables if "확전" in v]
        assert len(escalation) >= 1, "Escalation scope variable not found"

    def test_no_duplicate_variables(self):
        variables = [v["variable"] for v in KEY_VARIABLES]
        assert len(variables) == len(set(variables)), "Duplicate variables found"


# ── Hedging Strategies Tests ──


class TestHedgingStrategies:
    """Validate HEDGING_STRATEGIES list."""

    REQUIRED_KEYS = {"strategy", "rationale"}

    def test_strategies_not_empty(self):
        assert len(HEDGING_STRATEGIES) > 0

    def test_strategy_count(self):
        assert len(HEDGING_STRATEGIES) == 6

    def test_all_entries_have_required_keys(self):
        for i, entry in enumerate(HEDGING_STRATEGIES):
            missing = self.REQUIRED_KEYS - set(entry.keys())
            assert not missing, f"Entry {i} missing keys: {missing}"

    def test_no_empty_strategy_strings(self):
        for i, entry in enumerate(HEDGING_STRATEGIES):
            assert entry["strategy"].strip(), f"Entry {i} has empty strategy"

    def test_no_empty_rationale_strings(self):
        for i, entry in enumerate(HEDGING_STRATEGIES):
            assert entry["rationale"].strip(), f"Entry {i} has empty rationale"

    def test_oil_hedge_present(self):
        strategies = [s["strategy"] for s in HEDGING_STRATEGIES]
        oil = [s for s in strategies if "원유" in s or "USO" in s or "UCO" in s]
        assert len(oil) >= 1, "Oil hedge strategy not found"

    def test_gold_hedge_present(self):
        strategies = [s["strategy"] for s in HEDGING_STRATEGIES]
        gold = [s for s in strategies if "금" in s or "GLD" in s]
        assert len(gold) >= 1, "Gold hedge strategy not found"

    def test_defense_hedge_present(self):
        strategies = [s["strategy"] for s in HEDGING_STRATEGIES]
        defense = [s for s in strategies if "방산" in s or "ITA" in s]
        assert len(defense) >= 1, "Defense ETF hedge not found"

    def test_cash_strategy_present(self):
        strategies = [s["strategy"] for s in HEDGING_STRATEGIES]
        cash = [s for s in strategies if "현금" in s]
        assert len(cash) >= 1, "Cash allocation strategy not found"

    def test_vix_hedge_present(self):
        strategies = [s["strategy"] for s in HEDGING_STRATEGIES]
        vix = [s for s in strategies if "VIX" in s or "UVXY" in s]
        assert len(vix) >= 1, "VIX hedge strategy not found"

    def test_no_duplicate_strategies(self):
        strategies = [s["strategy"] for s in HEDGING_STRATEGIES]
        assert len(strategies) == len(set(strategies)), "Duplicate strategies found"


# ── Cross-Data Consistency Tests ──


class TestDataConsistency:
    """Cross-cutting data consistency validations."""

    def test_sector_impact_ticker_types(self):
        """All tickers in sector impact should be strings."""
        for entry in SECTOR_IMPACT:
            for ticker in entry["tickers"]:
                assert isinstance(ticker, str), (
                    f"Non-string ticker in {entry['sector']}: {ticker}"
                )

    def test_sector_impact_tickers_non_empty_strings(self):
        """No empty-string tickers in sector impact (empty list is allowed)."""
        for entry in SECTOR_IMPACT:
            for ticker in entry["tickers"]:
                assert ticker.strip(), (
                    f"Empty ticker string in {entry['sector']}"
                )

    def test_timeline_all_events_in_2026(self):
        """All timeline events should be in 2026."""
        for entry in IRAN_US_TIMELINE:
            assert entry["date"].startswith("2026-"), (
                f"Event not in 2026: {entry['date']}"
            )

    def test_timeline_spans_feb_to_march(self):
        """Timeline should cover February and March 2026."""
        months = {datetime.strptime(e["date"], "%Y-%m-%d").month for e in IRAN_US_TIMELINE}
        assert 2 in months, "No February events in timeline"
        assert 3 in months, "No March events in timeline"

    def test_market_impact_all_values_are_dicts(self):
        for key, val in MARKET_IMPACT.items():
            assert isinstance(val, dict), f"Market impact '{key}' is not a dict"

    def test_all_static_data_are_correct_types(self):
        """Verify top-level types of all static data structures."""
        assert isinstance(IRAN_US_TIMELINE, list)
        assert isinstance(MARKET_IMPACT, dict)
        assert isinstance(SECTOR_IMPACT, list)
        assert isinstance(SEMICONDUCTOR_RISKS, list)
        assert isinstance(HISTORICAL_PRECEDENTS, list)
        assert isinstance(KEY_VARIABLES, list)
        assert isinstance(HEDGING_STRATEGIES, list)

    def test_all_timeline_entries_are_dicts(self):
        for i, entry in enumerate(IRAN_US_TIMELINE):
            assert isinstance(entry, dict), f"Timeline entry {i} is not a dict"

    def test_all_sector_entries_are_dicts(self):
        for i, entry in enumerate(SECTOR_IMPACT):
            assert isinstance(entry, dict), f"Sector entry {i} is not a dict"

    def test_all_risk_entries_are_dicts(self):
        for i, entry in enumerate(SEMICONDUCTOR_RISKS):
            assert isinstance(entry, dict), f"Risk entry {i} is not a dict"

    def test_all_precedent_entries_are_dicts(self):
        for i, entry in enumerate(HISTORICAL_PRECEDENTS):
            assert isinstance(entry, dict), f"Precedent entry {i} is not a dict"

    def test_all_variable_entries_are_dicts(self):
        for i, entry in enumerate(KEY_VARIABLES):
            assert isinstance(entry, dict), f"Variable entry {i} is not a dict"

    def test_all_strategy_entries_are_dicts(self):
        for i, entry in enumerate(HEDGING_STRATEGIES):
            assert isinstance(entry, dict), f"Strategy entry {i} is not a dict"


# ── API Endpoint Tests ──


class TestIranUsDashboardAPI:
    """Test the /geopolitical/iran-us endpoint via TestClient."""

    @pytest_asyncio.fixture(scope="class")
    async def geo_client(self, setup_db):
        """Create a test client that includes the geopolitical router."""
        import httpx
        from fastapi import FastAPI
        from app.routers.geopolitical import router as geo_router

        test_app = FastAPI()
        test_app.include_router(geo_router)

        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_endpoint_returns_200(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_has_event_name(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        assert "event_name" in data
        assert data["event_name"] == "2026 이란-미국 분쟁"

    @pytest.mark.asyncio
    async def test_response_has_status(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        assert data["status"] == "진행 중"

    @pytest.mark.asyncio
    async def test_response_has_start_date(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        assert data["start_date"] == "2026-02-28"

    @pytest.mark.asyncio
    async def test_response_has_days_elapsed(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        assert isinstance(data["days_elapsed"], int)

    @pytest.mark.asyncio
    async def test_response_timeline_matches_static(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        assert len(data["timeline"]) == len(IRAN_US_TIMELINE)

    @pytest.mark.asyncio
    async def test_response_has_all_sections(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        expected_keys = {
            "event_name", "status", "start_date", "days_elapsed",
            "timeline", "market_impact", "sector_impact",
            "semiconductor_risks", "historical_precedents",
            "key_variables", "hedging_strategies",
            "live_data", "macro_snapshot", "updated_at",
            "soxl_specific",
        }
        missing = expected_keys - set(data.keys())
        assert not missing, f"Response missing keys: {missing}"

    @pytest.mark.asyncio
    async def test_response_live_data_is_dict(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        assert isinstance(data["live_data"], dict)

    @pytest.mark.asyncio
    async def test_response_soxl_specific_keys(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        soxl = data["soxl_specific"]
        assert "impact_summary" in soxl
        assert "key_level" in soxl
        assert "recovery_condition" in soxl

    @pytest.mark.asyncio
    async def test_response_updated_at_is_iso(self, geo_client):
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        # Should parse without error
        datetime.fromisoformat(data["updated_at"])

    @pytest.mark.asyncio
    async def test_macro_snapshot_none_when_no_data(self, geo_client):
        """With empty DB, macro_snapshot should be None."""
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        assert data["macro_snapshot"] is None

    @pytest.mark.asyncio
    async def test_live_data_empty_when_no_prices(self, geo_client):
        """With empty DB, live_data should be empty dict."""
        resp = await geo_client.get("/geopolitical/iran-us")
        data = resp.json()
        assert data["live_data"] == {}
