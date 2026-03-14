"""SOXL-Specific Backtesting & AI Strategy Router.

Endpoints:
  POST /soxl/backtest/run          — Run single-mode backtest
  POST /soxl/backtest/compare      — Compare all 4 modes (A/B/C/D)
  POST /soxl/backtest/ai-strategy  — AI-driven optimal strategy generation
  GET  /soxl/backtest/results      — List recent runs
  GET  /soxl/backtest/results/{id} — Detailed run + trades
  DELETE /soxl/backtest/results    — Clean old backtest results
  GET  /soxl/backtest/presets      — Parameter preset list
  GET  /soxl/backtest/stats/{id}   — Extended trade statistics
  GET  /soxl/backtest/export/{id}  — Export trades as CSV
"""

import csv
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.backtesting.soxl_engine import (
    PARAM_PRESETS,
    SoxlBacktestEngine,
    SoxlBacktestParams,
    StrategyMode,
)

router = APIRouter(prefix="/soxl/backtest", tags=["soxl-backtest"])
logger = logging.getLogger("vibe.soxl_backtest")

# Reusable mode labels
_MODE_LABELS = {
    "A": "Technical Only",
    "B": "Tech + Macro",
    "C": "Tech + Macro + Geo",
    "D": "Full (+ Vol + Decay)",
}

# Mode descriptions for documentation
_MODE_DESCRIPTIONS = {
    "A": "RSI/MACD/BB/StochRSI/ADX 기술적 지표만 사용",
    "B": "기술적 + VIX/금리/유가 매크로 게이팅",
    "C": "기술적 + 매크로 + 지정학 리스크 스코어",
    "D": "풀 모드: 변동성 스케일링 + 레버리지 decay + 슬리피지 + ATR 스탑",
}


class SoxlBacktestRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    mode: str = "D"
    params: Optional[dict] = None
    preset: Optional[str] = None  # [NEW] Named preset

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        v = v.upper()
        if v not in ("A", "B", "C", "D"):
            raise ValueError(f"Invalid mode '{v}'. Use A/B/C/D.")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates(cls, v):
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format '{v}'. Use YYYY-MM-DD.")
        return v


def _resolve_dates(req: SoxlBacktestRequest) -> tuple[str, str]:
    """Resolve start/end dates with defaults."""
    end_date = req.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = req.start_date or (
        datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=365)
    ).strftime("%Y-%m-%d")
    return start_date, end_date


def _build_params(req_params: dict | None, preset: str | None = None) -> SoxlBacktestParams:
    """Build SoxlBacktestParams from request dict with validation.

    If preset is specified, apply preset defaults first, then override with req_params.
    """
    params = SoxlBacktestParams()

    # [NEW] Apply preset first
    if preset and preset in PARAM_PRESETS:
        preset_vals = PARAM_PRESETS[preset]
        for k, v in preset_vals.items():
            if hasattr(params, k):
                setattr(params, k, v)

    # Then override with explicit params
    if req_params:
        for k, v in req_params.items():
            if hasattr(params, k):
                expected_type = type(getattr(params, k))
                try:
                    setattr(params, k, expected_type(v))
                except (ValueError, TypeError):
                    logger.warning("Invalid param %s=%s, using default", k, v)
    return params


# ── Endpoint 1: POST /run ──

@router.post("/run")
async def run_soxl_backtest(req: SoxlBacktestRequest):
    """Run SOXL-specific backtest (synchronous — single symbol is fast)."""
    start_date, end_date = _resolve_dates(req)

    try:
        mode = StrategyMode(req.mode.upper())
    except ValueError:
        raise HTTPException(400, f"Invalid mode '{req.mode}'. Use A/B/C/D.")

    params = _build_params(req.params, req.preset)
    engine = SoxlBacktestEngine()
    return await engine.run(start_date, end_date, mode, params)


# ── Endpoint 2: POST /compare ──

