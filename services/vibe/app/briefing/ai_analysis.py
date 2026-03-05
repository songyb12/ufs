"""AI-powered market analysis using VIBE database context.

Gathers macro, sentiment, signals, portfolio, and performance data,
then sends to LLM for comprehensive Korean market commentary.
"""

import json
import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import repositories as repo
from app.database.connection import get_db

logger = logging.getLogger("vibe.briefing.ai")


async def gather_analysis_context(
    markets: list[str] | None = None,
    include_portfolio: bool = True,
    portfolio_id: int = 1,
) -> dict:
    """Gather comprehensive context from DB for LLM analysis."""
    if markets is None:
        markets = ["KR", "US"]

    ctx: dict = {"gathered_at": datetime.now(timezone.utc).isoformat()}

    # 1. Macro snapshot
    macro = await repo.get_latest_macro()
    if macro:
        ctx["macro"] = {
            "vix": macro.get("vix"),
            "dxy": macro.get("dxy_index"),
            "usd_krw": macro.get("usd_krw"),
            "us_10y": macro.get("us_10y_yield"),
            "us_2y": macro.get("us_2y_yield"),
            "yield_spread": macro.get("us_yield_spread"),
            "wti": macro.get("wti_crude"),
            "gold": macro.get("gold_price"),
            "date": macro.get("indicator_date"),
        }

    # 2. Sentiment
    sentiment = await repo.get_latest_sentiment()
    if sentiment:
        ctx["sentiment"] = {
            "fear_greed": sentiment.get("fear_greed_index"),
            "put_call_ratio": sentiment.get("put_call_ratio"),
            "vix_term_structure": sentiment.get("vix_term_structure"),
            "date": sentiment.get("indicator_date"),
        }

    # 3. Latest signals summary
    db = await get_db()
    signal_summary = {}
    for mkt in markets:
        c = await db.execute(
            """SELECT final_signal, COUNT(*) as cnt, AVG(raw_score) as avg_score
               FROM signals
               WHERE signal_date = (SELECT MAX(signal_date) FROM signals)
               AND market = ?
               GROUP BY final_signal""",
            (mkt,),
        )
        rows = [dict(r) for r in await c.fetchall()]
        signal_summary[mkt] = {r["final_signal"]: {"count": r["cnt"], "avg_score": round(r["avg_score"], 1)} for r in rows}

    ctx["signals_summary"] = signal_summary

    # 4. Top movers (BUY/SELL with highest absolute scores)
    c = await db.execute(
        """SELECT s.symbol, s.market, s.final_signal, s.raw_score,
                  s.rsi_value, s.confidence, s.rationale, w.name
           FROM signals s
           LEFT JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
           WHERE s.signal_date = (SELECT MAX(signal_date) FROM signals)
           AND s.final_signal IN ('BUY', 'SELL')
           ORDER BY ABS(s.raw_score) DESC
           LIMIT 8""",
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
            "confidence": round(r["confidence"], 2) if r["confidence"] else None,
            "rationale": (r["rationale"] or "")[:120],
        })
    ctx["top_movers"] = movers

    # 5. Portfolio state
    if include_portfolio:
        positions = await repo.get_portfolio_state(portfolio_id=portfolio_id)
        portfolio_ctx = []
        for p in positions[:15]:
            portfolio_ctx.append({
                "symbol": p["symbol"],
                "market": p["market"],
                "entry_price": p.get("entry_price"),
                "position_size": p.get("position_size"),
                "sector": p.get("sector"),
            })
        ctx["portfolio"] = portfolio_ctx

    # 6. Performance summary
    perf = await repo.get_performance_summary()
    if perf:
        ctx["performance"] = {
            "total_signals": perf.get("total_signals", 0),
            "buy_signals": perf.get("buy_signals", 0),
            "sell_signals": perf.get("sell_signals", 0),
            "hit_rate_t5": round(perf["hit_rate_t5"] * 100, 1) if perf.get("hit_rate_t5") else None,
            "hit_rate_t20": round(perf["hit_rate_t20"] * 100, 1) if perf.get("hit_rate_t20") else None,
            "avg_return_t5": round(perf["avg_return_t5"], 2) if perf.get("avg_return_t5") else None,
            "avg_return_t20": round(perf["avg_return_t20"], 2) if perf.get("avg_return_t20") else None,
        }

    # 7. Upcoming events
    events = []
    for mkt in markets:
        evts = await repo.get_upcoming_events(market=mkt, days_ahead=7)
        for e in evts[:5]:
            events.append({
                "date": e["event_date"],
                "type": e["event_type"],
                "market": e.get("market"),
                "description": e["description"],
                "impact": e.get("impact_level"),
            })
    ctx["upcoming_events"] = events

    return ctx


