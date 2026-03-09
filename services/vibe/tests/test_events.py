"""Tests for app.risk.events — event calendar and signal suppression."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.risk.events import EventCalendar, FOMC_DATES, KR_HOLIDAYS


# ── should_suppress_signal (pure function) ──


class TestShouldSuppressSignal:
    def setup_method(self):
        self.cal = EventCalendar()

    def test_no_events(self):
        suppress, reason = self.cal.should_suppress_signal([])
        assert suppress is False
        assert reason == ""

    def test_high_impact_suppresses(self):
        events = [{"description": "FOMC Meeting Day 2 / Decision", "impact_level": "high"}]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is True
        assert "FOMC" in reason

    def test_medium_impact_does_not_suppress(self):
        events = [{"description": "KR Holiday", "impact_level": "medium"}]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is False
        assert reason == ""

    def test_low_impact_does_not_suppress(self):
        events = [{"description": "Minor Event", "impact_level": "low"}]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is False

    def test_missing_impact_level_does_not_suppress(self):
        events = [{"description": "No level field"}]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is False

    def test_none_impact_level_does_not_suppress(self):
        events = [{"description": "None level", "impact_level": None}]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is False

    def test_mixed_impact_levels(self):
        events = [
            {"description": "Options Expiry", "impact_level": "medium"},
            {"description": "FOMC Meeting", "impact_level": "high"},
        ]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is True

    def test_multiple_high_impact_all_in_reason(self):
        events = [
            {"description": "FOMC Meeting Day 1", "impact_level": "high"},
            {"description": "Emergency Fed Rate Cut", "impact_level": "high"},
        ]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is True
        assert "FOMC" in reason
        assert "Emergency" in reason

    def test_reason_truncates_long_descriptions(self):
        """Descriptions truncated to 40 chars in reason string."""
        long_desc = "A" * 100
        events = [{"description": long_desc, "impact_level": "high"}]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is True
        # The description in reason should be at most 40 chars
        assert long_desc not in reason  # Full 100-char string not present
        assert "A" * 40 in reason

    def test_reason_limits_to_3_events(self):
        """At most 3 high-impact events listed in reason."""
        events = [
            {"description": f"Event_{i}", "impact_level": "high"}
            for i in range(5)
        ]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is True
        assert "Event_0" in reason
        assert "Event_1" in reason
        assert "Event_2" in reason
        assert "Event_3" not in reason
        assert "Event_4" not in reason

    def test_reason_prefix(self):
        events = [{"description": "FOMC", "impact_level": "high"}]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert reason.startswith("High-impact event D-3:")

    def test_only_medium_events_many(self):
        """Many medium events still do not suppress."""
        events = [
            {"description": f"Holiday {i}", "impact_level": "medium"}
            for i in range(10)
        ]
        suppress, reason = self.cal.should_suppress_signal(events)
        assert suppress is False
        assert reason == ""


# ── FOMC_DATES data validation ──


class TestFOMCDates:
    def test_2025_has_8_meetings(self):
        assert len(FOMC_DATES[2025]) == 8

    def test_2026_has_8_meetings(self):
        assert len(FOMC_DATES[2026]) == 8

    def test_each_meeting_has_two_consecutive_days(self):
        for year in (2025, 2026):
            for day1, day2 in FOMC_DATES[year]:
                d1 = datetime.strptime(day1, "%Y-%m-%d")
                d2 = datetime.strptime(day2, "%Y-%m-%d")
                assert (d2 - d1).days == 1, f"FOMC {day1}-{day2} not consecutive"

    def test_all_fomc_dates_are_weekdays(self):
        for year in (2025, 2026):
            for day1, day2 in FOMC_DATES[year]:
                d1 = datetime.strptime(day1, "%Y-%m-%d")
                d2 = datetime.strptime(day2, "%Y-%m-%d")
                assert d1.weekday() < 5, f"{day1} is a weekend"
                assert d2.weekday() < 5, f"{day2} is a weekend"

    def test_fomc_dates_are_in_correct_year(self):
        for year in (2025, 2026):
            for day1, day2 in FOMC_DATES[year]:
                d1 = datetime.strptime(day1, "%Y-%m-%d")
                d2 = datetime.strptime(day2, "%Y-%m-%d")
                assert d1.year == year
                assert d2.year == year

    def test_fomc_dates_are_chronologically_ordered(self):
        for year in (2025, 2026):
            dates = [datetime.strptime(d1, "%Y-%m-%d") for d1, _ in FOMC_DATES[year]]
            for i in range(len(dates) - 1):
                assert dates[i] < dates[i + 1], (
                    f"FOMC dates out of order: {dates[i]} >= {dates[i+1]}"
                )

    def test_fomc_spread_across_year(self):
        """Meetings should span most of the year (at least 6 different months)."""
        for year in (2025, 2026):
            months = {datetime.strptime(d1, "%Y-%m-%d").month for d1, _ in FOMC_DATES[year]}
            assert len(months) >= 6


# ── KR_HOLIDAYS data validation ──


class TestKRHolidays:
    def test_2025_has_at_least_10_holidays(self):
        assert len(KR_HOLIDAYS[2025]) >= 10

    def test_2026_has_at_least_10_holidays(self):
        assert len(KR_HOLIDAYS[2026]) >= 10

    def test_dates_are_valid_and_in_correct_year(self):
        for year in (2025, 2026):
            for date_str, name in KR_HOLIDAYS[year]:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                assert dt.year == year, f"{date_str} wrong year"

    def test_holiday_names_not_empty(self):
        for year in (2025, 2026):
            for _, name in KR_HOLIDAYS[year]:
                assert len(name) > 0

    def test_new_years_day_present(self):
        for year in (2025, 2026):
            dates = [d for d, _ in KR_HOLIDAYS[year]]
            assert f"{year}-01-01" in dates

    def test_christmas_present(self):
        for year in (2025, 2026):
            dates = [d for d, _ in KR_HOLIDAYS[year]]
            assert f"{year}-12-25" in dates

    def test_independence_movement_day_present(self):
        for year in (2025, 2026):
            dates = [d for d, _ in KR_HOLIDAYS[year]]
            assert f"{year}-03-01" in dates

    def test_liberation_day_present(self):
        for year in (2025, 2026):
            dates = [d for d, _ in KR_HOLIDAYS[year]]
            assert f"{year}-08-15" in dates

    def test_national_foundation_day_present(self):
        for year in (2025, 2026):
            dates = [d for d, _ in KR_HOLIDAYS[year]]
            assert f"{year}-10-03" in dates


# ── Options expiry date calculation (3rd Friday logic) ──


class TestOptionsExpiryCalculation:
    """Test the 3rd Friday calculation logic extracted from seed_static_events."""

    @staticmethod
    def _compute_third_friday(year, month):
        """Replicate the 3rd Friday logic from EventCalendar.seed_static_events."""
        dt = datetime(year, month, 1)
        days_until_friday = (4 - dt.weekday()) % 7
        first_friday = dt + timedelta(days=days_until_friday)
        third_friday = first_friday + timedelta(weeks=2)
        return third_friday

    def test_jan_2025(self):
        # January 2025: 1st is Wednesday, 1st Friday=Jan 3, 3rd Friday=Jan 17
        tf = self._compute_third_friday(2025, 1)
        assert tf.day == 17
        assert tf.weekday() == 4  # Friday

    def test_feb_2025(self):
        # February 2025: 1st is Saturday, 1st Friday=Feb 7, 3rd Friday=Feb 21
        tf = self._compute_third_friday(2025, 2)
        assert tf.weekday() == 4
        assert tf.month == 2
        assert tf.day == 21

    def test_aug_2025_month_starting_on_friday(self):
        # August 2025 starts on Friday
        assert datetime(2025, 8, 1).weekday() == 4
        tf = self._compute_third_friday(2025, 8)
        assert tf.day == 15
        assert tf.weekday() == 4

    def test_all_months_produce_friday_2025(self):
        for month in range(1, 13):
            tf = self._compute_third_friday(2025, month)
            assert tf.weekday() == 4, f"2025 month {month} not Friday"
            assert tf.month == month, f"2025 month {month} spilled to next month"

    def test_all_months_produce_friday_2026(self):
        for month in range(1, 13):
            tf = self._compute_third_friday(2026, month)
            assert tf.weekday() == 4, f"2026 month {month} not Friday"
            assert tf.month == month, f"2026 month {month} spilled to next month"

    def test_third_friday_is_between_15_and_21(self):
        """3rd Friday is always between day 15 and day 21 inclusive."""
        for year in (2025, 2026):
            for month in range(1, 13):
                tf = self._compute_third_friday(year, month)
                assert 15 <= tf.day <= 21, (
                    f"{year}-{month}: 3rd Friday on day {tf.day}, expected 15-21"
                )

    def test_month_starting_on_saturday(self):
        # March 2025 starts on Saturday
        assert datetime(2025, 3, 1).weekday() == 5
        tf = self._compute_third_friday(2025, 3)
        # 1st Friday = Mar 7, 3rd Friday = Mar 21
        assert tf.day == 21
        assert tf.weekday() == 4

    def test_month_starting_on_sunday(self):
        # June 2025 starts on Sunday
        assert datetime(2025, 6, 1).weekday() == 6
        tf = self._compute_third_friday(2025, 6)
        # 1st Friday = Jun 6, 3rd Friday = Jun 20
        assert tf.day == 20
        assert tf.weekday() == 4


# ── seed_static_events event generation (structure, not DB) ──


class TestSeedStaticEventsStructure:
    """Test the event dict structure that seed_static_events produces.

    We replicate the generation logic here to test without DB access.
    """

    @staticmethod
    def _generate_events(year):
        """Replicate event generation without DB insertion."""
        events = []

        fomc = FOMC_DATES.get(year, [])
        for day1, day2 in fomc:
            events.append({
                "event_date": day1,
                "event_type": "fomc",
                "market": None,
                "symbol": None,
                "description": f"FOMC Meeting Day 1 ({day1})",
                "impact_level": "high",
            })
            events.append({
                "event_date": day2,
                "event_type": "fomc",
                "market": None,
                "symbol": None,
                "description": f"FOMC Meeting Day 2 / Decision ({day2})",
                "impact_level": "high",
            })

        holidays = KR_HOLIDAYS.get(year, [])
        for date_str, name in holidays:
            events.append({
                "event_date": date_str,
                "event_type": "kr_holiday",
                "market": "KR",
                "symbol": None,
                "description": name,
                "impact_level": "medium",
            })

        for month in range(1, 13):
            dt = datetime(year, month, 1)
            days_until_friday = (4 - dt.weekday()) % 7
            first_friday = dt + timedelta(days=days_until_friday)
            third_friday = first_friday + timedelta(weeks=2)
            events.append({
                "event_date": third_friday.strftime("%Y-%m-%d"),
                "event_type": "options_expiry",
                "market": "US",
                "symbol": None,
                "description": f"US Monthly Options Expiry ({third_friday.strftime('%b %Y')})",
                "impact_level": "medium",
            })

        return events

    def test_2025_event_count(self):
        events = self._generate_events(2025)
        fomc_count = 8 * 2  # 8 meetings * 2 days
        holiday_count = len(KR_HOLIDAYS[2025])
        expiry_count = 12  # 12 months
        assert len(events) == fomc_count + holiday_count + expiry_count

    def test_2026_event_count(self):
        events = self._generate_events(2026)
        fomc_count = 8 * 2
        holiday_count = len(KR_HOLIDAYS[2026])
        expiry_count = 12
        assert len(events) == fomc_count + holiday_count + expiry_count

    def test_fomc_events_are_high_impact(self):
        events = self._generate_events(2025)
        fomc_events = [e for e in events if e["event_type"] == "fomc"]
        assert len(fomc_events) == 16  # 8 meetings * 2 days
        for e in fomc_events:
            assert e["impact_level"] == "high"
            assert e["market"] is None
            assert e["symbol"] is None

    def test_holiday_events_are_medium_impact(self):
        events = self._generate_events(2025)
        holiday_events = [e for e in events if e["event_type"] == "kr_holiday"]
        for e in holiday_events:
            assert e["impact_level"] == "medium"
            assert e["market"] == "KR"

    def test_options_expiry_events(self):
        events = self._generate_events(2025)
        expiry_events = [e for e in events if e["event_type"] == "options_expiry"]
        assert len(expiry_events) == 12
        for e in expiry_events:
            assert e["impact_level"] == "medium"
            assert e["market"] == "US"

    def test_unknown_year_produces_only_expiry(self):
        """Year not in FOMC_DATES or KR_HOLIDAYS -> only options expiry events."""
        events = self._generate_events(2099)
        assert len(events) == 12
        assert all(e["event_type"] == "options_expiry" for e in events)

    def test_all_events_have_required_keys(self):
        events = self._generate_events(2025)
        required = {"event_date", "event_type", "market", "symbol", "description", "impact_level"}
        for e in events:
            assert set(e.keys()) == required, f"Missing keys in {e}"

    def test_event_dates_are_valid_iso_format(self):
        events = self._generate_events(2025)
        for e in events:
            dt = datetime.strptime(e["event_date"], "%Y-%m-%d")
            assert dt.year == 2025
