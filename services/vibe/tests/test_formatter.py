"""Tests for app.notifier.formatter — Discord embed formatting."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.notifier.formatter import (
    build_dashboard_payloads,
    build_dashboard_payload,
    format_soxl_alert,
    _calc_embed_chars,
    _split_into_payloads,
    _signal_emoji,
    _score_emoji,
)


# ── Helper: Mock stage result ──

class MockResult:
    def __init__(self, data=None, status="success"):
        self.data = data or {}
        self.status = status


def _base_context(**overrides):
    """Minimal valid context for build_dashboard_payloads."""
    ctx = {
        "market": "KR",
        "run_id": "abcdef1234567890",
        "date": "2025-01-15",
        "elapsed": 42.5,
        "s6_signal_generation": MockResult(data={
            "per_symbol": {
                "005930": {"final_signal": "BUY", "raw_score": 35, "hard_limit_triggered": False,
                           "position_recommendation": {"recommended_amount": 1000000}},
                "035420": {"final_signal": "HOLD", "raw_score": 5, "hard_limit_triggered": False},
                "068270": {"final_signal": "SELL", "raw_score": -20, "hard_limit_triggered": False},
            },
        }),
        "s7_red_team": None,
        "s3_macro_analysis": MockResult(data={
            "raw_data": {"vix": 18.5, "usd_krw": 1350, "us_10y_yield": 4.25, "dxy_index": 104.2},
            "details": {"aggregate_score": 0.15},
        }),
        "symbol_names": {"005930": "삼성전자", "035420": "NAVER", "068270": "셀트리온"},
    }
    ctx.update(overrides)
    return ctx


# ── _signal_emoji ──


class TestSignalEmoji:
    def test_buy(self):
        assert _signal_emoji("BUY") == "\U0001f7e2"

    def test_sell(self):
        assert _signal_emoji("SELL") == "\U0001f534"

    def test_hold(self):
        assert _signal_emoji("HOLD") == "\U0001f7e1"

    def test_unknown(self):
        assert _signal_emoji("WAIT") == "\u26aa"


# ── _score_emoji ──


class TestScoreEmoji:
    def test_positive_high(self):
        assert _score_emoji(50) == "\U0001f7e2"

    def test_positive_low(self):
        assert _score_emoji(15) == "\U0001f7e1"

    def test_negative_mild(self):
        assert _score_emoji(-15) == "\U0001f7e0"

    def test_negative_severe(self):
        assert _score_emoji(-50) == "\U0001f534"

    def test_boundary_30(self):
        assert _score_emoji(30) == "\U0001f7e1"
        assert _score_emoji(31) == "\U0001f7e2"

    def test_boundary_0(self):
        # 0 is not > 0, but 0 > -30 → orange
        assert _score_emoji(0) == "\U0001f7e0"
        assert _score_emoji(0.1) == "\U0001f7e1"

    def test_boundary_neg30(self):
        # -30 is not > -30 → red
        assert _score_emoji(-30) == "\U0001f534"
        assert _score_emoji(-29.9) == "\U0001f7e0"


# ── _calc_embed_chars ──


class TestCalcEmbedChars:
    def test_empty_embed(self):
        assert _calc_embed_chars({}) == 0

    def test_title_only(self):
        assert _calc_embed_chars({"title": "Hello"}) == 5

    def test_full_embed(self):
        embed = {
            "title": "Title",
            "description": "Desc",
            "fields": [{"name": "F1", "value": "V1"}],
            "footer": {"text": "Footer"},
            "author": {"name": "Author"},
        }
        expected = len("Title") + len("Desc") + len("F1") + len("V1") + len("Footer") + len("Author")
        assert _calc_embed_chars(embed) == expected

    def test_multiple_fields(self):
        embed = {
            "fields": [
                {"name": "AA", "value": "BB"},
                {"name": "CC", "value": "DD"},
            ],
        }
        assert _calc_embed_chars(embed) == 8


# ── _split_into_payloads ──


class TestSplitIntoPayloads:
    def test_empty(self):
        assert _split_into_payloads([]) == []

    def test_single_small_embed(self):
        embeds = [{"title": "Test", "description": "Short"}]
        payloads = _split_into_payloads(embeds)
        assert len(payloads) == 1
        assert payloads[0]["username"] == "VIBE"
        assert len(payloads[0]["embeds"]) == 1

    def test_split_on_char_limit(self):
        # Create embeds that collectively exceed 5800 chars
        big_embed = {"description": "X" * 3000}
        payloads = _split_into_payloads([big_embed, big_embed, big_embed], max_chars=5800)
        assert len(payloads) >= 2

    def test_split_on_embed_count(self):
        embeds = [{"title": f"E{i}"} for i in range(15)]
        payloads = _split_into_payloads(embeds, max_embeds=10)
        assert len(payloads) == 2
        assert len(payloads[0]["embeds"]) == 10
        assert len(payloads[1]["embeds"]) == 5

    def test_all_payloads_have_username(self):
        embeds = [{"description": "X" * 3000} for _ in range(5)]
        payloads = _split_into_payloads(embeds, max_chars=5800)
        for p in payloads:
            assert p["username"] == "VIBE"


# ── build_dashboard_payloads ──


class TestBuildDashboardPayloads:
    def test_minimal_context(self):
        ctx = _base_context()
        payloads = build_dashboard_payloads(ctx)
        assert len(payloads) >= 1
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p["embeds"])
        # At least: overview + signals + footer
        assert len(all_embeds) >= 3

    def test_overview_embed(self):
        ctx = _base_context()
        payloads = build_dashboard_payloads(ctx)
        overview = payloads[0]["embeds"][0]
        assert "VIBE DAILY" in overview["title"]
        assert "KR" in overview["title"]
        assert "2025-01-15" in overview["description"]

    def test_signal_embed_counts(self):
        ctx = _base_context()
        payloads = build_dashboard_payloads(ctx)
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p["embeds"])
        signal_embed = all_embeds[1]
        assert signal_embed["title"] == "Investment Signals"
        assert "BUY" in signal_embed["description"]
        assert "SELL" in signal_embed["description"]
        assert "HOLD" in signal_embed["description"]

    def test_position_sizing_for_buy(self):
        ctx = _base_context()
        payloads = build_dashboard_payloads(ctx)
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p["embeds"])
        # Find position sizing embed
        sizing = [e for e in all_embeds if "Position Sizing" in e.get("title", "")]
        assert len(sizing) == 1
        assert "삼성전자" in sizing[0]["description"]

    def test_footer_embed(self):
        ctx = _base_context()
        payloads = build_dashboard_payloads(ctx)
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p["embeds"])
        footer = all_embeds[-1]
        assert "Symbols: 3" in footer["description"]
        assert "B/S/H: 1/1/1" in footer["description"]
        assert "42.5s" in footer["description"]

    def test_s7_preferred_over_s6(self):
        """When S7 red-team data exists, use it instead of S6."""
        ctx = _base_context(
            s7_red_team=MockResult(data={
                "per_symbol": {
                    "005930": {"final_signal": "HOLD", "raw_score": 10, "hard_limit_triggered": False,
                               "red_team_warning": "RSI too high"},
                },
            }),
        )
        payloads = build_dashboard_payloads(ctx)
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p["embeds"])
        # Footer should show 1 symbol (from S7, not S6)
        footer = all_embeds[-1]
        assert "Symbols: 1" in footer["description"]

    def test_missing_macro_data(self):
        ctx = _base_context(s3_macro_analysis=None)
        payloads = build_dashboard_payloads(ctx)
        assert len(payloads) >= 1  # Should not crash

    def test_missing_sentiment_data(self):
        ctx = _base_context()
        ctx["s3b_sentiment_analysis"] = None
        payloads = build_dashboard_payloads(ctx)
        assert len(payloads) >= 1

    def test_sentiment_data_present(self):
        ctx = _base_context()
        ctx["s3b_sentiment_analysis"] = MockResult(data={
            "sentiment_score": 25,
            "raw_data": {"fear_greed_index": 45, "vix_term_structure": "contango"},
        })
        payloads = build_dashboard_payloads(ctx)
        overview = payloads[0]["embeds"][0]
        assert "Sentiment" in overview["description"]

    def test_hard_limit_alert(self):
        ctx = _base_context()
        ctx["s6_signal_generation"] = MockResult(data={
            "per_symbol": {
                "005930": {"final_signal": "BUY", "raw_score": 35, "hard_limit_triggered": True,
                           "hard_limit_reason": "RSI > 65"},
            },
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p["embeds"])
        alert_embeds = [e for e in all_embeds if e.get("title") == "Alerts"]
        assert len(alert_embeds) == 1
        assert "RSI > 65" in alert_embeds[0]["description"]

    def test_event_warnings(self):
        ctx = _base_context()
        ctx["s6b_risk_sizing"] = MockResult(data={
            "global_events": ["FOMC meeting tomorrow"],
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p["embeds"])
        event_embeds = [e for e in all_embeds if e.get("title") == "Event Warnings"]
        assert len(event_embeds) == 1

    def test_s8_explanation_embed(self):
        ctx = _base_context()
        ctx["s8_explanation"] = MockResult(data={
            "per_symbol": {
                "005930": {"explanation_llm": "삼성전자 기술적 반등 기대", "final_signal": "BUY"},
            },
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p["embeds"])
        ai_embeds = [e for e in all_embeds if "\ubd84\uc11d" in e.get("title", "")]
        assert len(ai_embeds) == 1

    def test_empty_per_symbol(self):
        ctx = _base_context()
        ctx["s6_signal_generation"] = MockResult(data={"per_symbol": {}})
        payloads = build_dashboard_payloads(ctx)
        assert len(payloads) >= 1
        # Footer should show 0 symbols
        footer = payloads[-1]["embeds"][-1]
        assert "Symbols: 0" in footer["description"]


# ── build_dashboard_payload (legacy) ──


class TestBuildDashboardPayloadLegacy:
    def test_returns_single_dict(self):
        ctx = _base_context()
        result = build_dashboard_payload(ctx)
        assert isinstance(result, dict)
        assert result["username"] == "VIBE"
        assert isinstance(result["embeds"], list)

    def test_empty_payloads(self):
        """Edge case: if build_dashboard_payloads returned empty."""
        ctx = _base_context()
        ctx["s6_signal_generation"] = MockResult(data={"per_symbol": {}})
        result = build_dashboard_payload(ctx)
        assert result["username"] == "VIBE"
        assert isinstance(result["embeds"], list)

    def test_no_payloads_returns_empty_embeds(self, monkeypatch):
        """Line 350: defensive guard when build_dashboard_payloads returns []."""
        import app.notifier.formatter as fmt_mod
        monkeypatch.setattr(fmt_mod, "build_dashboard_payloads", lambda _ctx: [])
        ctx = _base_context()
        result = build_dashboard_payload(ctx)
        assert result == {"username": "VIBE", "embeds": []}

    def test_max_10_embeds(self):
        ctx = _base_context()
        result = build_dashboard_payload(ctx)
        assert len(result["embeds"]) <= 10


# ── Optional embeds: s9 portfolio scenarios, s3c news, event_warning ──


class TestOptionalEmbeds:
    def test_s9_held_scenarios_embed(self):
        """Lines 206-225: portfolio holdings embed appears when s9 has held_scenarios."""
        ctx = _base_context()
        ctx["s9_portfolio_scenarios"] = MockResult(data={
            "held_scenarios": {
                "005930": {
                    "name": "삼성전자", "pnl_pct": 5.2, "current_price": 75000,
                    "target_prices": {"stop_loss": 68000, "target_10pct": 82500},
                },
            },
            "entry_scenarios": {},
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = [e for p in payloads for e in p["embeds"]]
        held_embeds = [e for e in all_embeds if "\ubcf4\uc720 \uc885\ubaa9" in e.get("title", "")]
        assert len(held_embeds) == 1
        assert "삼성전자" in held_embeds[0]["description"]
        assert "+5.2%" in held_embeds[0]["description"]

    def test_s9_entry_scenarios_embed(self):
        """Lines 227-245: new entry opportunities embed."""
        ctx = _base_context()
        ctx["s9_portfolio_scenarios"] = MockResult(data={
            "held_scenarios": {},
            "entry_scenarios": {
                "035420": {
                    "name": "NAVER",
                    "target_prices": {"entry": 200000, "stop_loss": 185000, "target_10pct": 220000},
                },
            },
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = [e for p in payloads for e in p["embeds"]]
        entry_embeds = [e for e in all_embeds if "\uc2e0\uaddc \uc9c4\uc785" in e.get("title", "")]
        assert len(entry_embeds) == 1
        assert "NAVER" in entry_embeds[0]["description"]

    def test_s3c_news_embed(self):
        """Lines 250-266: news headlines embed for BUY/SELL symbols."""
        ctx = _base_context()
        ctx["s3c_news_analysis"] = MockResult(data={
            "per_symbol": {
                "005930": {
                    "news_score": 15,
                    "article_count": 2,
                    "headlines": [{"title": "Samsung posts record Q4 profits"}],
                },
            },
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = [e for p in payloads for e in p["embeds"]]
        news_embeds = [e for e in all_embeds if "\ub274\uc2a4" in e.get("title", "")]
        assert len(news_embeds) == 1
        assert "삼성전자" in news_embeds[0]["description"]
        assert "Samsung" in news_embeds[0]["description"]

    def test_event_warning_in_per_symbol(self):
        """Line 151: event_warning on a symbol produces Event Warnings embed."""
        ctx = _base_context()
        ctx["s6_signal_generation"] = MockResult(data={
            "per_symbol": {
                "005930": {
                    "final_signal": "BUY", "raw_score": 30,
                    "hard_limit_triggered": False,
                    "event_warning": "FOMC 회의 예정 (2025-01-29)",
                },
            },
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = [e for p in payloads for e in p["embeds"]]
        event_embeds = [e for e in all_embeds if e.get("title") == "Event Warnings"]
        assert len(event_embeds) == 1
        assert "삼성전자" in event_embeds[0]["description"]
        assert "FOMC" in event_embeds[0]["description"]

    def test_s9_held_negative_pnl_shows_red(self):
        """Held position with negative P&L shows red emoji."""
        ctx = _base_context()
        ctx["s9_portfolio_scenarios"] = MockResult(data={
            "held_scenarios": {
                "068270": {
                    "name": "셀트리온", "pnl_pct": -3.5, "current_price": 150000,
                    "target_prices": {"stop_loss": 140000, "target_10pct": 180000},
                },
            },
            "entry_scenarios": {},
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = [e for p in payloads for e in p["embeds"]]
        held_embeds = [e for e in all_embeds if "\ubcf4\uc720 \uc885\ubaa9" in e.get("title", "")]
        assert len(held_embeds) == 1
        assert "-3.5%" in held_embeds[0]["description"]


# ── Regression: missing final_signal key must not raise KeyError ──


class TestMissingFinalSignalRegression:
    """Verify the sig.get('final_signal') fix: signals without the key don't crash."""

    def test_no_final_signal_key_does_not_raise(self):
        """Signal dict missing 'final_signal' routes to HOLD safely, no KeyError."""
        ctx = _base_context()
        ctx["s6_signal_generation"] = MockResult(data={
            "per_symbol": {
                "005930": {
                    # Deliberately omit 'final_signal' — pre-fix this would KeyError
                    "raw_score": 10,
                    "hard_limit_triggered": False,
                },
            },
        })
        # Should not raise
        payloads = build_dashboard_payloads(ctx)
        assert len(payloads) >= 1

        # Signal without final_signal falls into else-branch (hold_symbols for display)
        # but footer HOLD count only matches explicit "HOLD" strings → 0/0/0
        all_embeds = [e for p in payloads for e in p["embeds"]]
        footer = all_embeds[-1]
        assert "B/S/H: 0/0/0" in footer["description"]

    def test_footer_counts_ignore_missing_final_signal(self):
        """Footer BUY/SELL/HOLD counts treat missing final_signal as non-match."""
        ctx = _base_context()
        ctx["s6_signal_generation"] = MockResult(data={
            "per_symbol": {
                "AAA": {"raw_score": 40},          # no final_signal
                "BBB": {"final_signal": "BUY", "raw_score": 30},
                "CCC": {"final_signal": "SELL", "raw_score": -10},
            },
        })
        payloads = build_dashboard_payloads(ctx)
        all_embeds = [e for p in payloads for e in p["embeds"]]
        footer_desc = all_embeds[-1]["description"]
        # AAA has no final_signal → not counted as BUY or SELL
        assert "B/S/H: 1/1/0" in footer_desc