def _build_analysis_prompt(question: str, context: dict) -> str:
    """Build a structured Korean analysis prompt with VIBE data context."""
    macro = context.get("macro", {})
    sentiment = context.get("sentiment", {})
    signals = context.get("signals_summary", {})
    movers = context.get("top_movers", [])
    portfolio = context.get("portfolio", [])
    performance = context.get("performance", {})
    events = context.get("upcoming_events", [])

    sections = []
    sections.append("당신은 VIBE 투자 분석 시스템의 AI 어시스턴트입니다.")
    sections.append("아래 실시간 데이터를 기반으로 사용자의 질문에 한국어로 답변하세요.")
    sections.append("")

    # Macro
    if macro:
        sections.append("[매크로 환경]")
        sections.append(
            f"VIX={macro.get('vix', 'N/A')}, DXY={macro.get('dxy', 'N/A')}, "
            f"USD/KRW={macro.get('usd_krw', 'N/A')}, "
            f"US10Y={macro.get('us_10y', 'N/A')}%, US2Y={macro.get('us_2y', 'N/A')}%, "
            f"금리스프레드={macro.get('yield_spread', 'N/A')}, "
            f"WTI=${macro.get('wti', 'N/A')}, Gold=${macro.get('gold', 'N/A')}"
        )
        sections.append("")

    # Sentiment
    if sentiment:
        sections.append("[시장 심리]")
        fg = sentiment.get("fear_greed")
        fg_label = "N/A"
        if fg is not None:
            if fg <= 20: fg_label = "극단적 공포"
            elif fg <= 40: fg_label = "공포"
            elif fg <= 60: fg_label = "중립"
            elif fg <= 80: fg_label = "탐욕"
            else: fg_label = "극단적 탐욕"
        sections.append(
            f"Fear&Greed={fg}({fg_label}), "
            f"Put/Call={sentiment.get('put_call_ratio', 'N/A')}, "
            f"VIX구조={sentiment.get('vix_term_structure', 'N/A')}"
        )
        sections.append("")

    # Signals summary
    if signals:
        sections.append("[트레이딩 시그널 현황]")
        for mkt, summary in signals.items():
            buy = summary.get("BUY", {})
            sell = summary.get("SELL", {})
            hold = summary.get("HOLD", {})
            sections.append(
                f"{mkt}: BUY {buy.get('count', 0)}개(avg {buy.get('avg_score', 0)}), "
                f"SELL {sell.get('count', 0)}개(avg {sell.get('avg_score', 0)}), "
                f"HOLD {hold.get('count', 0)}개"
            )
        sections.append("")

    # Top movers
    if movers:
        sections.append("[주요 종목 시그널]")
        for m in movers:
            rsi_str = f", RSI={m['rsi']}" if m.get("rsi") else ""
            sections.append(
                f"- {m['name']}({m['symbol']}/{m['market']}): "
                f"{m['signal']} score={m['score']}{rsi_str}"
            )
        sections.append("")

    # Portfolio
    if portfolio:
        sections.append(f"[보유 포트폴리오 - {len(portfolio)}종목]")
        for p in portfolio[:10]:
            ep = f"매입가={p['entry_price']:,.0f}" if p.get("entry_price") else ""
            sz = f"투자금={p['position_size']:,.0f}" if p.get("position_size") else ""
            sections.append(
                f"- {p['symbol']}({p['market']}): {ep} {sz}"
            )
        sections.append("")

    # Performance
    if performance and performance.get("total_signals", 0) > 0:
        sections.append("[시그널 성과]")
        sections.append(
            f"총 {performance['total_signals']}건 "
            f"(BUY {performance.get('buy_signals', 0)}, SELL {performance.get('sell_signals', 0)})"
        )
        if performance.get("hit_rate_t5") is not None:
            sections.append(f"5일 명중률: {performance['hit_rate_t5']}%")
        if performance.get("hit_rate_t20") is not None:
            sections.append(f"20일 명중률: {performance['hit_rate_t20']}%")
        sections.append("")

    # Events
    if events:
        sections.append("[향후 7일 주요 일정]")
        for e in events:
            sections.append(f"- {e['date']} [{e.get('market', '')}] {e['description']} ({e.get('impact', '')})")
        sections.append("")

    # Question
    sections.append(f"[사용자 질문]")
    sections.append(question)
    sections.append("")
    sections.append("요구사항:")
    sections.append("- 한국어로 답변")
    sections.append("- 실제 데이터 기반으로 분석")
    sections.append("- 투자 조언이 아닌 객관적 해설")
    sections.append("- 핵심 수치와 근거를 포함")

    return "\n".join(sections)


async def run_ai_analysis(
    question: str = "오늘의 시장 상황을 종합 분석해주세요.",
    markets: list[str] | None = None,
    include_portfolio: bool = True,
    portfolio_id: int = 1,
) -> dict:
    """Run AI-powered analysis using VIBE database context.

    Returns dict with analysis text, metadata, and context snapshot.
    """
    if not settings.LLM_API_KEY:
        return {
            "status": "error",
            "message": "LLM API 키가 설정되지 않았습니다. .env에 LLM_API_KEY를 설정하세요.",
        }

    # 1. Gather context
    context = await gather_analysis_context(
        markets=markets,
        include_portfolio=include_portfolio,
        portfolio_id=portfolio_id,
    )

    # 2. Build prompt
    prompt = _build_analysis_prompt(question, context)
    logger.debug("AI analysis prompt length: %d chars", len(prompt))

    # 3. Call LLM
    analysis_text = None
    model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL
    provider = settings.LLM_PROVIDER.lower()

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
            response = await client.messages.create(
                model=model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            analysis_text = response.content[0].text.strip()
        elif provider == "openai":
            import openai
            client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
            )
            analysis_text = response.choices[0].message.content.strip()
        else:
            return {"status": "error", "message": f"Unknown LLM provider: {provider}"}
    except Exception as e:
        logger.error("AI analysis LLM call failed: %s", e)
        return {"status": "error", "message": f"LLM 호출 실패: {str(e)}"}

    # 4. Build response
    return {
        "status": "ok",
        "question": question,
        "analysis": analysis_text,
        "metadata": {
            "model": model,
            "provider": provider,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "context_snapshot": {
                "macro_date": context.get("macro", {}).get("date"),
                "signal_markets": list(context.get("signals_summary", {}).keys()),
                "top_movers_count": len(context.get("top_movers", [])),
                "portfolio_positions": len(context.get("portfolio", [])),
                "events_upcoming": len(context.get("upcoming_events", [])),
            },
        },
    }
