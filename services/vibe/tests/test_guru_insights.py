"""Tests for app.indicators.guru_insights — pure function tests.

Covers: _market_mood, _vix_level, all 8 guru view functions,
all 8 guru pick functions, _score_and_sort, analyze_all_gurus,
build_guru_llm_prompt, GURU_13F / GURUS data integrity.
Edge cases: empty/None inputs, boundary values, zero/negative scores.
"""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest

from app.indicators.guru_insights import (
    GURUS,
    GURU_13F,
    _VALUE_SECTORS,
    _GROWTH_SECTORS,
    _INNOVATION_SECTORS,
    _DEFENSIVE_SECTORS,
    _CYCLICAL_SECTORS,
    analyze_all_gurus,
    _market_mood,
    _vix_level,
    _buffett_view, _dalio_view, _lynch_view, _soros_view,
    _marks_view, _wood_view, _nps_view, _gpfg_view,
    _buffett_picks, _dalio_picks, _lynch_picks, _soros_picks,
    _marks_picks, _wood_picks, _nps_picks, _gpfg_picks,
    _score_and_sort,
    _default_view,
    _default_picks,
    build_guru_llm_prompt,
)


# ═══════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════

@pytest.fixture
def macro_extreme_fear():
    """Macro data: extreme fear (FG <= 15)."""
    return {
        "fear_greed_index": 10,
        "vix": 40,
        "us_10y_yield": 4.0,
        "us_2y_yield": 4.5,
        "dxy_index": 104,
        "usd_krw": 1380,
        "gold_price": 2500,
        "wti_crude": 80,
    }


@pytest.fixture
def macro_fear():
    """Macro data: fear regime (15 < FG <= 30)."""
    return {
        "fear_greed_index": 25,
        "vix": 28,
        "us_10y_yield": 4.0,
        "us_2y_yield": 3.8,
        "dxy_index": 104,
        "usd_krw": 1380,
        "gold_price": 2300,
        "wti_crude": 75,
    }


@pytest.fixture
def macro_greed():
    """Macro data: greed regime (65 <= FG < 80)."""
    return {
        "fear_greed_index": 70,
        "vix": 14,
        "us_10y_yield": 4.0,
        "us_2y_yield": 3.5,
        "dxy_index": 100,
        "usd_krw": 1280,
        "gold_price": 2100,
        "wti_crude": 72,
    }


@pytest.fixture
def macro_extreme_greed():
    """Macro data: extreme greed (FG >= 80)."""
    return {
        "fear_greed_index": 85,
        "vix": 12,
        "us_10y_yield": 4.0,
        "us_2y_yield": 3.5,
        "dxy_index": 98,
        "usd_krw": 1250,
        "gold_price": 2000,
        "wti_crude": 70,
    }


@pytest.fixture
def macro_neutral():
    """Macro data: neutral regime (30 < FG < 65)."""
    return {
        "fear_greed_index": 50,
        "vix": 18,
        "us_10y_yield": 3.5,
        "us_2y_yield": 3.2,
        "dxy_index": 101,
        "usd_krw": 1320,
        "gold_price": 2200,
        "wti_crude": 73,
    }


@pytest.fixture
def macro_empty():
    """Empty macro data — all defaults."""
    return {}


@pytest.fixture
def macro_alt_keys():
    """Macro data using alternate key names (fear_greed, us10y, dxy, gold, wti_oil)."""
    return {
        "fear_greed": 20,
        "vix": 32,
        "us10y": 4.2,
        "us02y": 4.5,
        "dxy": 108,
        "usd_krw": 1450,
        "gold": 2600,
        "wti_oil": 85,
        "put_call_ratio": 1.3,
    }


@pytest.fixture
def macro_high_dxy():
    """Macro with DXY > 107 for Soros FX play branch."""
    return {
        "fear_greed_index": 50,
        "vix": 18,
        "dxy_index": 110,
        "usd_krw": 1450,
    }


@pytest.fixture
def macro_soros_contrarian():
    """Macro triggering Soros contrarian long: VIX > 30 and FG < 20."""
    return {
        "fear_greed_index": 15,
        "vix": 35,
        "dxy_index": 102,
        "usd_krw": 1400,
    }


@pytest.fixture
def macro_dalio_tightening():
    """Macro for Dalio: inverted yield curve."""
    return {
        "fear_greed_index": 50,
        "vix": 20,
        "us_10y_yield": 3.5,
        "us_2y_yield": 4.0,
        "dxy_index": 100,
        "usd_krw": 1300,
        "gold_price": 2200,
    }


@pytest.fixture
def macro_dalio_high_dxy():
    """Macro for Dalio: DXY > 106."""
    return {
        "fear_greed_index": 50,
        "vix": 18,
        "us_10y_yield": 4.0,
        "us_2y_yield": 3.5,
        "dxy_index": 108,
        "usd_krw": 1400,
        "gold_price": 2200,
    }


@pytest.fixture
def macro_dalio_easing():
    """Macro for Dalio: low yields = easing cycle."""
    return {
        "fear_greed_index": 50,
        "vix": 15,
        "us_10y_yield": 2.0,
        "us_2y_yield": 1.8,
        "dxy_index": 98,
        "usd_krw": 1280,
        "gold_price": 2100,
    }