@router.post("/compare")
async def compare_soxl_modes(req: SoxlBacktestRequest):
    """Run all 4 strategy modes and compare metrics."""
    start_date, end_date = _resolve_dates(req)
    params = _build_params(req.params, req.preset)
    engine = SoxlBacktestEngine()

    results = []
    for mode in StrategyMode:
        result = await engine.run(start_date, end_date, mode, params)
        metrics = result.get("metrics", {})
        results.append({
            "mode": mode.value,
            "mode_label": _MODE_LABELS.get(mode.value, mode.value),
            "mode_description": _MODE_DESCRIPTIONS.get(mode.value, ""),
            "status": result.get("status"),
            "metrics": metrics,
            "leverage_decay_total": result.get("leverage_decay_total", 0),
            "transaction_costs": result.get("transaction_costs"),
            "benchmark_return": result.get("benchmark_return"),
            "trades_count": len(result.get("trades", [])),
            "backtest_id": result.get("backtest_id"),
            # [NEW] Extended stats
            "monthly_returns": result.get("monthly_returns"),
            "exit_reason_stats": result.get("exit_reason_stats"),
        })

    # Find best mode by total_return
    valid = [
        r for r in results
        if r["metrics"] and r["metrics"].get("total_return") is not None
    ]
    best_mode = max(valid, key=lambda x: x["metrics"]["total_return"]) if valid else None

    # Find best risk-adjusted (by sharpe)
    best_sharpe = max(valid, key=lambda x: x["metrics"].get("sharpe_ratio", 0)) if valid else None

    # [NEW] Find best Sortino
    best_sortino = max(valid, key=lambda x: x["metrics"].get("sortino_ratio", 0)) if valid else None

    # [NEW] Find lowest max drawdown
    best_drawdown = min(valid, key=lambda x: x["metrics"].get("max_drawdown", 999)) if valid else None

    # [NEW] Compute alpha vs benchmark for each mode
    for r in results:
        bnh = r.get("benchmark_return")
        total_ret = r["metrics"].get("total_return") if r["metrics"] else None
        if bnh is not None and total_ret is not None:
            r["alpha_vs_benchmark"] = round(total_ret - bnh, 2)
        else:
            r["alpha_vs_benchmark"] = None

    return {
        "status": "ok",
        "period": f"{start_date} ~ {end_date}",
        "comparison": results,
        "best_mode": best_mode["mode"] if best_mode else None,
        "best_metrics": best_mode["metrics"] if best_mode else None,
        "best_risk_adjusted": best_sharpe["mode"] if best_sharpe else None,
        "best_sortino": best_sortino["mode"] if best_sortino else None,
        "best_drawdown": best_drawdown["mode"] if best_drawdown else None,
        "benchmark_return": results[0].get("benchmark_return") if results else None,
    }


# ── Endpoint 3: POST /ai-strategy ──

