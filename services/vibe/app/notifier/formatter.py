"""Discord embed formatter for VIBE DAILY DASHBOARD.

Discord limits:
- Max 10 embeds per message
- Max 6000 characters TOTAL across all embeds in one message
  (sum of title, description, field.name, field.value, footer.text, author.name)
- Individual field limits: title 256, description 4096, field.name 256, field.value 1024

Strategy: build embeds, then split into multiple messages to stay under 6000 chars.
"""

from datetime import datetime, timezone
from typing import Any

from app.config import settings


def build_dashboard_payloads(context: dict[str, Any]) -> list[dict]:
    """Build Discord webhook payloads from pipeline context.

    Returns a list of payloads (may be split into 2+ messages
    to respect Discord's 6000 char total limit).
    """
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
    macro_data = (macro_result.data or {}).get("raw_data", {}) if macro_result and macro_result.data else {}
    macro_details = (macro_result.data or {}).get("details", {}) if macro_result and macro_result.data else {}

    all_embeds = []

    # ── Embed 1: Market Overview ──
    overview_fields = []
    for key, label, fmt in [
        ("vix", "VIX", "{:.1f}"),
        ("usd_krw", "USD/KRW", "{:.0f}"),
        ("us_10y_yield", "US 10Y", "{:.2f}%"),
        ("dxy_index", "DXY", "{:.1f}"),
    ]:
        val = macro_data.get(key)
        if val is not None:
            overview_fields.append({
                "name": label,
                "value": fmt.format(val),
                "inline": True,
            })

    macro_score = macro_details.get("aggregate_score", 0)
    macro_emoji = _score_emoji(macro_score * 100)

    # Sentiment data (Phase D)
    sentiment_result = context.get("s3b_sentiment_analysis")
    sentiment_line = ""
    if sentiment_result and sentiment_result.status == "success" and sentiment_result.data:
        s_score = sentiment_result.data.get("sentiment_score", 0)
        s_emoji = _score_emoji(s_score)
        fg = sentiment_result.data.get("raw_data", {}).get("fear_greed_index")
        fg_str = f" | F&G: {fg}" if fg is not None else ""
        sentiment_line = f"\nSentiment: {s_emoji} **{s_score:+.0f}**{fg_str}"
        vix_struct = sentiment_result.data.get("raw_data", {}).get("vix_term_structure")
        if vix_struct:
            overview_fields.append({
                "name": "VIX Term",
                "value": vix_struct.capitalize(),
                "inline": True,
            })

    all_embeds.append({
        "title": f"VIBE DAILY - {market}",
        "description": (
            f"Date: **{signal_date}** | Run: `{run_id}`\n"
            f"Macro: {macro_emoji} **{macro_score:+.2f}**"
            f"{sentiment_line}"
        ),
        "color": 0x03B2F8,
        "fields": overview_fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # ── Embed 2: Investment Signals (compact) ──
    buy_symbols = []
    sell_symbols = []
    hold_symbols = []
    for symbol, sig in per_symbol.items():
        name = symbol_names.get(symbol, symbol)
        hl = " [HL]" if sig.get("hard_limit_triggered") else ""
        entry = (name, sig.get("raw_score", 0), hl)
        if sig.get("final_signal") == "BUY":
            buy_symbols.append(entry)
        elif sig["final_signal"] == "SELL":
            sell_symbols.append(entry)
        else:
            hold_symbols.append(entry)

    sig_lines = []
    if buy_symbols:
        items = " / ".join(f"**{n}**({s:+.0f}){h}" for n, s, h in buy_symbols)
        sig_lines.append(f"\U0001f7e2 BUY: {items}")
    if sell_symbols:
        items = " / ".join(f"**{n}**({s:+.0f}){h}" for n, s, h in sell_symbols)
        sig_lines.append(f"\U0001f534 SELL: {items}")
    if hold_symbols:
        items = " / ".join(f"{n}{h}" for n, _, h in hold_symbols)
        sig_lines.append(f"\U0001f7e1 HOLD: {items}")

    if sig_lines:
        all_embeds.append({
            "title": "Investment Signals",
            "description": "\n".join(sig_lines)[:4096],
            "color": 0x03B2F8,
        })

    # ── Embed 2b: Position Sizing (BUY only, compact) ──
    sizing_lines = []
    for symbol, sig in per_symbol.items():
        rec = sig.get("position_recommendation")
        if rec and sig["final_signal"] == "BUY":
            name = symbol_names.get(symbol, symbol)
            amt = rec.get("recommended_amount", 0)
            sizing_lines.append(f"{name}: \u20a9{amt:,.0f}")
    if sizing_lines:
        all_embeds.append({
            "title": "\U0001f4ca Position Sizing",
            "description": " | ".join(sizing_lines)[:4096],
            "color": 0x00CC88,
        })

    # ── Embed 2c: Event Warnings ──
    s6b = context.get("s6b_risk_sizing")
    s6b_data = s6b.data if s6b and s6b.status == "success" else {}
    event_lines = []
    global_events = s6b_data.get("global_events", []) if s6b_data else []
    for ev in global_events[:3]:
        event_lines.append(f"\U0001f5d3\ufe0f {ev}")
    for symbol, sig in per_symbol.items():
        ew = sig.get("event_warning")
        if ew:
            event_lines.append(f"\u26a0\ufe0f {symbol_names.get(symbol, symbol)}: {ew}")
    if event_lines:
        all_embeds.append({
            "title": "Event Warnings",
            "description": "\n".join(event_lines[:8])[:4096],
            "color": 0xFFAA00,
        })

    # ── Embed 3: Hard Limit + Red-Team (merged) ──
    alert_lines = []
    for sym, sig in per_symbol.items():
        if sig.get("hard_limit_triggered"):
            alert_lines.append(
                f"\U0001f6d1 **{symbol_names.get(sym, sym)}**: {sig.get('hard_limit_reason', 'HL')}"
            )
    for sym, sig in per_symbol.items():
        if sig.get("red_team_warning"):
            alert_lines.append(
                f"\u26a0\ufe0f **{symbol_names.get(sym, sym)}**: {sig['red_team_warning']}"
            )
    if alert_lines:
        all_embeds.append({
            "title": "Alerts",
            "description": "\n".join(alert_lines[:10])[:4096],
            "color": 0xFF0000,
        })

    # ── Embed: AI Signal Analysis (Korean, top 10) ──
    s8 = context.get("s8_explanation")
    if s8 and s8.status == "success":
        s8_per_symbol = s8.data.get("per_symbol", {})
        explain_lines = []
        # Prioritize BUY/SELL explanations
        for symbol, exp_data in s8_per_symbol.items():
            text = exp_data.get("explanation_llm") or exp_data.get("explanation_rule", "")
            if text:
                sig_type = exp_data.get("final_signal", "HOLD")
                emoji = _signal_emoji(sig_type)
                explain_lines.append((sig_type, f"{emoji} {text}"))

        # Sort: BUY first, then SELL, then HOLD
        priority = {"BUY": 0, "SELL": 1, "HOLD": 2}
        explain_lines.sort(key=lambda x: priority.get(x[0], 3))
        top_lines = [line for _, line in explain_lines[:12]]

        if top_lines:
            all_embeds.append({
                "title": "\U0001f4dd AI \ubd84\uc11d",
                "description": "\n".join(top_lines)[:4096],
                "color": 0x5865F2,
            })

    # ── Embed: Portfolio Holdings Status ──
    s9 = context.get("s9_portfolio_scenarios")
    if s9 and s9.status == "success":
        held = s9.data.get("held_scenarios", {})
        if held:
            held_lines = []
            for symbol, scenario in held.items():
                name = scenario.get("name", symbol_names.get(symbol, symbol))
                pnl = scenario.get("pnl_pct", 0)
                pnl_emoji = "\U0001f7e2" if pnl > 0 else "\U0001f7e1" if pnl == 0 else "\U0001f534"
                targets = scenario.get("target_prices", {})
                cur = scenario.get("current_price", 0)
                sl = targets.get("stop_loss", 0)
                tp = targets.get("target_10pct", 0)
                held_lines.append(
                    f"{pnl_emoji} **{name}** {pnl:+.1f}% "
                    f"(\u20a9{cur:,.0f} | SL \u20a9{sl:,.0f} | TP \u20a9{tp:,.0f})"
                )
            all_embeds.append({
                "title": "\U0001f4bc \ubcf4\uc720 \uc885\ubaa9",
                "description": "\n".join(held_lines[:10])[:4096],
                "color": 0x9B59B6,
            })

        # ── Embed: New Entry Opportunities ──
        entry = s9.data.get("entry_scenarios", {})
        if entry:
            entry_lines = []
            for symbol, scenario in entry.items():
                name = scenario.get("name", symbol_names.get(symbol, symbol))
                targets = scenario.get("target_prices", {})
                cur = targets.get("entry", 0)
                sl = targets.get("stop_loss", 0)
                tp = targets.get("target_10pct", 0)
                entry_lines.append(
                    f"\U0001f7e2 **{name}** \u20a9{cur:,.0f} "
                    f"(SL \u20a9{sl:,.0f} | TP \u20a9{tp:,.0f})"
                )
            all_embeds.append({
                "title": "\U0001f195 \uc2e0\uaddc \uc9c4\uc785",
                "description": "\n".join(entry_lines[:8])[:4096],
                "color": 0x2ECC71,
            })

    # ── Embed: News Headlines ──
    s3c = context.get("s3c_news_analysis")
    if s3c and s3c.status == "success":
        s3c_per_symbol = s3c.data.get("per_symbol", {})
        news_lines = []
        # Show news for BUY/SELL signals only (most relevant)
        for symbol, sig in per_symbol.items():
            if sig["final_signal"] in ("BUY", "SELL") and symbol in s3c_per_symbol:
                ns = s3c_per_symbol[symbol]
                if ns.get("article_count", 0) > 0:
                    name = symbol_names.get(symbol, symbol)
                    score = ns.get("news_score", 0)
                    emoji = "\U0001f7e2" if score > 0 else "\U0001f534" if score < 0 else "\U0001f7e1"
                    headlines = ns.get("headlines", [])
                    top_headline = headlines[0].get("title", "")[:60] if headlines else ""
                    news_lines.append(
                        f"{emoji} **{name}** ({score:+.0f}): {top_headline}"
                    )
        if news_lines:
            all_embeds.append({
                "title": "\U0001f4f0 뉴스",
                "description": "\n".join(news_lines[:8])[:4096],
                "color": 0x1DA1F2,
            })

    # ── Footer embed ──
    buy_count = sum(1 for s in per_symbol.values() if s["final_signal"] == "BUY")
    sell_count = sum(1 for s in per_symbol.values() if s["final_signal"] == "SELL")
    hold_count = sum(1 for s in per_symbol.values() if s["final_signal"] == "HOLD")

    all_embeds.append({
        "description": (
            f"Symbols: {len(per_symbol)} | "
            f"B/S/H: {buy_count}/{sell_count}/{hold_count} | "
            f"Time: {elapsed:.1f}s"
        ),
        "color": 0x888888,
        "footer": {"text": f"VIBE v{settings.VERSION} | UFS"},
    })

    # ── Split into multiple messages to respect 6000 char limit ──
    return _split_into_payloads(all_embeds)


def _calc_embed_chars(embed: dict) -> int:
    """Calculate total character count of an embed for Discord's limit."""
    total = 0
    total += len(embed.get("title", ""))
    total += len(embed.get("description", ""))
    for field in embed.get("fields", []):
        total += len(field.get("name", ""))
        total += len(field.get("value", ""))
    footer = embed.get("footer", {})
    total += len(footer.get("text", ""))
    author = embed.get("author", {})
    total += len(author.get("name", ""))
    return total


def _split_into_payloads(
    embeds: list[dict], max_chars: int = 5800, max_embeds: int = 10,
) -> list[dict]:
    """Split embeds into multiple payloads respecting Discord limits.

    Each payload stays under max_chars total and max_embeds count.
    """
    payloads: list[dict] = []
    current_embeds: list[dict] = []
    current_chars = 0

    for embed in embeds:
        embed_chars = _calc_embed_chars(embed)
        would_exceed_chars = (current_chars + embed_chars) > max_chars
        would_exceed_count = len(current_embeds) >= max_embeds

        if current_embeds and (would_exceed_chars or would_exceed_count):
            payloads.append({
                "username": "VIBE",
                "embeds": current_embeds,
            })
            current_embeds = []
            current_chars = 0

        current_embeds.append(embed)
        current_chars += embed_chars

    if current_embeds:
        payloads.append({
            "username": "VIBE",
            "embeds": current_embeds,
        })

    return payloads


# Legacy single-payload API (kept for backward compatibility)
def build_dashboard_payload(context: dict[str, Any]) -> dict:
    """Build a single Discord payload. May exceed Discord limits for large watchlists.

    Prefer build_dashboard_payloads() which returns multiple payloads if needed.
    """
    payloads = build_dashboard_payloads(context)
    if not payloads:
        return {"username": "VIBE", "embeds": []}
    # Merge all embeds into one payload (caller handles splitting if needed)
    all_embeds = []
    for p in payloads:
        all_embeds.extend(p.get("embeds", []))
    return {"username": "VIBE", "embeds": all_embeds[:10]}


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