@pytest.fixture
def sample_signals():
    """Sample signals list for pick testing."""
    return [
        {"symbol": "005930", "name": "삼성전자", "market": "KR",
         "final_signal": "BUY", "raw_score": 20, "rsi_value": 30,
         "technical_score": 25, "macro_score": 15, "fund_flow_score": 1.0,
         "fundamental_score": 1.2, "sector": "반도체"},
        {"symbol": "AAPL", "name": "Apple", "market": "US",
         "final_signal": "BUY", "raw_score": 18, "rsi_value": 40,
         "technical_score": 22, "macro_score": 12, "fund_flow_score": 0.5,
         "fundamental_score": 1.5, "sector": "Consumer"},
        {"symbol": "000660", "name": "SK하이닉스", "market": "KR",
         "final_signal": "HOLD", "raw_score": 6, "rsi_value": 55,
         "technical_score": 12, "macro_score": 5, "fund_flow_score": 0.1,
         "fundamental_score": 0.8, "sector": "반도체"},
        {"symbol": "TSLA", "name": "Tesla", "market": "US",
         "final_signal": "SELL", "raw_score": -1.0, "rsi_value": 72,
         "technical_score": -0.5, "macro_score": -0.3, "fund_flow_score": 0.0,
         "fundamental_score": -0.2, "sector": "Auto"},
        {"symbol": "035420", "name": "NAVER", "market": "KR",
         "final_signal": "BUY", "raw_score": 10, "rsi_value": 38,
         "technical_score": 15, "macro_score": 8, "fund_flow_score": 0.3,
         "fundamental_score": 1.0, "sector": "인터넷"},
        {"symbol": "KO", "name": "Coca-Cola", "market": "US",
         "final_signal": "HOLD", "raw_score": 4, "rsi_value": 50,
         "technical_score": 5, "macro_score": 3, "fund_flow_score": 0.2,
         "fundamental_score": 1.1, "sector": "Consumer"},
    ]


@pytest.fixture
def value_sector_signals():
    """Signals from value sectors for Buffett pick testing."""
    return [
        {"symbol": "BAC", "name": "Bank of America", "market": "US",
         "final_signal": "BUY", "rsi_value": 28, "sector": "금융",
         "fundamental_score": 2.0, "raw_score": 10, "technical_score": 5,
         "macro_score": 3},
        {"symbol": "KO", "name": "Coca-Cola", "market": "US",
         "final_signal": "BUY", "rsi_value": 42, "sector": "소비재",
         "fundamental_score": 1.5, "raw_score": 8, "technical_score": 4,
         "macro_score": 2},
    ]


@pytest.fixture
def defensive_sector_signals():
    """Signals from defensive sectors."""
    return [
        {"symbol": "KT", "name": "KT", "market": "KR",
         "final_signal": "HOLD", "rsi_value": 45, "sector": "통신",
         "fundamental_score": 1.0, "raw_score": 5, "technical_score": 3,
         "macro_score": 2},
        {"symbol": "JNJ", "name": "J&J", "market": "US",
         "final_signal": "BUY", "rsi_value": 50, "sector": "Healthcare",
         "fundamental_score": 1.5, "raw_score": 7, "technical_score": 4,
         "macro_score": 3},
    ]


@pytest.fixture
def innovation_sector_signals():
    """Signals from innovation sectors for Wood pick testing."""
    return [
        {"symbol": "005930", "name": "삼성전자", "market": "KR",
         "final_signal": "BUY", "rsi_value": 40, "sector": "반도체",
         "fundamental_score": 1.2, "raw_score": 12, "technical_score": 15,
         "macro_score": 5},
        {"symbol": "373220", "name": "LG에너지솔루션", "market": "KR",
         "final_signal": "BUY", "rsi_value": 35, "sector": "배터리",
         "fundamental_score": 0.8, "raw_score": 9, "technical_score": 12,
         "macro_score": 4},
    ]


@pytest.fixture
def oversold_signals():
    """Signals with extreme oversold RSI for Marks contrarian testing."""
    return [
        {"symbol": "TEST1", "name": "Oversold A", "market": "KR",
         "final_signal": "SELL", "rsi_value": 20, "sector": "금융",
         "fundamental_score": 2.0, "raw_score": -5, "technical_score": -3,
         "macro_score": -2},
        {"symbol": "TEST2", "name": "Oversold B", "market": "US",
         "final_signal": "SELL", "rsi_value": 35, "sector": "Healthcare",
         "fundamental_score": 1.5, "raw_score": -2, "technical_score": -1,
         "macro_score": -1},
    ]


# ═══════════════════════════════════════════════
# _market_mood boundary tests
# ═══════════════════════════════════════════════

class TestMarketMood:
    """Test _market_mood classification with exact boundaries."""

    def test_extreme_fear_below_threshold(self):
        assert _market_mood({"fear_greed_index": 10}) == "extreme_fear"

    def test_extreme_fear_at_threshold(self):
        assert _market_mood({"fear_greed_index": 15}) == "extreme_fear"

    def test_fear_just_above_extreme(self):
        assert _market_mood({"fear_greed_index": 16}) == "fear"

    def test_fear_at_upper_boundary(self):
        assert _market_mood({"fear_greed_index": 30}) == "fear"

    def test_neutral_just_above_fear(self):
        assert _market_mood({"fear_greed_index": 31}) == "neutral"

    def test_neutral_mid_range(self):
        assert _market_mood({"fear_greed_index": 50}) == "neutral"

    def test_neutral_just_below_greed(self):
        assert _market_mood({"fear_greed_index": 64}) == "neutral"

    def test_greed_at_lower_boundary(self):
        assert _market_mood({"fear_greed_index": 65}) == "greed"

    def test_greed_mid_range(self):
        assert _market_mood({"fear_greed_index": 75}) == "greed"

    def test_greed_just_below_extreme(self):
        assert _market_mood({"fear_greed_index": 79}) == "greed"

    def test_extreme_greed_at_threshold(self):
        assert _market_mood({"fear_greed_index": 80}) == "extreme_greed"

    def test_extreme_greed_above_threshold(self):
        assert _market_mood({"fear_greed_index": 95}) == "extreme_greed"

    def test_empty_dict_defaults_neutral(self):
        """Empty dict -> fear_greed defaults to 50 -> neutral."""
        assert _market_mood({}) == "neutral"

    def test_none_value_defaults_neutral(self):
        """None value -> falls through to default 50 -> neutral."""
        assert _market_mood({"fear_greed_index": None}) == "neutral"

    def test_zero_value(self):
        """Zero is falsy, so default 50 kicks in -> neutral."""
        assert _market_mood({"fear_greed_index": 0}) == "neutral"

    def test_alternate_key_fear_greed(self):
        """Uses 'fear_greed' as fallback key."""
        assert _market_mood({"fear_greed": 10}) == "extreme_fear"

    def test_alternate_key_precedence(self):
        """'fear_greed_index' takes precedence over 'fear_greed'."""
        result = _market_mood({"fear_greed_index": 85, "fear_greed": 10})
        assert result == "extreme_greed"


