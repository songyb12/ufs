"""Daily market briefing generator.

Aggregates macro indicators, sentiment data, news headlines, and signal
summaries into a structured daily briefing.  Optionally enriches with LLM
commentary when LLM_EXPLANATION_ENABLED is True.
"""

import json
import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import repositories as repo
from app.database.connection import get_db

logger = logging.getLogger("vibe.briefing")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vix_label(vix: float | None) -> str:
    if vix is None:
        return "N/A"
    if vix < 12:
        return "매우 안정"
    if vix < 20:
        return "안정"
    if vix < 25:
        return "주의"
    if vix < 30:
        return "경계"
    return "공포"


def _fg_label(fg: int | None) -> str:
    if fg is None:
        return "N/A"
    if fg <= 20:
        return "극단적 공포"
    if fg <= 40:
        return "공포"
    if fg <= 60:
        return "중립"
    if fg <= 80:
        return "탐욕"
    return "극단적 탐욕"


def _yield_label(spread: float | None) -> str:
    if spread is None:
        return "N/A"
    if spread < 0:
        return "역전 (경기침체 경고)"
    if spread < 0.5:
        return "평탄화 (주의)"
    return "정상"


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

async def generate_market_briefing(target_date: str | None = None) -> dict:
    """Build a comprehensive market briefing from available data.

    Returns a dict with sections:
      macro, sentiment, signals, news, market_movers, summary_text
    """
    db = await get_db()
    today = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- 1. Macro Snapshot ---
    macro = await repo.get_latest_macro()
    macro_section = {}
    if macro:
        macro_section = {
            "date": macro.get("indicator_date", today),
            "vix": macro.get("vix"),
            "vix_label": _vix_label(macro.get("vix")),
            "dxy": macro.get("dxy_index"),
            "usd_krw": macro.get("usd_krw"),
            "us_10y": macro.get("us_10y_yield"),
            "us_2y": macro.get("us_2y_yield"),
            "yield_spread": macro.get("us_yield_spread"),
            "yield_label": _yield_label(macro.get("us_yield_spread")),
            "wti": macro.get("wti_crude"),
            "gold": macro.get("gold_price"),
        }

    # --- 2. Sentiment ---
    sentiment = await repo.get_latest_sentiment()
    sentiment_section = {}
    if sentiment:
        sentiment_section = {
            "date": sentiment.get("indicator_date", today),
            "fear_greed": sentiment.get("fear_greed_index"),
            "fear_greed_label": _fg_label(sentiment.get("fear_greed_index")),
            "put_call_ratio": sentiment.get("put_call_ratio"),
            "vix_term_structure": sentiment.get("vix_term_structure"),
        }

    # --- 3. Signal Summary (latest date) ---
    c = await db.execute(
        """SELECT final_signal, market, COUNT(*) as cnt
           FROM signals
           WHERE signal_date = (SELECT MAX(signal_date) FROM signals)
           GROUP BY final_signal, market"""
    )
    signal_rows = [dict(r) for r in await c.fetchall()]
    signal_summary = {"KR": {"BUY": 0, "SELL": 0, "HOLD": 0}, "US": {"BUY": 0, "SELL": 0, "HOLD": 0}}
    latest_signal_date = None
    for sr in signal_rows:
        mkt = sr.get("market", "KR")
        sig = sr.get("final_signal", "HOLD")
        if mkt in signal_summary and sig in signal_summary[mkt]:
            signal_summary[mkt][sig] = sr["cnt"]

    c = await db.execute("SELECT MAX(signal_date) FROM signals")
    row = await c.fetchone()
    if row:
        latest_signal_date = row[0]

    # --- 4. Top Movers (BUY/SELL with highest scores) ---
    c = await db.execute(
        """SELECT s.symbol, s.market, s.final_signal, s.raw_score,
                  s.rsi_value, s.rationale, w.name
           FROM signals s
           LEFT JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
           WHERE s.signal_date = (SELECT MAX(signal_date) FROM signals)
           AND s.final_signal IN ('BUY', 'SELL')
           ORDER BY ABS(s.raw_score) DESC
           LIMIT 10"""
    )
    movers = []
    for r in await c.fetchall():
        movers.append({
            "symbol": r["symbol"],
            "name": r["name"] or r["symbol"],
            "market": r["market"],
            "signal": r["final_signal"],
            "score": round(r["raw_score"], 1) if r["raw_score"] else 0,
            "rsi": round(r["rsi_value"], 1) if r["rsi_value"] else None,
            "rationale": r["rationale"],
        })

    # --- 5. Recent News Headlines (from news_data) ---
    c = await db.execute(
        """SELECT symbol, market, trade_date, headlines_json, news_score
           FROM news_data
           WHERE trade_date >= date(?, '-3 days')
           ORDER BY trade_date DESC
           LIMIT 30""",
        (today,),
    )
    news_items = []
    for r in await c.fetchall():
        headlines = []
        if r["headlines_json"]:
            try:
                headlines = json.loads(r["headlines_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        for h in headlines[:3]:  # top 3 per symbol
            news_items.append({
                "symbol": r["symbol"],
                "market": r["market"],
                "title": h.get("title", "") if isinstance(h, dict) else str(h),
                "score": h.get("score", 0) if isinstance(h, dict) else 0,
                "date": r["trade_date"],
            })
    # Sort by absolute score (most impactful first)
    news_items.sort(key=lambda x: abs(x.get("score", 0)), reverse=True)
    news_items = news_items[:15]  # top 15

    # --- 6. Build summary text ---
    lines = []
    lines.append(f"[{today} 시황 브리핑]")
    if macro_section:
        lines.append(f"VIX {macro_section.get('vix', 'N/A')} ({macro_section.get('vix_label', '')})")
        lines.append(f"DXY {macro_section.get('dxy', 'N/A')} | USD/KRW {macro_section.get('usd_krw', 'N/A')}")
        lines.append(f"US10Y {macro_section.get('us_10y', 'N/A')}% | Spread {macro_section.get('yield_spread', 'N/A')} ({macro_section.get('yield_label', '')})")
        lines.append(f"WTI ${macro_section.get('wti', 'N/A')} | Gold ${macro_section.get('gold', 'N/A')}")
    if sentiment_section:
        lines.append(f"Fear&Greed {sentiment_section.get('fear_greed', 'N/A')} ({sentiment_section.get('fear_greed_label', '')})")
        pcr = sentiment_section.get("put_call_ratio")
        if pcr:
            lines.append(f"Put/Call {pcr:.2f}")
    if latest_signal_date:
        kr = signal_summary.get("KR", {})
        us = signal_summary.get("US", {})
        lines.append(f"KR: BUY {kr.get('BUY',0)} / SELL {kr.get('SELL',0)} / HOLD {kr.get('HOLD',0)}")
        lines.append(f"US: BUY {us.get('BUY',0)} / SELL {us.get('SELL',0)} / HOLD {us.get('HOLD',0)}")
    summary_text = "\n".join(lines)

    # --- Assemble ---
    content = {
        "briefing_date": today,
        "macro": macro_section,
        "sentiment": sentiment_section,
        "signals": {
            "date": latest_signal_date,
            "summary": signal_summary,
        },
        "market_movers": movers,
        "news": news_items,
        "summary_text": summary_text,
    }

    # --- LLM Commentary (optional) ---
    llm_summary = None
    if settings.LLM_EXPLANATION_ENABLED and settings.LLM_API_KEY:
        llm_summary = await _generate_llm_commentary(content)

    # --- Save ---
    await repo.upsert_market_briefing(today, "ALL", content, llm_summary)
    logger.info("Market briefing generated for %s", today)

    return {**content, "llm_summary": llm_summary}


async def _generate_llm_commentary(content: dict) -> str | None:
    """Use LLM to generate a concise Korean market commentary."""
    try:
        provider = settings.LLM_PROVIDER.lower()
        model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL

        macro = content.get("macro", {})
        sentiment = content.get("sentiment", {})
        signals = content.get("signals", {})
        movers = content.get("market_movers", [])

        prompt = f"""아래 데이터를 바탕으로 오늘의 시황을 3~5문장의 한국어 브리핑으로 작성하세요.
개인 투자자가 이해할 수 있도록 핵심만 전달하세요.

매크로: VIX={macro.get('vix')}, DXY={macro.get('dxy')}, USD/KRW={macro.get('usd_krw')}, US10Y={macro.get('us_10y')}%, 금리스프레드={macro.get('yield_spread')}, WTI=${macro.get('wti')}, Gold=${macro.get('gold')}
심리: Fear&Greed={sentiment.get('fear_greed')}({sentiment.get('fear_greed_label')}), Put/Call={sentiment.get('put_call_ratio')}, VIX구조={sentiment.get('vix_term_structure')}
시그널: KR({signals.get('summary',{}).get('KR',{})}), US({signals.get('summary',{}).get('US',{})})
주요종목: {', '.join(f"{m['name']}({m['signal']} {m['score']})" for m in movers[:5])}

요구사항:
- 3~5문장, 한국어
- 시장 분위기, 주의 사항, 기회 요인을 포함
- 투자 조언이 아닌 사실 기반 해설"""

        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
            response = await client.messages.create(
                model=model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        elif provider == "openai":
            import openai
            client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        else:
            logger.warning("Unknown LLM provider: %s", provider)
            return None
    except Exception as e:
        logger.error("LLM commentary generation failed: %s", e)
        return None