# ════════════════════════════════════════════════════════════════
# format_soxl_alert
# ════════════════════════════════════════════════════════════════


class TestFormatSoxlAlert:
    def test_price_above_includes_trigger_and_deviation(self):
        result = format_soxl_alert(
            alert_type="price_above",
            threshold=25.0,
            triggered_price=26.5,
            triggered_at="2024-03-10T15:00:00",
        )
        assert result["symbol"] == "SOXL"
        assert result["alert_type"] == "price_above"
        assert result["triggered_price"] == 26.5
        assert result["threshold"] == 25.0
        assert result["deviation_pct"] == 6.0  # (26.5-25)/25*100
        assert "26.50" in result["message"]
        assert "25.00" in result["message"]
        assert "+6.00%" in result["message"]
        assert result["triggered_at"] == "2024-03-10T15:00:00"

    def test_price_below_includes_leverage_warning(self):
        result = format_soxl_alert(
            alert_type="price_below",
            threshold=20.0,
            triggered_price=18.5,
        )
        assert "레버리지" in result["leverage_warning"]
        assert "3x" in result["leverage_warning"] or "3배" in result["leverage_warning"]
        assert "가격 하향 이탈" in result["message"]
        assert result["deviation_pct"] == -7.5  # (18.5-20)/20*100

    def test_threshold_zero_no_division_error(self):
        result = format_soxl_alert(
            alert_type="change_pct",
            threshold=0,
            triggered_price=5.0,
        )
        assert result["deviation_pct"] is None
        assert result["triggered_price"] == 5.0
        assert "등락률 초과" in result["message"]
        # No crash, message still formed
        assert "SOXL" in result["message"]