# ═══════════════════════════════════════════════
# _vix_level boundary tests
# ═══════════════════════════════════════════════

class TestVixLevel:
    """Test _vix_level classification with exact boundaries."""

    def test_panic_high_vix(self):
        assert _vix_level({"vix": 50}) == "panic"

    def test_panic_at_threshold(self):
        assert _vix_level({"vix": 35}) == "panic"

    def test_elevated_just_below_panic(self):
        assert _vix_level({"vix": 34}) == "elevated"

    def test_elevated_at_lower_threshold(self):
        assert _vix_level({"vix": 25}) == "elevated"

    def test_normal_just_below_elevated(self):
        assert _vix_level({"vix": 24}) == "normal"

    def test_normal_mid_range(self):
        assert _vix_level({"vix": 18}) == "normal"

    def test_normal_just_above_complacent(self):
        assert _vix_level({"vix": 15}) == "normal"

    def test_complacent_at_threshold(self):
        assert _vix_level({"vix": 14}) == "complacent"

    def test_complacent_low_vix(self):
        assert _vix_level({"vix": 10}) == "complacent"

    def test_empty_dict_defaults_normal(self):
        """Empty dict -> vix defaults to 15 -> normal."""
        assert _vix_level({}) == "normal"

    def test_none_value_defaults_normal(self):
        assert _vix_level({"vix": None}) == "normal"

    def test_zero_value_defaults_normal(self):
        """Zero is falsy, default 15 kicks in -> normal."""
        assert _vix_level({"vix": 0}) == "normal"


# ═══════════════════════════════════════════════
# Guru View Functions — generic parametrized tests
# ═══════════════════════════════════════════════

class TestGuruViewsGeneric:
    """All 8 guru view functions: structural checks across all regimes."""

    REQUIRED_KEYS = {"stance", "stance_kr", "conviction", "summary_kr", "key_points_kr"}
    VIEW_FNS = [
        _buffett_view, _dalio_view, _lynch_view, _soros_view,
        _marks_view, _wood_view, _nps_view, _gpfg_view,
    ]

    @pytest.mark.parametrize("fn", VIEW_FNS)
    def test_returns_required_keys_neutral(self, fn, macro_neutral):
        result = fn(macro_neutral)
        assert self.REQUIRED_KEYS.issubset(result.keys())

    @pytest.mark.parametrize("fn", VIEW_FNS)
    def test_returns_required_keys_empty(self, fn, macro_empty):
        result = fn(macro_empty)
        assert self.REQUIRED_KEYS.issubset(result.keys())
        assert isinstance(result["conviction"], (int, float))

    @pytest.mark.parametrize("fn", VIEW_FNS)
    def test_conviction_in_valid_range(self, fn, macro_neutral):
        result = fn(macro_neutral)
        assert 0 <= result["conviction"] <= 100

    @pytest.mark.parametrize("fn", VIEW_FNS)
    def test_key_points_is_list(self, fn, macro_neutral):
        result = fn(macro_neutral)
        assert isinstance(result["key_points_kr"], list)

    @pytest.mark.parametrize("fn", VIEW_FNS)
    def test_summary_is_nonempty_string(self, fn, macro_neutral):
        result = fn(macro_neutral)
        assert isinstance(result["summary_kr"], str)
        assert len(result["summary_kr"]) > 0

    @pytest.mark.parametrize("fn", VIEW_FNS)
    def test_fear_vs_greed_differs(self, fn, macro_extreme_fear, macro_extreme_greed):
        fear = fn(macro_extreme_fear)
        greed = fn(macro_extreme_greed)
        assert fear["conviction"] != greed["conviction"] or fear["stance"] != greed["stance"]


# ═══════════════════════════════════════════════
# Guru View Functions — per-guru specific tests
# ═══════════════════════════════════════════════

class TestBuffettView:
    def test_fear_is_bullish(self, macro_extreme_fear):
        r = _buffett_view(macro_extreme_fear)
        assert r["stance"] == "bullish"
        assert r["conviction"] == 80

    def test_greed_is_cautious(self, macro_extreme_greed):
        r = _buffett_view(macro_extreme_greed)
        assert r["stance"] == "cautious"
        assert r["conviction"] == 30

    def test_neutral_is_neutral(self, macro_neutral):
        r = _buffett_view(macro_neutral)
        assert r["stance"] == "neutral"
        assert r["conviction"] == 55

    def test_fear_boundary_at_30(self):
        """FG=30 -> fear -> bullish."""
        r = _buffett_view({"fear_greed_index": 30})
        assert r["stance"] == "bullish"

    def test_greed_boundary_at_65(self):
        """FG=65 -> greed -> cautious."""
        r = _buffett_view({"fear_greed_index": 65})
        assert r["stance"] == "cautious"


class TestDalioView:
    def test_high_vix_risk_parity(self):
        """VIX > 28 triggers risk_parity stance."""
        r = _dalio_view({"vix": 30, "fear_greed_index": 50})
        assert r["stance"] == "risk_parity"
        assert r["conviction"] == 60

    def test_inverted_yield_curve(self, macro_dalio_tightening):
        """Negative spread -> late_cycle classification."""
        r = _dalio_view(macro_dalio_tightening)
        # VIX=20 < 28 so not risk_parity; DXY=100 < 106 so balanced
        assert r["stance"] == "balanced"
        # But the summary/points should reflect late_cycle
        assert any("경기 후반" in p for p in r["key_points_kr"])

    def test_high_dxy_cautious(self, macro_dalio_high_dxy):
        """DXY > 106 triggers cautious stance (when VIX is normal)."""
        r = _dalio_view(macro_dalio_high_dxy)
        assert r["stance"] == "cautious"
        assert r["conviction"] == 45

    def test_easing_cycle(self, macro_dalio_easing):
        """Low yields -> easing cycle in key_points."""
        r = _dalio_view(macro_dalio_easing)
        assert any("완화" in p for p in r["key_points_kr"])

    def test_tightening_cycle(self):
        """us10y > 4.5 and positive spread -> tightening."""
        r = _dalio_view({"us_10y_yield": 5.0, "us_2y_yield": 4.0, "vix": 15})
        # balanced stance (vix < 28, dxy default 100 < 106)
        assert r["stance"] == "balanced"

    def test_empty_macro_uses_defaults(self, macro_empty):
        r = _dalio_view(macro_empty)
        assert "stance" in r


