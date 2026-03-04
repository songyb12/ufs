"""Discord embed formatter for VIBE DAILY DASHBOARD."""

from datetime import datetime, timezone
from typing import Any


def build_dashboard_payload(context: dict[str, Any]) -> dict:
    """Build complete Discord webhook payload from pipeline context."""
    market = context["market"]
    run_id = context["run_id"][:8]
    signal_date = context["date"]
    elapsed = context.get("elapsed", 0)

    # Get final signals from S7 or S6
    s7 = context.get("s7_red_team")
    s6 = context.get("s6_signal_generation")
    source = s7 if s7 and s7.status == "success" else s6
    per_symbol = source.data.get("per_symbol", {}) if source else {}

    # Symbol -> Name mapping for display
    symbol_names = context.get("symbol_names", {})

    # Get macro data
    macro_result = context.get("s3_macro_analysis")
    macro_data = macro_result.data.get("raw_data", {}) if macro_result else {}
    macro_details = macro_result.data.get("details", {}) if macro_result else {}

    embeds = []

    # ── Embed 1: Market Overview ──
    overview_fields = []
    if macro_data.get("vix") is not None:
        overview_fields.append({
            "name": "VIX",
            "value": f"{macro_data['vix']:.1f}",
            "inline": True,
        })
    if macro_data.get("usd_krw") is not None:
        overview_fields.append({
            "name": "USD/KRW",
            "value": f"{macro_data['usd_krw']:.0f}",
            "inline": True,
        })
    if macro_data.get("us_10y_yield") is not None:
        overview_fields.append({
            "name": "US 10Y",
            "value": f"{macro_data['us_10y_yield']:.2f}%",
            "inline": True,
        })
    if macro_data.get("dxy_index") is not None:
        overview_fields.append({
            "name": "DXY",
            "value": f"{macro_data['dxy_index']:.1f}",
            "inline": True,
        })

    macro_score = macro_details.get("aggregate_score", 0)
    macro_emoji = _score_emoji(macro_score * 100)

    # Sentiment data (Phase D)
    sentiment_result = context.get("s3b_sentiment_analysis")
    sentiment_line = ""
    if sentiment_result and sentiment_result.status == "success":
        s_score = sentiment_result.data.get("sentiment_score", 0)
        s_emoji = _score_emoji(s_score)
        fg = sentiment_result.data.get("raw_data", {}).get("fear_greed_index")
        fg_str = f" | F&G: {fg}" if fg is not None else ""
        sentiment_line = f"\nSentiment: {s_emoji} **{s_score:+.0f}**{fg_str}"
        # Add VIX term structure to overview
        vix_struct = sentiment_result.data.get("raw_data", {}).get("vix_term_structure")
        if vix_struct:
            overview_fields.append({
                "name": "VIX Term",
                "value": vix_struct.capitalize(),
                "inline": True,
            })

    embeds.append({
        "title": f"VIBE DAILY DASHBOARD - {market}",
        "description": (
            f"Date: **{signal_date}** | Run: `{run_id}`\n"
            f"Macro Score: {macro_emoji} **{macro_score:+.2f}**"
            f"{sentiment_line}"
        ),
        "color": 0x03B2F8,
        "fields": overview_fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # ── Embed 2: Investment Signals ──
    signal_fields = []
    for symbol, sig in per_symbol.items():
        name = symbol_names.get(symbol, symbol)
        emoji = _signal_emoji(sig["final_signal"])
        hl_tag = " **[HL]**" if sig.get("hard_limit_triggered") else ""
        conf = sig.get("confidence", 1.0)

        # Build detail line with fund/weekly if available
        detail_parts = [
            f"RSI: {_fmt(sig.get('rsi_value'))}",
            f"Disp: {_fmt(sig.get('disparity_value'))}%",
        ]
        fund_score = sig.get("fundamental_score")
        if fund_score and fund_score != 0:
            detail_parts.append(f"Fund: {fund_score:+.0f}")
        wk_trend = sig.get("weekly_trend")
        if wk_trend and wk_trend != "neutral":
            tf_m = sig.get("timeframe_multiplier", 1.0)
            detail_parts.append(f"Wk: {wk_trend}(×{tf_m:.1f})")

        signal_fields.append({
            "name": f"{emoji} {name}{hl_tag}",
            "value": (
                f"**{sig['final_signal']}** (score: {sig['raw_score']:+.1f})\n"
                f"{' | '.join(detail_parts)}\n"
                f"Conf: {conf:.0%}"
            ),
            "inline": True,
        })

    if signal_fields:
        embeds.append({
            "title": "Investment Signals",
            "color": 0x03B2F8,
            "fields": signal_fields[:25],  # Discord limit
        })

    # ── Embed 2b: Position Sizing (from S6b) ──
    s6b = context.get("s6b_risk_sizing")
    s6b_data = s6b.data if s6b and s6b.status == "success" else {}
    sizing_fields = []
    for symbol, sig in per_symbol.items():
        rec = sig.get("position_recommendation")
        if rec and sig["final_signal"] == "BUY":
            name = symbol_names.get(symbol, symbol)
            amt = rec.get("recommended_amount", 0)
            pct = rec.get("recommended_pct", 0) * 100
            sizing_fields.append({
                "name": f"📊 {name}",
                "value": (
                    f"Size: **₩{amt:,.0f}**\n"
                    f"Weight: {pct:.1f}% | "
                    f"Sector: {rec.get('sector', 'N/A')}"
                ),
                "inline": True,
            })
    if sizing_fields:
        embeds.append({
            "title": "Position Sizing",
            "color": 0x00CC88,
            "fields": sizing_fields[:25],
        })

    # ── Embed 2c: Event Warnings ──
    event_warnings = []
    for symbol, sig in per_symbol.items():
        ew = sig.get("event_warning")
        if ew:
            name = symbol_names.get(symbol, symbol)
            event_warnings.append(f"⚠️ **{name}**: {ew}")
    global_events = s6b_data.get("global_events", []) if s6b_data else []
    if global_events:
        for ev in global_events[:5]:
            event_warnings.insert(0, f"🗓️ {ev}")
    if event_warnings:
        embeds.append({
            "title": "Event Calendar Warnings",
            "description": "\n".join(event_warnings[:15]),
            "color": 0xFFAA00,
        })

    # ── Embed 2d: Correlation Warnings ──
    corr_warnings = []
    for symbol, sig in per_symbol.items():
        cw = sig.get("correlation_warning")
        if cw:
            corr_warnings.append(f"🔗 {cw}")
    if corr_warnings:
        embeds.append({
            "title": "Correlation Alerts",
            "description": "\n".join(set(corr_warnings[:10])),
            "color": 0xFF6600,
        })

    # ── Embed 3: Hard Limit Alerts ──
    hl_alerts = [
        (sym, sig) for sym, sig in per_symbol.items()
        if sig.get("hard_limit_triggered")
    ]
    if hl_alerts:
        hl_lines = [
            f"**{symbol_names.get(sym, sym)}**: {sig.get('hard_limit_reason', 'N/A')}"
            for sym, sig in hl_alerts
        ]
        embeds.append({
            "title": "Hard Limit Alerts",
            "description": "\n".join(hl_lines),
            "color": 0xFF0000,
        })

    # ── Embed 4: Red-Team Warnings ──
    rt_warnings = [
        (sym, sig) for sym, sig in per_symbol.items()
        if sig.get("red_team_warning")
    ]
    if rt_warnings:
        rt_lines = [
            f"**{symbol_names.get(sym, sym)}**: {sig['red_team_warning']}"
            for sym, sig in rt_warnings
        ]
        embeds.append({
            "title": "Red-Team Warnings",
            "description": "\n".join(rt_lines[:10]),
            "color": 0xFF6600,
        })

    # ── Embed: AI Signal Analysis (Korean) ──
    s8 = context.get("s8_explanation")
    if s8 and s8.status == "success":
        s8_per_symbol = s8.data.get("per_symbol", {})
        explain_lines = []
        for symbol, exp_data in s8_per_symbol.items():
            # Prefer LLM explanation, fall back to rule-based
            text = exp_data.get("explanation_llm") or exp_data.get("explanation_rule", "")
            if text:
                emoji = _signal_emoji(exp_data.get("final_signal", "HOLD"))
                explain_lines.append(f"{emoji} {text}")

        if explain_lines:
            embeds.append({
                "title": "\U0001f4dd AI \ubd84\uc11d \uc694\uc57d",
                "description": "\n\n".join(explain_lines)[:4096],
                "color": 0x5865F2,
            })

    # ── Embed: Portfolio Holdings Status ──
    s9 = context.get("s9_portfolio_scenarios")
    if s9 and s9.status == "success":
        held = s9.data.get("held_scenarios", {})
        if held:
            held_fields = []
            for symbol, scenario in held.items():
                name = scenario.get("name", symbol_names.get(symbol, symbol))
                pnl = scenario.get("pnl_pct", 0)
                pnl_emoji = "\U0001f7e2" if pnl > 0 else "\U0001f534"
                text = scenario.get("scenario_llm") or scenario.get("scenario_rule", "")
                targets = scenario.get("target_prices", {})
                held_fields.append({
                    "name": f"{pnl_emoji} {name} ({pnl:+.1f}%)",
                    "value": (
                        f"\u2193\u00a0\u00a0\u2193 \u00a0\u00a0\u2193\n"
                        f"\u25b6 \u2193\u00a0\u00a0{text[:180]}\n"
                        f"SL: \u20a9{targets.get('stop_loss', 0):,.0f} | "
                        f"TP: \u20a9{targets.get('target_10pct', 0):,.0f}"
                    ),
                    "inline": True,
                })
            embeds.append({
                "title": "\U0001f4bc \ubcf4\uc720 \uc885\ubaa9 \ud604\ud669",
                "color": 0x9B59B6,
                "fields": held_fields[:25],
            })

        # ── Embed: New Entry Opportunities ──
        entry = s9.data.get("entry_scenarios", {})
        if entry:
            entry_fields = []
            for symbol, scenario in entry.items():
                name = scenario.get("name", symbol_names.get(symbol, symbol))
                text = scenario.get("scenario_llm") or scenario.get("scenario_rule", "")
                entry_fields.append({
                    "name": f"\U0001f7e2 {name} (NEW BUY)",
                    "value": text[:200],
                    "inline": True,
                })
            embeds.append({
                "title": "\U0001f195 \uc2e0\uaddc \uc9c4\uc785 \uae30\ud68c",
                "color": 0x2ECC71,
                "fields": entry_fields[:25],
            })

    # ── Embed 5: Footer ──
    buy_count = sum(1 for s in per_symbol.values() if s["final_signal"] == "BUY")
    sell_count = sum(1 for s in per_symbol.values() if s["final_signal"] == "SELL")
    hold_count = sum(1 for s in per_symbol.values() if s["final_signal"] == "HOLD")

    embeds.append({
        "fields": [
            {"name": "Symbols", "value": str(len(per_symbol)), "inline": True},
            {"name": "BUY/SELL/HOLD", "value": f"{buy_count}/{sell_count}/{hold_count}", "inline": True},
            {"name": "Run Time", "value": f"{elapsed:.1f}s", "inline": True},
        ],
        "color": 0x888888,
        "footer": {"text": "VIBE v0.1.0 | UFS Master Core Ecosystem"},
    })

    return {
        "username": "VIBE",
        "embeds": embeds[:10],  # Discord limit: 10 embeds per message
    }


def _signal_emoji(signal: str) -> str:
    return {"BUY": "\U0001f7e2", "SELL": "\U0001f534", "HOLD": "\U0001f7e1"}.get(signal, "\u26aa")


def _score_emoji(score: float) -> str:
    if score > 30:
        return "\U0001f7e2"
    elif score > 0:
        return "\U0001f7e1"
    elif score > -30:
        return "\U0001f7e0"
    else:
        return "\U0001f534"


def _fmt(val: float | None) -> str:
    return f"{val:.1f}" if val is not None else "N/A"
