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

    embeds.append({
        "title": f"VIBE DAILY DASHBOARD - {market}",
        "description": (
            f"Date: **{signal_date}** | Run: `{run_id}`\n"
            f"Macro Score: {macro_emoji} **{macro_score:+.2f}**"
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

        signal_fields.append({
            "name": f"{emoji} {name}{hl_tag}",
            "value": (
                f"**{sig['final_signal']}** (score: {sig['raw_score']:+.1f})\n"
                f"RSI: {_fmt(sig.get('rsi_value'))} | "
                f"Disp: {_fmt(sig.get('disparity_value'))}%\n"
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