class TestLynchView:
    def test_fear_is_bullish(self, macro_extreme_fear):
        r = _lynch_view(macro_extreme_fear)
        assert r["stance"] == "bullish"
        assert r["conviction"] == 75

    def test_greed_is_selective(self, macro_extreme_greed):
        r = _lynch_view(macro_extreme_greed)
        assert r["stance"] == "selective"
        assert r["conviction"] == 40

    def test_neutral_is_growth_hunting(self, macro_neutral):
        r = _lynch_view(macro_neutral)
        assert r["stance"] == "growth_hunting"
        assert r["conviction"] == 60


class TestSorosView:
    def test_contrarian_long(self, macro_soros_contrarian):
        """VIX > 30 and FG < 20 -> contrarian_long."""
        r = _soros_view(macro_soros_contrarian)
        assert r["stance"] == "contrarian_long"
        assert r["conviction"] == 70

    def test_fx_play_high_dxy(self, macro_high_dxy):
        """DXY > 107 triggers fx_play (when not in contrarian territory)."""
        r = _soros_view(macro_high_dxy)
        assert r["stance"] == "fx_play"
        assert r["conviction"] == 65

    def test_short_ready_high_fg(self):
        """FG > 75 -> short_ready."""
        r = _soros_view({"fear_greed_index": 80, "vix": 15, "dxy_index": 100, "usd_krw": 1300})
        assert r["stance"] == "short_ready"
        assert r["conviction"] == 55

    def test_trend_follow_default(self, macro_neutral):
        """No extreme triggers -> trend_follow."""
        r = _soros_view(macro_neutral)
        assert r["stance"] == "trend_follow"
        assert r["conviction"] == 50

    def test_usd_krw_in_key_points(self, macro_neutral):
        r = _soros_view(macro_neutral)
        assert any("USD/KRW" in p for p in r["key_points_kr"])

    def test_high_usd_krw_warning(self):
        """USD/KRW > 1400 triggers warning text."""
        r = _soros_view({"usd_krw": 1450, "vix": 18, "fear_greed_index": 50, "dxy_index": 100})
        assert any("원화 약세 주의" in p for p in r["key_points_kr"])


class TestMarksView:
    def test_extreme_fear_aggressive(self, macro_extreme_fear):
        r = _marks_view(macro_extreme_fear)
        assert r["stance"] == "aggressive_buy"
        assert r["conviction"] == 85
        assert r["cycle_position"] == "bottom"

    def test_fear_accumulate(self, macro_fear):
        r = _marks_view(macro_fear)
        assert r["stance"] == "accumulate"
        assert r["conviction"] == 70
        assert r["cycle_position"] == "lower_half"

    def test_extreme_greed_defensive(self, macro_extreme_greed):
        r = _marks_view(macro_extreme_greed)
        assert r["stance"] == "defensive"
        assert r["conviction"] == 25
        assert r["cycle_position"] == "top"

    def test_neutral_selective(self, macro_neutral):
        r = _marks_view(macro_neutral)
        assert r["stance"] == "selective"
        assert r["conviction"] == 50
        assert r["cycle_position"] == "mid_cycle"

    def test_has_cycle_position_fields(self, macro_neutral):
        r = _marks_view(macro_neutral)
        assert "cycle_position" in r
        assert "cycle_position_kr" in r


class TestWoodView:
    def test_fear_buy_innovation(self, macro_extreme_fear):
        r = _wood_view(macro_extreme_fear)
        assert r["stance"] == "buy_innovation"
        assert r["conviction"] == 85

    def test_greed_hold_conviction(self, macro_extreme_greed):
        r = _wood_view(macro_extreme_greed)
        assert r["stance"] == "hold_conviction"
        assert r["conviction"] == 65

    def test_neutral_accumulate(self, macro_neutral):
        r = _wood_view(macro_neutral)
        assert r["stance"] == "accumulate_disruptors"
        assert r["conviction"] == 70


class TestNpsView:
    def test_fear_rebalance_buy(self, macro_extreme_fear):
        r = _nps_view(macro_extreme_fear)
        assert r["stance"] == "rebalance_buy"
        assert r["conviction"] == 65

    def test_greed_rebalance_trim(self, macro_extreme_greed):
        r = _nps_view(macro_extreme_greed)
        assert r["stance"] == "rebalance_trim"
        assert r["conviction"] == 40

    def test_neutral_strategic_hold(self, macro_neutral):
        r = _nps_view(macro_neutral)
        assert r["stance"] == "strategic_hold"
        assert r["conviction"] == 55

    def test_high_usd_krw_hedging(self):
        """USD/KRW > 1400 triggers hedge wording."""
        r = _nps_view({"usd_krw": 1450, "fear_greed_index": 50})
        assert any("환헤지" in p for p in r["key_points_kr"])


class TestGpfgView:
    def test_fear_systematic_buy(self, macro_extreme_fear):
        r = _gpfg_view(macro_extreme_fear)
        assert r["stance"] == "systematic_buy"
        assert r["conviction"] == 60

    def test_neutral_index_plus(self, macro_neutral):
        r = _gpfg_view(macro_neutral)
        assert r["stance"] == "index_plus"
        assert r["conviction"] == 55

    def test_greed_index_plus(self, macro_extreme_greed):
        """Non-fear -> index_plus."""
        r = _gpfg_view(macro_extreme_greed)
        assert r["stance"] == "index_plus"


