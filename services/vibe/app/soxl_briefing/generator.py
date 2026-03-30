"""SOXL Daily Briefing Generator.

Collects market data from the VIBE DB, calls the Anthropic LLM to
produce a structured Korean-language briefing, and persists the result
via ``store.save_briefing()``.

The generator is designed to run **without** a FastAPI ``Request`` object
so it can be invoked from APScheduler jobs or CLI scripts as well as
from an HTTP endpoint.
"""

import json
import logging
from datetime import datetime, timezone

import numpy as np

from app.config import settings
from app.database.connection import get_db
from app.soxl_briefing.store import save_briefing
from app.utils.soxl_indicators import (
    compute_bollinger,
    compute_macd,
    compute_rsi,
)

logger = logging.getLogger("vibe.soxl_briefing.generator")

BRIEFING_SYSTEM_PROMPT = (
    "당신은 SOXL 3x 레버리지 ETF 전문 투자 애널리스트입니다. "
    "포트폴리오 비중 50% 이상 보유자를 위한 일간 브리핑을 작성합니다. "
    "반드시 아래 구조로 작성하세요:\n\n"
    "1) **오늘의 판단** (BUY/HOLD/REDUCE/SELL + 한줄 근거)\n"
    "2) **반도체 섹터 매크로 현황**\n"
    "3) **기술적 분석 시그널**\n"
    "4) **3x 레버리지 특수 분석** (변동성 드래그, 괴리율, MDD 위치)\n"
    "5) **손절/익절 라인** (ATR 기반 동적 스톱, 지지/저항 기반 목표가, 시나리오별 3단계)\n"
    "6) **포지션 비중 조정 제안**\n"
    "7) **주의사항 및 리스크 팩터**\n\n"
    "모든 수치는 구체적 가격으로 제시하세요. "
    "마지막에 반드시 레버리지 ETF 장기보유 리스크 디스클레이머를 포함하세요."
)


# ---------------------------------------------------------------------------
# Data collection (DB-only, no Request / Finnhub dependency)
# ---------------------------------------------------------------------------