@router.post("/ai-strategy")
async def generate_soxl_strategy(req: SoxlBacktestRequest = None):
    """Generate AI-driven optimal SOXL strategy from backtest + current data."""
    from app.config import settings

    if not getattr(settings, "LLM_API_KEY", None):
        raise HTTPException(503, "LLM API 키가 설정되지 않았습니다.")

    from app.database.connection import get_db
    db = await get_db()

    try:
        # 1. Get recent backtest results
        cursor = await db.execute(
            """SELECT backtest_id, mode, hit_rate, avg_return, sharpe_ratio,
                      max_drawdown, profit_factor, total_return, leverage_decay_total,
                      start_date, end_date, total_trades
               FROM soxl_backtest_runs
               WHERE status='completed'
               ORDER BY created_at DESC LIMIT 8"""
        )
        bt_rows = await cursor.fetchall()
        backtest_summary = [
            {
                "mode": r[1], "hit_rate": r[2], "avg_return": r[3],
                "sharpe": r[4], "max_dd": r[5], "profit_factor": r[6],
                "total_return": r[7], "decay": r[8],
                "period": f"{r[9]}~{r[10]}", "trades": r[11],
            }
            for r in bt_rows
        ]

        # 2. Get winning/losing trade patterns from most recent run
        trade_patterns = {"winners": [], "losers": []}
        trade_streaks = {"max_consecutive_wins": 0, "max_consecutive_losses": 0}
        if bt_rows:
            best_id = bt_rows[0][0]
            cursor = await db.execute(
                """SELECT entry_rsi, entry_vix, entry_macro_score, entry_geo_score,
                          return_pct, return_pct_with_decay, holding_days, exit_reason,
                          position_size_mult
                   FROM soxl_backtest_trades WHERE backtest_id=?
                   ORDER BY return_pct DESC""",
                (best_id,),
            )
            trades = await cursor.fetchall()
            for t in trades[:5]:
                trade_patterns["winners"].append({
                    "rsi": t[0], "vix": t[1], "macro": t[2], "geo": t[3],
                    "return": t[4], "return_with_decay": t[5],
                    "days": t[6], "exit": t[7], "pos_mult": t[8],
                })
            for t in trades[-5:]:
                trade_patterns["losers"].append({
                    "rsi": t[0], "vix": t[1], "macro": t[2], "geo": t[3],
                    "return": t[4], "return_with_decay": t[5],
                    "days": t[6], "exit": t[7], "pos_mult": t[8],
                })

            # [NEW] Win/loss streak analysis
            all_returns = [t[4] for t in trades if t[4] is not None]
            cur_w, cur_l, max_w, max_l = 0, 0, 0, 0
            for r in sorted(trades, key=lambda x: x[6] or 0):  # by holding days as proxy for date
                if (r[4] or 0) > 0:
                    cur_w += 1; cur_l = 0; max_w = max(max_w, cur_w)
                else:
                    cur_l += 1; cur_w = 0; max_l = max(max_l, cur_l)
            trade_streaks = {"max_consecutive_wins": max_w, "max_consecutive_losses": max_l}

        # 3. Gather current market context
        current_ctx = await _gather_current_context(db)

        # 4. Build prompt
        try:
            from app.routers.geopolitical import SEMICONDUCTOR_RISKS, KEY_VARIABLES
        except ImportError:
            SEMICONDUCTOR_RISKS, KEY_VARIABLES = [], []

        prompt = _build_strategy_prompt(
            backtest_summary, trade_patterns, current_ctx,
            SEMICONDUCTOR_RISKS, KEY_VARIABLES, trade_streaks,
        )

        # 5. Call LLM
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
        msg = await client.messages.create(
            model=settings.LLM_MODEL or "claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        strategy_text = msg.content[0].text.strip()

        return {
            "status": "ok",
            "strategy": strategy_text,
            "backtest_summary": backtest_summary[:4],
            "current_context": current_ctx,
            "trade_streaks": trade_streaks,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": settings.LLM_MODEL or "claude-sonnet-4-20250514",
        }

    except Exception as e:
        logger.error("AI strategy generation failed: %s", e, exc_info=True)
        raise HTTPException(500, f"전략 생성 실패: {str(e)}")


async def _gather_current_context(db) -> dict:
    """Gather current market context from DB for AI strategy prompt."""
    ctx = {}

    # Current price + recent performance
    try:
        cursor = await db.execute(
            """SELECT close, trade_date FROM price_history
               WHERE symbol='SOXL' AND market='US'
               ORDER BY trade_date DESC LIMIT 5"""
        )
        rows = await cursor.fetchall()
        if rows:
            ctx["price"] = rows[0][0]
            ctx["price_date"] = rows[0][1]
            # [NEW] Recent price change
            if len(rows) >= 2:
                ctx["price_1d_change"] = round((rows[0][0] - rows[1][0]) / rows[1][0] * 100, 2) if rows[1][0] else None
            if len(rows) >= 5:
                ctx["price_5d_change"] = round((rows[0][0] - rows[4][0]) / rows[4][0] * 100, 2) if rows[4][0] else None
    except Exception:
        pass

    # Macro indicators
    try:
        cursor = await db.execute(
            """SELECT vix, dxy_index, us_10y_yield, us_2y_yield, us_yield_spread,
                      wti_crude, gold_price, fear_greed_index, copper_price, usd_krw
               FROM macro_indicators ORDER BY indicator_date DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            ctx["macro"] = {
                "vix": row[0], "dxy": row[1], "us_10y": row[2], "us_2y": row[3],
                "yield_spread": row[4], "wti": row[5], "gold": row[6],
                "fear_greed": row[7], "copper": row[8], "usd_krw": row[9],
            }
    except Exception:
        pass

    # Latest signal
    try:
        cursor = await db.execute(
            """SELECT final_signal, raw_score, confidence
               FROM signals WHERE symbol='SOXL'
               ORDER BY signal_date DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            ctx["signal"] = {"signal": row[0], "score": row[1], "confidence": row[2]}
    except Exception:
        pass

    # Recent geo events
    try:
        cursor = await db.execute(
            """SELECT event_date, event_text, impact
               FROM geopolitical_events
               ORDER BY event_date DESC LIMIT 5"""
        )
        rows = await cursor.fetchall()
        ctx["geo_events"] = [
            {"date": r[0], "event": r[1], "impact": r[2]} for r in rows
        ]
    except Exception:
        pass

    # [NEW] 52-week high/low
    try:
        cursor = await db.execute(
            """SELECT MAX(high), MIN(low) FROM price_history
               WHERE symbol='SOXL' AND market='US'
               AND trade_date >= date('now', '-365 days')"""
        )
        row = await cursor.fetchone()
        if row and row[0]:
            ctx["week52_high"] = row[0]
            ctx["week52_low"] = row[1]
            if ctx.get("price") and row[0]:
                ctx["pct_from_52w_high"] = round((ctx["price"] - row[0]) / row[0] * 100, 2)
    except Exception:
        pass

    return ctx


def _build_strategy_prompt(backtest_summary, trade_patterns, current_ctx,
                           semi_risks, key_vars, trade_streaks=None):
    """Build LLM prompt for optimal strategy generation."""
    sections = []

    sections.append(
        "당신은 SOXL(3x 레버리지 반도체 ETF) 트레이딩 전략 설계 전문가입니다.\n"
        "아래 백테스트 결과와 현재 시장 데이터를 종합하여 최적의 SOXL 트레이딩 전략을 한국어로 제안해주세요.\n"
        "투자 조언이 아닌 데이터 기반 전략 해설입니다.\n"
        "반드시 구체적 수치(RSI, VIX, 포지션 비중 등)를 포함하고, "
        "3x 레버리지 ETF의 일일 리밸런싱 decay를 고려해주세요."
    )

    # Backtest results
    if backtest_summary:
        bt_lines = []
        for bt in backtest_summary[:4]:
            if isinstance(bt.get('hit_rate'), (int, float)):
                bt_lines.append(
                    f"  모드 {bt['mode']}: 적중률={bt['hit_rate']:.1%}, "
                    f"총수익={bt.get('total_return', 0):.1%}, "
                    f"샤프={bt.get('sharpe', 0):.2f}, "
                    f"최대DD={bt.get('max_dd', 0):.1%}, "
                    f"Decay={bt.get('decay', 0):.1f}%, "
                    f"PF={bt.get('profit_factor', 0):.2f}, "
                    f"거래수={bt.get('trades', 0)}"
                )
            else:
                bt_lines.append(f"  모드 {bt['mode']}: 데이터 부족")
        sections.append("[백테스트 결과 (모드 비교)]\n" + "\n".join(bt_lines))

    # [NEW] Win/loss streaks
    if trade_streaks:
        sections.append(
            f"[연속 승패 패턴]\n"
            f"  최대 연승: {trade_streaks.get('max_consecutive_wins', 0)}연승\n"
            f"  최대 연패: {trade_streaks.get('max_consecutive_losses', 0)}연패"
        )

    # Trade patterns
    if trade_patterns.get("winners"):
        w_lines = [
            f"  RSI={t.get('rsi', '?')}, VIX={t.get('vix', '?')}, "
            f"Macro={t.get('macro', '?')}, Geo={t.get('geo', '?')}, "
            f"수익={_safe_fmt(t.get('return'), '.1f')}%, "
            f"w/Decay={_safe_fmt(t.get('return_with_decay'), '.1f')}%, "
            f"보유={t.get('days', '?')}일, 퇴출={t.get('exit', '?')}"
            for t in trade_patterns["winners"]
        ]
        sections.append("[최고 수익 트레이드]\n" + "\n".join(w_lines))

    if trade_patterns.get("losers"):
        l_lines = [
            f"  RSI={t.get('rsi', '?')}, VIX={t.get('vix', '?')}, "
            f"Macro={t.get('macro', '?')}, Geo={t.get('geo', '?')}, "
            f"수익={_safe_fmt(t.get('return'), '.1f')}%, "
            f"보유={t.get('days', '?')}일, 퇴출={t.get('exit', '?')}"
            for t in trade_patterns["losers"]
        ]
        sections.append("[최악 손실 트레이드]\n" + "\n".join(l_lines))

    # Current context
    macro = current_ctx.get("macro", {})
    sig = current_ctx.get("signal", {})
    geo = current_ctx.get("geo_events", [])
    ctx_text = (
        f"현재가: ${current_ctx.get('price', '?')} ({current_ctx.get('price_date', '')})\n"
        f"1일 변동: {_safe_fmt(current_ctx.get('price_1d_change'), '+.2f')}%, "
        f"5일 변동: {_safe_fmt(current_ctx.get('price_5d_change'), '+.2f')}%\n"
        f"52주 고가: ${_safe_fmt(current_ctx.get('week52_high'), '.2f')}, "
        f"52주 저가: ${_safe_fmt(current_ctx.get('week52_low'), '.2f')}, "
        f"고점 대비: {_safe_fmt(current_ctx.get('pct_from_52w_high'), '.1f')}%\n"
        f"VIX: {macro.get('vix', '?')}, DXY: {macro.get('dxy', '?')}\n"
        f"US10Y: {macro.get('us_10y', '?')}%, US2Y: {macro.get('us_2y', '?')}%\n"
        f"Yield Spread: {macro.get('yield_spread', '?')}%\n"
        f"WTI: ${macro.get('wti', '?')}, Gold: ${macro.get('gold', '?')}, Copper: ${macro.get('copper', '?')}\n"
        f"USD/KRW: {macro.get('usd_krw', '?')}\n"
        f"Fear&Greed: {macro.get('fear_greed', '?')}\n"
        f"최신 시그널: {sig.get('signal', '?')} (점수={sig.get('score', '?')}, 신뢰도={sig.get('confidence', '?')})\n"
        f"최근 지정학 이벤트: {len(geo)}건"
    )
    if geo:
        for e in geo[:5]:
            ctx_text += f"\n  - [{e.get('date')}] ({e.get('impact')}) {e.get('event')}"
    sections.append(f"[현재 시장 상황]\n{ctx_text}")

    # Semiconductor risks
    if semi_risks:
        r_lines = [f"- [{r['severity']}] {r['risk']}: {r['detail']}" for r in semi_risks[:5]]
        sections.append("[반도체 섹터 리스크]\n" + "\n".join(r_lines))

    # Key variables
    if key_vars:
        k_lines = [
            f"- {k['variable']}: 현재={k['current']}, 긍정={k['bullish']}, 부정={k['bearish']}"
            for k in key_vars
        ]
        sections.append("[핵심 변수]\n" + "\n".join(k_lines))

    # Strategy request
    sections.append(
        "[전략 생성 요청]\n"
        "위 백테스트 결과와 현재 시장 데이터를 종합하여 다음을 제안해주세요:\n\n"
        "1. **최적 전략 모드**: A/B/C/D 중 현재 환경에 적합한 모드와 근거\n"
        "2. **최적 진입 조건**: RSI, MACD, StochRSI, ADX, VIX, 매크로 점수, BB 기준값\n"
        "3. **최적 퇴출 조건**: 손절/익절/트레일링 스탑/ATR 스탑/시간 기준\n"
        "4. **포지션 사이징**: 현재 VIX/변동성/지정학 고려한 적정 비중 (구체적 %, Kelly 기준)\n"
        "5. **리스크 관리**: 현재 환경의 핵심 위험과 헤지 방안 (SOXS, 현금, 연패 대응)\n"
        "6. **시나리오 분석**: 낙관/중립/비관 시나리오별 예상 수익률과 확률\n"
        "7. **보유 기간 권고**: 레버리지 decay 최소화를 위한 최적 보유 기간\n"
        "8. **현재 진입 적정성**: 52주 위치, 최근 모멘텀 기반 진입 타이밍 판단\n\n"
        "- 3x 레버리지 ETF의 일일 리밸런싱 decay 고려 필수\n"
        "- 백테스트에서 확인된 승패 패턴, 연승/연패 패턴을 근거로 구체적 수치 제시\n"
        "- Sortino, Calmar ratio 등 risk-adjusted 메트릭 참조\n"
        "- 한국어로 작성 (마크다운 형식)"
    )

    return "\n\n".join(sections)


def _safe_fmt(value, fmt=".1f"):
    """Safely format a numeric value."""
    if value is None:
        return "?"
    try:
        return f"{value:{fmt}}"
    except (TypeError, ValueError):
        return str(value)


# ── Endpoint 4: GET /results ──

@router.get("/results")
async def get_soxl_backtest_results(
    limit: int = Query(10, ge=1, le=50),
    mode: str | None = Query(None, description="Filter by mode (A/B/C/D)"),
    status: str | None = Query(None, description="Filter by status (completed/failed)"),
):
    """List recent SOXL backtest runs with optional mode and status filter."""
    from app.database.connection import get_db
    db = await get_db()

    conditions = []
    params_list = []
    if mode:
        conditions.append("mode=?")
        params_list.append(mode.upper())
    if status:
        conditions.append("status=?")
        params_list.append(status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params_list.append(limit)

    cursor = await db.execute(
        f"""SELECT backtest_id, start_date, end_date, mode, status,
                  total_trades, hit_rate, avg_return, sharpe_ratio,
                  max_drawdown, total_return, leverage_decay_total, created_at
           FROM soxl_backtest_runs
           {where}
           ORDER BY created_at DESC LIMIT ?""",
        params_list,
    )
    rows = await cursor.fetchall()
    return {
        "results": [
            {
                "backtest_id": r[0], "start_date": r[1], "end_date": r[2],
                "mode": r[3], "mode_label": _MODE_LABELS.get(r[3], r[3]),
                "status": r[4], "total_trades": r[5],
                "hit_rate": r[6], "avg_return": r[7], "sharpe_ratio": r[8],
                "max_drawdown": r[9], "total_return": r[10],
                "leverage_decay_total": r[11], "created_at": r[12],
            }
            for r in rows
        ]
    }


# ── Endpoint 5: GET /results/{backtest_id} ──

@router.get("/results/{backtest_id}")
async def get_soxl_backtest_detail(backtest_id: str):
    """Get detailed SOXL backtest results with trades and equity curve."""
    from app.database.connection import get_db
    db = await get_db()

    cursor = await db.execute(
        """SELECT backtest_id, start_date, end_date, mode, params_json, status,
                  total_trades, hit_rate, avg_return, sharpe_ratio,
                  max_drawdown, profit_factor, total_return, leverage_decay_total,
                  equity_curve_json, created_at
           FROM soxl_backtest_runs WHERE backtest_id=?""",
        (backtest_id,),
    )
    run = await cursor.fetchone()
    if not run:
        raise HTTPException(404, "백테스트를 찾을 수 없습니다.")

    cursor = await db.execute(
        """SELECT entry_date, entry_price, entry_signal, entry_score,
                  entry_rsi, entry_vix, entry_macro_score, entry_geo_score,
                  exit_date, exit_price, exit_reason,
                  return_pct, return_pct_with_decay, holding_days, position_size_mult
           FROM soxl_backtest_trades WHERE backtest_id=?
           ORDER BY entry_date ASC""",
        (backtest_id,),
    )
    trades = [
        {
            "entry_date": t[0], "entry_price": t[1], "entry_signal": t[2],
            "entry_score": t[3], "entry_rsi": t[4], "entry_vix": t[5],
            "entry_macro_score": t[6], "entry_geo_score": t[7],
            "exit_date": t[8], "exit_price": t[9], "exit_reason": t[10],
            "return_pct": t[11], "return_pct_with_decay": t[12],
            "holding_days": t[13], "position_size_mult": t[14],
        }
        for t in await cursor.fetchall()
    ]

    # [NEW] Compute exit reason stats from trades
    from app.backtesting.metrics import compute_exit_reason_stats, compute_monthly_returns
    exit_stats = compute_exit_reason_stats(trades)
    monthly_returns = compute_monthly_returns(trades)

    return {
        "backtest_id": run[0],
        "start_date": run[1], "end_date": run[2],
        "mode": run[3],
        "mode_label": _MODE_LABELS.get(run[3], run[3]),
        "params": json.loads(run[4]) if run[4] else {},
        "status": run[5],
        "metrics": {
            "total_trades": run[6], "hit_rate": run[7], "avg_return": run[8],
            "sharpe_ratio": run[9], "max_drawdown": run[10],
            "profit_factor": run[11], "total_return": run[12],
        },
        "leverage_decay_total": run[13],
        "equity_curve": json.loads(run[14]) if run[14] else [],
        "trades": trades,
        "exit_reason_stats": exit_stats,
        "monthly_returns": monthly_returns,
        "created_at": run[15],
    }


# ── Endpoint 6: DELETE /results ──

@router.delete("/results")
async def cleanup_soxl_backtests(keep: int = Query(20, ge=1, le=100)):
    """Delete old backtest runs, keeping the most recent N."""
    from app.database.connection import get_db
    db = await get_db()

    cursor = await db.execute(
        """SELECT backtest_id FROM soxl_backtest_runs
           ORDER BY created_at DESC LIMIT -1 OFFSET ?""",
        (keep,),
    )
    old_ids = [r[0] for r in await cursor.fetchall()]

    if not old_ids:
        return {"status": "ok", "deleted": 0}

    placeholders = ",".join("?" * len(old_ids))
    await db.execute(f"DELETE FROM soxl_backtest_trades WHERE backtest_id IN ({placeholders})", old_ids)
    await db.execute(f"DELETE FROM soxl_backtest_runs WHERE backtest_id IN ({placeholders})", old_ids)
    await db.commit()

    logger.info("Cleaned up %d old SOXL backtest runs", len(old_ids))
    return {"status": "ok", "deleted": len(old_ids)}


# ── Endpoint 7: GET /presets ──

@router.get("/presets")
async def get_parameter_presets():
    """List available parameter presets with their values."""
    presets = {}
    for name, overrides in PARAM_PRESETS.items():
        params = SoxlBacktestParams()
        for k, v in overrides.items():
            if hasattr(params, k):
                setattr(params, k, v)
        from dataclasses import asdict
        presets[name] = asdict(params)
    return {"presets": presets}


# ── Endpoint 8: GET /stats/{backtest_id} ──

@router.get("/stats/{backtest_id}")
async def get_soxl_backtest_stats(backtest_id: str):
    """Get extended trade statistics for a backtest run."""
    from app.database.connection import get_db
    db = await get_db()

    cursor = await db.execute(
        "SELECT status FROM soxl_backtest_runs WHERE backtest_id=?", (backtest_id,)
    )
    run = await cursor.fetchone()
    if not run:
        raise HTTPException(404, "백테스트를 찾을 수 없습니다.")

    cursor = await db.execute(
        """SELECT entry_date, entry_price, entry_rsi, entry_vix,
                  entry_macro_score, entry_geo_score,
                  exit_date, exit_price, exit_reason,
                  return_pct, return_pct_with_decay, holding_days, position_size_mult
           FROM soxl_backtest_trades WHERE backtest_id=?
           ORDER BY entry_date ASC""",
        (backtest_id,),
    )
    raw_trades = await cursor.fetchall()
    trades = [
        {
            "entry_date": t[0], "entry_price": t[1], "entry_rsi": t[2],
            "entry_vix": t[3], "entry_macro_score": t[4], "entry_geo_score": t[5],
            "exit_date": t[6], "exit_price": t[7], "exit_reason": t[8],
            "return_pct": t[9], "return_pct_with_decay": t[10],
            "holding_days": t[11], "position_size_mult": t[12],
        }
        for t in raw_trades
    ]

    from app.backtesting.metrics import (
        compute_backtest_metrics,
        compute_drawdown_periods,
        compute_exit_reason_stats,
        compute_monthly_returns,
    )

    metrics = compute_backtest_metrics(trades)
    monthly = compute_monthly_returns(trades)
    exit_stats = compute_exit_reason_stats(trades)
    drawdowns = compute_drawdown_periods(trades)

    # [NEW] Return distribution buckets
    returns = [t["return_pct"] for t in trades if t.get("return_pct") is not None]
    distribution = _compute_return_distribution(returns)

    # [NEW] Holding days distribution
    holding_dist = _compute_holding_distribution(trades)

    # [NEW] Win rate by entry RSI range
    rsi_analysis = _compute_rsi_win_rate(trades)

    return {
        "backtest_id": backtest_id,
        "metrics": metrics,
        "monthly_returns": monthly,
        "exit_reason_stats": exit_stats,
        "drawdown_periods": drawdowns,
        "return_distribution": distribution,
        "holding_days_distribution": holding_dist,
        "rsi_win_rate_analysis": rsi_analysis,
    }


def _compute_return_distribution(returns: list[float]) -> list[dict]:
    """Bucket returns into distribution ranges."""
    if not returns:
        return []
    buckets = [
        ("<-10%", -999, -10), ("-10~-5%", -10, -5), ("-5~-2%", -5, -2),
        ("-2~0%", -2, 0), ("0~2%", 0, 2), ("2~5%", 2, 5),
        ("5~10%", 5, 10), ("10~20%", 10, 20), (">20%", 20, 999),
    ]
    result = []
    for label, lo, hi in buckets:
        count = sum(1 for r in returns if lo <= r < hi)
        result.append({"range": label, "count": count})
    return result


def _compute_holding_distribution(trades: list[dict]) -> list[dict]:
    """Bucket holding days into distribution ranges."""
    if not trades:
        return []
    buckets = [
        ("1-3일", 1, 4), ("4-7일", 4, 8), ("8-14일", 8, 15),
        ("15-20일", 15, 21), ("21일+", 21, 999),
    ]
    result = []
    for label, lo, hi in buckets:
        count = sum(1 for t in trades if lo <= (t.get("holding_days") or 0) < hi)
        result.append({"range": label, "count": count})
    return result


def _compute_rsi_win_rate(trades: list[dict]) -> list[dict]:
    """Compute win rate grouped by entry RSI ranges."""
    if not trades:
        return []
    ranges = [
        ("RSI≤25", 0, 26), ("RSI 26-30", 26, 31), ("RSI 31-35", 31, 36),
        ("RSI 36-40", 36, 41), ("RSI 41-50", 41, 51), ("RSI>50", 51, 101),
    ]
    result = []
    for label, lo, hi in ranges:
        group = [t for t in trades if t.get("entry_rsi") is not None and lo <= t["entry_rsi"] < hi]
        if group:
            wins = sum(1 for t in group if (t.get("return_pct") or 0) > 0)
            avg_ret = sum(t.get("return_pct", 0) for t in group) / len(group)
            result.append({
                "range": label, "count": len(group),
                "win_rate": round(wins / len(group), 4),
                "avg_return": round(avg_ret, 2),
            })
    return result


# ── Endpoint 9: GET /export/{backtest_id} ──

@router.get("/export/{backtest_id}")
async def export_soxl_backtest_csv(backtest_id: str):
    """Export backtest trades as CSV file."""
    from app.database.connection import get_db
    db = await get_db()

    cursor = await db.execute(
        "SELECT mode, start_date, end_date FROM soxl_backtest_runs WHERE backtest_id=?",
        (backtest_id,),
    )
    run = await cursor.fetchone()
    if not run:
        raise HTTPException(404, "백테스트를 찾을 수 없습니다.")

    cursor = await db.execute(
        """SELECT entry_date, entry_price, entry_rsi, entry_vix,
                  entry_macro_score, entry_geo_score,
                  exit_date, exit_price, exit_reason,
                  return_pct, return_pct_with_decay, holding_days, position_size_mult
           FROM soxl_backtest_trades WHERE backtest_id=?
           ORDER BY entry_date ASC""",
        (backtest_id,),
    )
    trades = await cursor.fetchall()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Entry Date", "Entry Price", "Entry RSI", "Entry VIX",
        "Macro Score", "Geo Score",
        "Exit Date", "Exit Price", "Exit Reason",
        "Return %", "Return w/Decay %", "Holding Days", "Position Mult",
    ])
    for t in trades:
        writer.writerow(t)

    output.seek(0)
    filename = f"soxl_backtest_{run[0]}_{run[1]}_{run[2]}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