class TestDefaultView:
    def test_returns_neutral(self):
        r = _default_view({})
        assert r["stance"] == "neutral"
        assert r["conviction"] == 50
        assert r["key_points_kr"] == []


# ═══════════════════════════════════════════════
# _score_and_sort helper
# ═══════════════════════════════════════════════

class TestScoreAndSort:
    def _make_signal(self, symbol="TEST", score_val=10, **overrides):
        base = {
            "symbol": symbol, "name": f"Test-{symbol}", "market": "KR",
            "final_signal": "BUY", "rsi_value": 40, "_val": score_val,
        }
        base.update(overrides)
        return base

    def test_basic_sorting_descending(self):
        items = [self._make_signal("A", 10), self._make_signal("B", 30), self._make_signal("C", 20)]
        result = _score_and_sort(items, lambda x: (x["_val"], "reason"))
        assert result[0]["fit_score"] >= result[1]["fit_score"] >= result[2]["fit_score"]

    def test_filters_out_zero_and_negative(self):
        items = [
            self._make_signal("A", -5),
            self._make_signal("B", 0),
            self._make_signal("C", 10),
        ]
        result = _score_and_sort(items, lambda x: (x["_val"], "reason"))
        assert len(result) == 1
        assert result[0]["symbol"] == "C"

    def test_fit_score_capped_at_100(self):
        items = [self._make_signal("A", 200)]
        result = _score_and_sort(items, lambda x: (x["_val"], "reason"))
        assert result[0]["fit_score"] == 100

    def test_fit_score_rounded(self):
        items = [self._make_signal("A", 33.7)]
        result = _score_and_sort(items, lambda x: (x["_val"], "reason"))
        assert result[0]["fit_score"] == 34  # round(33.7) = 34

    def test_empty_input(self):
        result = _score_and_sort([], lambda x: (10, "reason"))
        assert result == []

    def test_output_includes_expected_fields(self):
        items = [self._make_signal("X", 50)]
        result = _score_and_sort(items, lambda x: (x["_val"], "match reason"))
        pick = result[0]
        assert pick["symbol"] == "X"
        assert pick["name"] == "Test-X"
        assert pick["market"] == "KR"
        assert pick["reason_kr"] == "match reason"
        assert pick["signal"] == "BUY"
        assert pick["rsi"] == 40
        assert pick["fit_score"] == 50

    def test_missing_name_falls_back_to_symbol(self):
        item = {"symbol": "NONAME", "market": "US", "final_signal": "HOLD", "rsi_value": 50, "_val": 20}
        result = _score_and_sort([item], lambda x: (x["_val"], "r"))
        assert result[0]["name"] == "NONAME"

    def test_all_negative_returns_empty(self):
        items = [self._make_signal("A", -1), self._make_signal("B", -10)]
        result = _score_and_sort(items, lambda x: (x["_val"], "r"))
        assert result == []


# ═══════════════════════════════════════════════
# Guru Pick Functions — generic parametrized tests
# ═══════════════════════════════════════════════

class TestGuruPicksGeneric:
    """All 8 guru pick functions: structural checks."""

    PICK_FNS = [
        _buffett_picks, _dalio_picks, _lynch_picks, _soros_picks,
        _marks_picks, _wood_picks, _nps_picks, _gpfg_picks,
    ]

    @pytest.mark.parametrize("fn", PICK_FNS)
    def test_returns_list(self, fn, sample_signals, macro_neutral):
        result = fn(sample_signals, macro_neutral)
        assert isinstance(result, list)

    @pytest.mark.parametrize("fn", PICK_FNS)
    def test_picks_have_required_fields(self, fn, sample_signals, macro_neutral):
        result = fn(sample_signals, macro_neutral)
        for pick in result:
            assert "symbol" in pick
            assert "name" in pick
            assert "fit_score" in pick
            assert "reason_kr" in pick
            assert "signal" in pick
            assert "rsi" in pick
            assert 0 < pick["fit_score"] <= 100

    @pytest.mark.parametrize("fn", PICK_FNS)
    def test_sorted_descending(self, fn, sample_signals, macro_neutral):
        result = fn(sample_signals, macro_neutral)
        if len(result) > 1:
            scores = [p["fit_score"] for p in result]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.parametrize("fn", PICK_FNS)
    def test_empty_signals_returns_empty(self, fn, macro_neutral):
        assert fn([], macro_neutral) == []

    @pytest.mark.parametrize("fn", PICK_FNS)
    def test_empty_macro_no_crash(self, fn, sample_signals, macro_empty):
        """Pick functions should not crash with empty macro."""
        result = fn(sample_signals, macro_empty)
        assert isinstance(result, list)


# ═══════════════════════════════════════════════
# Guru Pick Functions — per-guru specific tests
# ═══════════════════════════════════════════════

class TestBuffettPicks:
    def test_prefers_value_sectors(self, value_sector_signals, macro_neutral):
        result = _buffett_picks(value_sector_signals, macro_neutral)
        assert len(result) > 0
        # Value sector signals should score well
        for pick in result:
            assert pick["fit_score"] > 0

    def test_penalizes_volatile_tech(self, macro_neutral):
        """Buffett avoids high-volatility tech (인터넷, 배터리)."""
        signals = [
            {"symbol": "INT", "name": "Internet Co", "market": "KR",
             "final_signal": "BUY", "rsi_value": 30, "sector": "인터넷",
             "fundamental_score": 1.0},
            {"symbol": "BAT", "name": "Battery Co", "market": "KR",
             "final_signal": "BUY", "rsi_value": 30, "sector": "배터리",
             "fundamental_score": 1.0},
            {"symbol": "FIN", "name": "Finance Co", "market": "KR",
             "final_signal": "BUY", "rsi_value": 30, "sector": "금융",
             "fundamental_score": 1.0},
        ]
        result = _buffett_picks(signals, macro_neutral)
        scores_by_sym = {p["symbol"]: p["fit_score"] for p in result}
        # Finance should score higher than internet/battery
        if "FIN" in scores_by_sym and "INT" in scores_by_sym:
            assert scores_by_sym["FIN"] > scores_by_sym["INT"]

    def test_oversold_rsi_bonus(self, macro_neutral):
        """RSI < 35 gives +25 bonus."""
        signals = [
            {"symbol": "LOW", "name": "Low RSI", "market": "US",
             "final_signal": "HOLD", "rsi_value": 25, "sector": "금융",
             "fundamental_score": 0},
            {"symbol": "HIGH", "name": "High RSI", "market": "US",
             "final_signal": "HOLD", "rsi_value": 60, "sector": "금융",
             "fundamental_score": 0},
        ]
        result = _buffett_picks(signals, macro_neutral)
        scores = {p["symbol"]: p["fit_score"] for p in result}
        assert scores.get("LOW", 0) > scores.get("HIGH", 0)