async def _collect_context() -> dict:
    """Gather SOXL-relevant data from the local DB.

    This mirrors the data that ``soxl_live._gather_soxl_context()`` collects
    but does **not** require a live Finnhub connection — the latest daily
    close from ``price_history`` is used instead of a real-time quote.
    """
    db = await get_db()
    ctx: dict = {}

    # 1. Latest price from DB
    try:
        cursor = await db.execute(
            """SELECT trade_date, open, high, low, close, volume
               FROM price_history
               WHERE symbol='SOXL' AND market='US'
               ORDER BY trade_date DESC LIMIT 60"""
        )
        rows = await cursor.fetchall()
        if rows:
            latest = rows[0]
            ctx["price"] = latest[4]
            ctx["price_date"] = latest[0]
            ctx["open"] = latest[1]
            ctx["high"] = latest[2]
            ctx["low"] = latest[3]
            ctx["volume"] = latest[4]

            daily_closes = [r[4] for r in reversed(rows)]
            daily_volumes = [r[5] or 0 for r in reversed(rows)]
            closes = np.array(daily_closes, dtype=float)

            # Technicals
            rsi_val = compute_rsi(closes, 14)
            ctx["rsi_14"] = round(rsi_val, 1) if rsi_val is not None else None
            macd_l, sig_l, hist = compute_macd(closes)
            ctx["macd"] = round(macd_l, 4) if macd_l is not None else None
            ctx["macd_signal"] = round(sig_l, 4) if sig_l is not None else None
            ctx["macd_histogram"] = round(hist, 4) if hist is not None else None
            bb_u, bb_m, bb_l = compute_bollinger(closes, 20, 2)
            ctx["bb_upper"] = round(bb_u, 2) if bb_u is not None else None
            ctx["bb_middle"] = round(bb_m, 2) if bb_m is not None else None
            ctx["bb_lower"] = round(bb_l, 2) if bb_l is not None else None
            ctx["ma_5"] = round(float(np.mean(closes[-5:])), 2) if len(closes) >= 5 else None
            ctx["ma_20"] = round(float(np.mean(closes[-20:])), 2) if len(closes) >= 20 else None
            ctx["ma_60"] = round(float(np.mean(closes[-60:])), 2) if len(closes) >= 60 else None

            if len(daily_volumes) >= 20:
                avg_vol = np.mean(daily_volumes[-20:])
                ctx["volume_ratio"] = round(daily_volumes[-1] / avg_vol, 2) if avg_vol > 0 else None
            else:
                ctx["volume_ratio"] = None

            # 1d / 5d change
            if len(daily_closes) >= 2:
                prev = daily_closes[-2]
                ctx["change_1d"] = round((daily_closes[-1] - prev) / prev * 100, 2) if prev else None
            if len(daily_closes) >= 6:
                prev5 = daily_closes[-6]
                ctx["change_5d"] = round((daily_closes[-1] - prev5) / prev5 * 100, 2) if prev5 else None
    except Exception as e:
        logger.warning("Context: price/technicals failed: %s", e)

    # 2. Latest signal
    try:
        cursor = await db.execute(
            """SELECT final_signal, raw_score, confidence, rationale, signal_date
               FROM signals WHERE symbol='SOXL'
               ORDER BY signal_date DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            ctx["signal"] = {
                "final_signal": row[0], "raw_score": row[1],
                "confidence": row[2], "rationale": row[3], "date": row[4],
            }
    except Exception as e:
        logger.debug("Context: signal query failed: %s", e)

    # 3. Macro snapshot
    try:
        cursor = await db.execute(
            """SELECT vix, dxy_index, us_10y_yield, us_2y_yield, us_yield_spread,
                      wti_crude, gold_price, usd_krw, fed_funds_rate, fear_greed_index,
                      indicator_date
               FROM macro_indicators ORDER BY indicator_date DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            ctx["macro"] = {
                "vix": row[0], "dxy": row[1], "us_10y": row[2], "us_2y": row[3],
                "yield_spread": row[4], "wti": row[5], "gold": row[6],
                "usd_krw": row[7], "fed_rate": row[8], "fear_greed": row[9],
                "date": row[10],
            }
    except Exception as e:
        logger.debug("Context: macro query failed: %s", e)

    # 4. Geopolitical events (recent 5)
    try:
        cursor = await db.execute(
            """SELECT event_date, event_text, detail, impact
               FROM geopolitical_events
               ORDER BY event_date DESC, id DESC LIMIT 5"""
        )
        ctx["geo_events"] = [
            {"date": r[0], "event": r[1], "detail": r[2], "impact": r[3]}
            for r in await cursor.fetchall()
        ]
    except Exception as e:
        logger.debug("Context: geo events failed: %s", e)
        ctx["geo_events"] = []

    # 5. Best backtest result
    try:
        cursor = await db.execute(
            """SELECT mode, sharpe_ratio, max_drawdown, total_return,
                      hit_rate, total_trades, start_date, end_date
               FROM soxl_backtest_runs
               WHERE status='completed' AND sharpe_ratio IS NOT NULL
               ORDER BY sharpe_ratio DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            ctx["best_backtest"] = {
                "mode": row[0], "sharpe": row[1],
                "max_drawdown": row[2], "total_return": row[3],
                "hit_rate": row[4], "total_trades": row[5],
                "period": f"{row[6]}~{row[7]}",
            }
    except Exception as e:
        logger.debug("Context: best backtest query failed: %s", e)

    # 6. Latest optimization result
    try:
        cursor = await db.execute(
            """SELECT mode, params_json, sharpe, sortino, max_drawdown, total_return, run_at
               FROM soxl_optimize_results
               WHERE sharpe IS NOT NULL
               ORDER BY created_at DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            ctx["latest_optimize"] = {
                "mode": row[0],
                "params": json.loads(row[1]) if row[1] else {},
                "sharpe": row[2], "sortino": row[3],
                "max_drawdown": row[4], "total_return": row[5],
                "run_at": row[6],
            }
    except Exception as e:
        logger.debug("Context: optimize result query failed: %s", e)

    return ctx


# ---------------------------------------------------------------------------
# Briefing generation
# ---------------------------------------------------------------------------

async def generate_soxl_briefing() -> dict:
    """Generate, persist, and return today's SOXL daily briefing.

    Returns
    -------
    dict
        ``{"status": "ok"|"error", "briefing_text": str, "metadata": dict}``
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── Step 1: Collect context ──
    ctx = await _collect_context()
    if not ctx.get("price"):
        logger.warning("No SOXL price data — generating fallback briefing")
        fallback = f"[{today}] SOXL 가격 데이터를 조회할 수 없어 브리핑을 생성하지 못했습니다."
        return {"status": "error", "briefing_text": fallback, "metadata": {"error": "no_price_data"}}

    # ── Step 2: Call LLM ──
    if not settings.LLM_API_KEY:
        fallback = f"[{today}] LLM API 키가 설정되지 않아 브리핑을 생성하지 못했습니다."
        return {"status": "error", "briefing_text": fallback, "metadata": {"error": "no_api_key"}}

    try:
        import anthropic
    except ImportError:
        fallback = f"[{today}] anthropic 패키지가 설치되지 않아 브리핑을 생성하지 못했습니다."
        return {"status": "error", "briefing_text": fallback, "metadata": {"error": "no_anthropic"}}

    model = settings.LLM_EXPLANATION_MODEL or settings.LLM_MODEL
    user_message = (
        f"아래는 {today} 기준 SOXL 관련 데이터입니다. "
        "이 데이터를 기반으로 일간 브리핑을 작성해주세요.\n\n"
        f"```json\n{json.dumps(ctx, ensure_ascii=False, indent=2, default=str)}\n```"
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
        response = await client.messages.create(
            model=model,
            max_tokens=3000,
            system=BRIEFING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            timeout=120.0,
        )
        briefing_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                briefing_text += block.text
        briefing_text = briefing_text.strip()
    except Exception as e:
        logger.error("LLM call failed: %s", e, exc_info=True)
        fallback = (
            f"[{today}] LLM 호출 실패로 브리핑을 생성하지 못했습니다. "
            f"오류: {e}\n\n"
            f"수집된 데이터 요약 — 현재가: ${ctx.get('price')}, "
            f"RSI: {ctx.get('rsi_14')}, VIX: {ctx.get('macro', {}).get('vix')}"
        )
        await save_briefing(today, fallback, {"error": str(e), "context_keys": list(ctx.keys())})
        return {"status": "error", "briefing_text": fallback, "metadata": {"error": str(e)}}

    # ── Step 3: Build metadata & persist ──
    signal_info = ctx.get("signal", {})
    macro_info = ctx.get("macro", {})
    metadata = {
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "price": ctx.get("price"),
        "rsi_14": ctx.get("rsi_14"),
        "signal": signal_info.get("final_signal"),
        "signal_score": signal_info.get("raw_score"),
        "vix": macro_info.get("vix"),
        "fear_greed": macro_info.get("fear_greed"),
        "context_keys": list(ctx.keys()),
    }
    await save_briefing(today, briefing_text, metadata)

    # ── Step 4: Return ──
    return {
        "status": "ok",
        "briefing_text": briefing_text,
        "metadata": metadata,
    }