class TestDalioPicks:
    def test_prefers_balanced_rsi(self, macro_neutral):
        """RSI between 30-70 gets bonus."""
        signals = [
            {"symbol": "BAL", "name": "Balanced", "market": "US",
             "final_signal": "HOLD", "rsi_value": 50, "sector": "통신",
             "fundamental_score": 1.0},
        ]
        result = _dalio_picks(signals, macro_neutral)
        assert len(result) > 0

    def test_etf_bonus(self, macro_neutral):
        """ETF sector gets extra points."""
        signals = [
            {"symbol": "SPY", "name": "SPY", "market": "US",
             "final_signal": "HOLD", "rsi_value": 50, "sector": "ETF",
             "fundamental_score": 0},
            {"symbol": "PLAIN", "name": "Plain", "market": "US",
             "final_signal": "HOLD", "rsi_value": 50, "sector": "기타",
             "fundamental_score": 0},
        ]
        result = _dalio_picks(signals, macro_neutral)
        scores = {p["symbol"]: p["fit_score"] for p in result}
        assert scores.get("SPY", 0) > scores.get("PLAIN", 0)


class TestLynchPicks:
    def test_growth_sector_bonus(self, macro_neutral):
        """Growth sector signals get higher scores."""
        signals = [
            {"symbol": "SEMI", "name": "Semi Co", "market": "KR",
             "final_signal": "BUY", "rsi_value": 50, "sector": "반도체",
             "technical_score": 25, "fundamental_score": 0},
        ]
        result = _lynch_picks(signals, macro_neutral)
        assert len(result) > 0
        assert result[0]["fit_score"] > 0

    def test_high_rsi_penalty(self, macro_neutral):
        """RSI > 70 gets -15 penalty."""
        signals = [
            {"symbol": "OB", "name": "Overbought", "market": "US",
             "final_signal": "HOLD", "rsi_value": 75, "sector": "기타",
             "technical_score": 0, "fundamental_score": 0},
        ]
        result = _lynch_picks(signals, macro_neutral)
        # Should have very low or zero score
        assert len(result) == 0 or result[0]["fit_score"] < 10


class TestSorosPicks:
    def test_strong_momentum_bonus(self, macro_neutral):
        """raw_score > 15 gives +25."""
        signals = [
            {"symbol": "MOM", "name": "Momentum", "market": "US",
             "final_signal": "BUY", "rsi_value": 50, "sector": "Tech",
             "raw_score": 20, "macro_score": 15},
        ]
        result = _soros_picks(signals, macro_neutral)
        assert len(result) > 0
        assert result[0]["fit_score"] >= 25

    def test_dollar_strength_us_bonus(self):
        """USD/KRW > 1400 and market=US gives bonus."""
        macro = {"usd_krw": 1450, "fear_greed_index": 50}
        signals = [
            {"symbol": "US1", "name": "US Stock", "market": "US",
             "final_signal": "BUY", "rsi_value": 50, "raw_score": 10, "macro_score": 5},
            {"symbol": "KR1", "name": "KR Stock", "market": "KR",
             "final_signal": "BUY", "rsi_value": 50, "raw_score": 10, "macro_score": 5},
        ]
        result = _soros_picks(signals, macro)
        scores = {p["symbol"]: p["fit_score"] for p in result}
        assert scores.get("US1", 0) > scores.get("KR1", 0)


class TestMarksPicks:
    def test_contrarian_in_fear(self, macro_extreme_fear, oversold_signals):
        """In extreme fear, Marks buys the most beaten-down."""
        result = _marks_picks(oversold_signals, macro_extreme_fear)
        assert len(result) > 0
        # Oversold + SELL signal = contrarian opportunity
        top = result[0]
        assert top["fit_score"] > 0
        assert "역발상" in top["reason_kr"] or "과매도" in top["reason_kr"]

    def test_sell_signal_bonus_in_fear(self, macro_extreme_fear):
        """SELL signal adds points in fear (contrarian)."""
        signals = [
            {"symbol": "SELL1", "name": "Sold Off", "market": "KR",
             "final_signal": "SELL", "rsi_value": 25, "sector": "금융",
             "fundamental_score": 1.0},
        ]
        result = _marks_picks(signals, macro_extreme_fear)
        assert len(result) > 0
        assert "군중의 매도" in result[0]["reason_kr"]

    def test_defensive_in_neutral(self, defensive_sector_signals, macro_neutral):
        """In neutral, Marks prefers defensive quality."""
        result = _marks_picks(defensive_sector_signals, macro_neutral)
        assert len(result) > 0
        for pick in result:
            assert "방어적" in pick["reason_kr"] or "펀더멘털" in pick["reason_kr"] or "저평가" in pick["reason_kr"]


class TestWoodPicks:
    def test_innovation_sector_bonus(self, innovation_sector_signals, macro_neutral):
        """Innovation sectors get high scores."""
        result = _wood_picks(innovation_sector_signals, macro_neutral)
        assert len(result) > 0
        for pick in result:
            assert pick["fit_score"] >= 25  # at least sector bonus

    def test_battery_double_bonus(self, macro_neutral):
        """Battery sector matches both INNOVATION_SECTORS and specific theme."""
        signals = [
            {"symbol": "BAT", "name": "Battery", "market": "KR",
             "final_signal": "BUY", "rsi_value": 40, "sector": "배터리",
             "technical_score": 15, "fundamental_score": 0},
        ]
        result = _wood_picks(signals, macro_neutral)
        assert len(result) == 1
        # Should get both innovation sector + core theme bonus
        assert result[0]["fit_score"] >= 50


class TestNpsPicks:
    def test_kr_market_bonus(self, macro_neutral):
        """KR market signals get bonus (NPS mandate)."""
        signals = [
            {"symbol": "KR1", "name": "KR Stock", "market": "KR",
             "final_signal": "HOLD", "rsi_value": 50, "sector": "반도체",
             "fundamental_score": 1.0},
            {"symbol": "US1", "name": "US Stock", "market": "US",
             "final_signal": "HOLD", "rsi_value": 50, "sector": "반도체",
             "fundamental_score": 1.0},
        ]
        result = _nps_picks(signals, macro_neutral)
        scores = {p["symbol"]: p["fit_score"] for p in result}
        assert scores.get("KR1", 0) > scores.get("US1", 0)

    def test_defensive_sector_bonus(self, defensive_sector_signals, macro_neutral):
        result = _nps_picks(defensive_sector_signals, macro_neutral)
        assert len(result) > 0


class TestGpfgPicks:
    def test_us_market_bonus(self, macro_neutral):
        """US market signals get bonus."""
        signals = [
            {"symbol": "US1", "name": "US Stock", "market": "US",
             "final_signal": "HOLD", "rsi_value": 50,
             "fundamental_score": 1.0},
            {"symbol": "KR1", "name": "KR Stock", "market": "KR",
             "final_signal": "HOLD", "rsi_value": 50,
             "fundamental_score": 1.0},
        ]
        result = _gpfg_picks(signals, macro_neutral)
        scores = {p["symbol"]: p["fit_score"] for p in result}
        assert scores.get("US1", 0) > scores.get("KR1", 0)

    def test_balanced_rsi_bonus(self, macro_neutral):
        """RSI 35-65 gets bonus."""
        signals = [
            {"symbol": "BAL", "name": "Balanced", "market": "US",
             "final_signal": "HOLD", "rsi_value": 50,
             "fundamental_score": 0},
            {"symbol": "EXT", "name": "Extreme", "market": "US",
             "final_signal": "HOLD", "rsi_value": 80,
             "fundamental_score": 0},
        ]
        result = _gpfg_picks(signals, macro_neutral)
        scores = {p["symbol"]: p["fit_score"] for p in result}
        assert scores.get("BAL", 0) > scores.get("EXT", 0)


class TestDefaultPicks:
    def test_returns_empty(self):
        assert _default_picks([], {}) == []
        assert _default_picks([{"symbol": "X"}], {"vix": 20}) == []


# ═══════════════════════════════════════════════
# analyze_all_gurus integration
# ═══════════════════════════════════════════════

class TestAnalyzeAllGurus:
    def test_returns_all_gurus(self, macro_neutral, sample_signals):
        result = analyze_all_gurus(macro_neutral, sample_signals)
        assert isinstance(result, list)
        assert len(result) == len(GURUS)

    def test_guru_ids_match(self, macro_neutral, sample_signals):
        result = analyze_all_gurus(macro_neutral, sample_signals)
        result_ids = {g["id"] for g in result}
        expected_ids = {g["id"] for g in GURUS}
        assert result_ids == expected_ids

    def test_each_has_market_view(self, macro_neutral, sample_signals):
        result = analyze_all_gurus(macro_neutral, sample_signals)
        for guru in result:
            assert "market_view" in guru
            assert "stance" in guru["market_view"]
            assert "conviction" in guru["market_view"]

    def test_each_has_picks(self, macro_neutral, sample_signals):
        result = analyze_all_gurus(macro_neutral, sample_signals)
        for guru in result:
            assert "picks" in guru
            assert isinstance(guru["picks"], list)

    def test_picks_capped_at_5(self, macro_neutral, sample_signals):
        """picks[:5] — never more than 5 picks."""
        result = analyze_all_gurus(macro_neutral, sample_signals)
        for guru in result:
            assert len(guru["picks"]) <= 5

    def test_portfolio_structure(self, macro_neutral, sample_signals):
        """Each guru result has portfolio dict with expected keys."""
        result = analyze_all_gurus(macro_neutral, sample_signals)
        for guru in result:
            p = guru["portfolio"]
            assert "source" in p
            assert "as_of" in p
            assert "total_value" in p
            assert "top_holdings" in p
            assert "watchlist_overlaps" in p
            assert isinstance(p["top_holdings"], list)
            assert isinstance(p["watchlist_overlaps"], list)

    def test_watchlist_overlaps_detected(self):
        """Signals with symbols matching 13F holdings should appear in overlaps."""
        signals = [
            {"symbol": "AAPL", "name": "Apple", "market": "US",
             "final_signal": "HOLD", "rsi_value": 50, "sector": "Consumer"},
        ]
        result = analyze_all_gurus({"fear_greed_index": 50}, signals)
        buffett = next(g for g in result if g["id"] == "buffett")
        assert "AAPL" in buffett["portfolio"]["watchlist_overlaps"]

    def test_no_overlaps_with_unknown_symbols(self):
        """Signals with unknown symbols should not appear in overlaps."""
        signals = [
            {"symbol": "ZZZZZZ", "name": "Unknown", "market": "US",
             "final_signal": "HOLD", "rsi_value": 50, "sector": "Other"},
        ]
        result = analyze_all_gurus({"fear_greed_index": 50}, signals)
        for guru in result:
            assert "ZZZZZZ" not in guru["portfolio"]["watchlist_overlaps"]

    def test_with_empty_signals(self, macro_neutral):
        result = analyze_all_gurus(macro_neutral, [])
        assert len(result) == len(GURUS)
        for guru in result:
            assert guru["picks"] == []

    def test_with_empty_macro(self, macro_empty, sample_signals):
        """Should not crash with empty macro."""
        result = analyze_all_gurus(macro_empty, sample_signals)
        assert len(result) == len(GURUS)

    def test_with_both_empty(self, macro_empty):
        result = analyze_all_gurus(macro_empty, [])
        assert len(result) == len(GURUS)

    def test_guru_profile_fields_preserved(self, macro_neutral, sample_signals):
        """Original guru profile fields (**guru) are spread into result."""
        result = analyze_all_gurus(macro_neutral, sample_signals)
        for guru in result:
            assert "name" in guru
            assert "name_kr" in guru
            assert "org" in guru
            assert "style_kr" in guru
            assert "philosophy_kr" in guru


# ═══════════════════════════════════════════════
# build_guru_llm_prompt
# ═══════════════════════════════════════════════

class TestBuildGuruLlmPrompt:
    def test_known_guru_contains_profile(self):
        prompt = build_guru_llm_prompt("buffett", {"vix": 20}, "summary")
        assert "Warren Buffett" in prompt
        assert "워런 버핏" in prompt
        assert "Berkshire Hathaway" in prompt

    def test_includes_signals_summary(self):
        prompt = build_guru_llm_prompt("dalio", {"vix": 20}, "BUY 3, SELL 1")
        assert "BUY 3, SELL 1" in prompt

    def test_includes_macro_data(self):
        macro = {"vix": 25, "fear_greed_index": 40, "usd_krw": 1350}
        prompt = build_guru_llm_prompt("soros", macro, "test")
        assert "25" in prompt  # VIX value
        assert "40" in prompt  # FG value

    def test_unknown_guru_returns_empty(self):
        prompt = build_guru_llm_prompt("nonexistent", {"vix": 20}, "test")
        assert prompt == ""

    def test_alternate_macro_keys(self, macro_alt_keys):
        """Uses alternate key names like fear_greed, us10y, dxy etc."""
        prompt = build_guru_llm_prompt("buffett", macro_alt_keys, "test")
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_all_guru_ids_produce_prompt(self):
        """Every guru id in GURUS should produce a non-empty prompt."""
        for guru in GURUS:
            prompt = build_guru_llm_prompt(guru["id"], {"vix": 20}, "test")
            assert isinstance(prompt, str)
            assert len(prompt) > 50, f"Guru {guru['id']} produced too-short prompt"

    def test_empty_macro(self):
        prompt = build_guru_llm_prompt("lynch", {}, "test")
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_empty_signals_summary(self):
        prompt = build_guru_llm_prompt("marks", {"vix": 20}, "")
        assert isinstance(prompt, str)
        assert len(prompt) > 50


# ═══════════════════════════════════════════════
# GURUS and GURU_13F data integrity
# ═══════════════════════════════════════════════

class TestGurusData:
    REQUIRED_GURU_KEYS = {"id", "name", "name_kr", "org", "style_kr", "avatar", "philosophy_kr"}

    def test_gurus_is_nonempty(self):
        assert len(GURUS) >= 8

    def test_each_guru_has_required_keys(self):
        for guru in GURUS:
            missing = self.REQUIRED_GURU_KEYS - guru.keys()
            assert not missing, f"Guru {guru.get('id', '?')} missing keys: {missing}"

    def test_guru_ids_unique(self):
        ids = [g["id"] for g in GURUS]
        assert len(ids) == len(set(ids)), "Duplicate guru IDs found"


class TestGuru13F:
    def test_fund_gurus_have_13f(self):
        """Gurus with actual fund portfolios should have 13F data."""
        fund_gurus = {"buffett", "dalio", "soros", "wood", "nps", "gpfg"}
        for gid in fund_gurus:
            assert gid in GURU_13F, f"{gid} missing from GURU_13F"

    def test_13f_structure(self):
        for guru_id, data in GURU_13F.items():
            assert isinstance(data, dict), f"{guru_id} should be a dict"
            assert "source" in data, f"{guru_id} missing 'source'"
            assert "as_of" in data, f"{guru_id} missing 'as_of'"
            holding_keys = [k for k in data if k.startswith("holdings")]
            assert len(holding_keys) >= 1, f"{guru_id} missing holdings"

    def test_holdings_have_symbol_and_weight(self):
        for guru_id, data in GURU_13F.items():
            for key in data:
                if key.startswith("holdings"):
                    for h in data[key]:
                        assert "symbol" in h, f"{guru_id}/{key}: missing 'symbol'"
                        assert "name" in h, f"{guru_id}/{key}: missing 'name'"
                        assert "weight" in h, f"{guru_id}/{key}: missing 'weight'"
                        assert isinstance(h["weight"], (int, float))
                        assert h["weight"] > 0

    def test_nps_has_kr_and_us_holdings(self):
        """NPS has both holdings_kr and holdings_us."""
        nps = GURU_13F["nps"]
        assert "holdings_kr" in nps
        assert "holdings_us" in nps
        assert len(nps["holdings_kr"]) > 0
        assert len(nps["holdings_us"]) > 0


# ═══════════════════════════════════════════════
# Sector classification data integrity
# ═══════════════════════════════════════════════

class TestSectorClassifications:
    def test_value_sectors_nonempty(self):
        assert len(_VALUE_SECTORS) > 0
        assert isinstance(_VALUE_SECTORS, set)

    def test_growth_sectors_nonempty(self):
        assert len(_GROWTH_SECTORS) > 0

    def test_innovation_sectors_nonempty(self):
        assert len(_INNOVATION_SECTORS) > 0

    def test_defensive_sectors_nonempty(self):
        assert len(_DEFENSIVE_SECTORS) > 0

    def test_cyclical_sectors_nonempty(self):
        assert len(_CYCLICAL_SECTORS) > 0

    def test_sets_are_distinct_types(self):
        """All sector constants should be sets."""
        for s in [_VALUE_SECTORS, _GROWTH_SECTORS, _INNOVATION_SECTORS,
                  _DEFENSIVE_SECTORS, _CYCLICAL_SECTORS]:
            assert isinstance(s, set)
