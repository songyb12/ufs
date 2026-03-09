"""
SOXL Dedicated Dashboard Router

Provides SOXL-specific price data, technicals, signals, and trading strategy info.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Query

router = APIRouter(prefix="/soxl", tags=["soxl"])
logger = logging.getLogger("vibe.soxl")


@router.get("/dashboard")
async def soxl_dashboard(days: int = Query(90, ge=7, le=365)):
    """Complete SOXL dashboard data: price, technicals, signals, strategy."""
    from app.database.connection import get_db
    import math

    db = await get_db()

    # 1. Price history
    cursor = await db.execute(
        """SELECT trade_date, open, high, low, close, volume
           FROM price_history
           WHERE symbol='SOXL' AND market='US'
           ORDER BY trade_date DESC
           LIMIT ?""",
        (days,),
    )
    rows = await cursor.fetchall()
    prices = [
        {
            "date": r[0], "open": r[1], "high": r[2],
            "low": r[3], "close": r[4], "volume": r[5],
        }
        for r in rows
    ]
    prices.reverse()

    # 2. Latest technicals
    cursor = await db.execute(
        """SELECT rsi_14, ma_5, ma_20, ma_60, macd, macd_signal,
                  bollinger_upper, bollinger_middle, bollinger_lower, volume_ratio,
                  disparity_20, created_at
           FROM technical_indicators
           WHERE symbol='SOXL' AND market='US'
           ORDER BY created_at DESC LIMIT 1"""
    )
    tech_row = await cursor.fetchone()
    technicals = None
    if tech_row:
        technicals = {
            "rsi_14": tech_row[0],
            "ma_5": tech_row[1],
            "ma_20": tech_row[2],
            "ma_60": tech_row[3],
            "macd": tech_row[4],
            "macd_signal": tech_row[5],
            "bb_upper": tech_row[6],
            "bb_middle": tech_row[7],
            "bb_lower": tech_row[8],
            "volume_ratio": tech_row[9],
            "disparity_20": tech_row[10],
            "updated_at": tech_row[11],
        }

    # 3. Recent signals
    cursor = await db.execute(
        """SELECT signal_date, raw_signal, final_signal, raw_score,
                  confidence, rationale, hard_limit_triggered
           FROM signals
           WHERE symbol='SOXL' AND market='US'
           ORDER BY signal_date DESC
           LIMIT 30"""
    )
    sig_rows = await cursor.fetchall()
    signals = [
        {
            "date": r[0], "raw_signal": r[1], "final_signal": r[2],
            "raw_score": r[3], "confidence": r[4],
            "rationale": r[5], "hard_limit": bool(r[6]),
        }
        for r in sig_rows
    ]

    # 4. Price performance metrics
    perf = _calc_performance(prices)

    # 5. Trading strategy (static + dynamic)
    strategy = _build_strategy(technicals, perf)

    return {
        "symbol": "SOXL",
        "name": "Direxion Daily Semiconductor Bull 3X Shares",
        "asset_type": "3x Leveraged ETF",
        "underlying": "ICE Semiconductor Index",
        "prices": prices,
        "technicals": technicals,
        "signals": signals,
        "performance": perf,
        "strategy": strategy,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/levels")
async def soxl_levels():
    """Key support/resistance levels and trading zones."""
    from app.database.connection import get_db

    db = await get_db()
    cursor = await db.execute(
        """SELECT trade_date, high, low, close, volume
           FROM price_history
           WHERE symbol='SOXL' AND market='US'
           ORDER BY trade_date DESC
           LIMIT 120"""
    )
    rows = await cursor.fetchall()
    if not rows:
        return {"levels": [], "zones": []}

    closes = [r[3] for r in rows if r[3] is not None]
    highs = [r[1] for r in rows if r[1] is not None]
    lows = [r[2] for r in rows if r[2] is not None]
    volumes = [r[4] for r in rows if r[4] is not None]

    if not closes:
        return {"levels": [], "zones": []}

    current = closes[0]
    high_52w = max(highs) if highs else current
    low_52w = min(lows) if lows else current

    # Fibonacci levels from 52-week range
    diff = high_52w - low_52w
    fib_levels = {
        "52w_high": round(high_52w, 2),
        "fib_786": round(low_52w + diff * 0.786, 2),
        "fib_618": round(low_52w + diff * 0.618, 2),
        "fib_500": round(low_52w + diff * 0.5, 2),
        "fib_382": round(low_52w + diff * 0.382, 2),
        "fib_236": round(low_52w + diff * 0.236, 2),
        "52w_low": round(low_52w, 2),
    }

    # Recent support/resistance (20-day pivots)
    recent_20 = closes[:20]
    pivot = (max(recent_20) + min(recent_20) + recent_20[0]) / 3
    r1 = 2 * pivot - min(recent_20)
    s1 = 2 * pivot - max(recent_20)
    r2 = pivot + (max(recent_20) - min(recent_20))
    s2 = pivot - (max(recent_20) - min(recent_20))

    pivot_levels = {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
    }

    # Position vs levels
    pct_from_high = round((current - high_52w) / high_52w * 100, 1) if high_52w else 0
    pct_from_low = round((current - low_52w) / low_52w * 100, 1) if low_52w else 0

    return {
        "current_price": round(current, 2),
        "fibonacci": fib_levels,
        "pivot_points": pivot_levels,
        "position": {
            "pct_from_52w_high": pct_from_high,
            "pct_from_52w_low": pct_from_low,
        },
    }


def _calc_performance(prices: list) -> dict:
    """Calculate various return periods."""
    if len(prices) < 2:
        return {}

    current = prices[-1]["close"] if prices else None
    if current is None:
        return {}

    def _pct(idx):
        if idx < len(prices) and prices[-(idx + 1)]["close"]:
            old = prices[-(idx + 1)]["close"]
            return round((current - old) / old * 100, 2) if old else None
        return None

    # Volume stats
    vols = [p["volume"] for p in prices if p.get("volume")]
    avg_vol_20 = round(sum(vols[-20:]) / min(len(vols[-20:]), 20)) if vols else None
    latest_vol = vols[-1] if vols else None

    # Daily return volatility (last 20 days)
    daily_returns = []
    for i in range(max(0, len(prices) - 20), len(prices)):
        if i > 0 and prices[i]["close"] and prices[i - 1]["close"]:
            ret = (prices[i]["close"] - prices[i - 1]["close"]) / prices[i - 1]["close"]
            daily_returns.append(ret)

    import math
    volatility_20d = None
    if daily_returns:
        mean = sum(daily_returns) / len(daily_returns)
        var = sum((r - mean) ** 2 for r in daily_returns) / len(daily_returns)
        volatility_20d = round(math.sqrt(var) * math.sqrt(252) * 100, 1)  # annualized

    return {
        "current_price": current,
        "change_1d": _pct(1),
        "change_5d": _pct(5),
        "change_20d": _pct(20),
        "change_60d": _pct(60),
        "avg_volume_20d": avg_vol_20,
        "latest_volume": latest_vol,
        "volatility_20d_ann": volatility_20d,
    }


def _build_strategy(technicals: dict | None, perf: dict) -> dict:
    """Build SOXL-specific trading strategy recommendations."""
    rsi = technicals.get("rsi_14") if technicals else None
    disparity = technicals.get("disparity_20") if technicals else None
    macd = technicals.get("macd") if technicals else None
    macd_sig = technicals.get("macd_signal") if technicals else None
    vol_ratio = technicals.get("volume_ratio") if technicals else None
    volatility = perf.get("volatility_20d_ann")

    # Determine market condition
    conditions = []
    buy_signals = 0
    sell_signals = 0

    if rsi is not None:
        if rsi < 30:
            conditions.append({"indicator": "RSI", "value": round(rsi, 1), "signal": "OVERSOLD", "desc": "RSI 30 미만 — 과매도 영역, 기술적 반등 가능성"})
            buy_signals += 2
        elif rsi < 40:
            conditions.append({"indicator": "RSI", "value": round(rsi, 1), "signal": "APPROACHING_OVERSOLD", "desc": "RSI 40 미만 — 매수 관심 구간 진입"})
            buy_signals += 1
        elif rsi > 70:
            conditions.append({"indicator": "RSI", "value": round(rsi, 1), "signal": "OVERBOUGHT", "desc": "RSI 70 초과 — 과매수 영역, 차익실현 고려"})
            sell_signals += 2
        elif rsi > 60:
            conditions.append({"indicator": "RSI", "value": round(rsi, 1), "signal": "APPROACHING_OVERBOUGHT", "desc": "RSI 60 초과 — 매도 준비 구간"})
            sell_signals += 1
        else:
            conditions.append({"indicator": "RSI", "value": round(rsi, 1), "signal": "NEUTRAL", "desc": f"RSI {round(rsi, 1)} — 중립 구간"})

    if macd is not None and macd_sig is not None:
        if macd > macd_sig:
            conditions.append({"indicator": "MACD", "value": round(macd - macd_sig, 3), "signal": "BULLISH", "desc": "MACD 골든크로스 — 상승 모멘텀"})
            buy_signals += 1
        else:
            conditions.append({"indicator": "MACD", "value": round(macd - macd_sig, 3), "signal": "BEARISH", "desc": "MACD 데드크로스 — 하락 모멘텀"})
            sell_signals += 1

    if disparity is not None:
        if disparity > 110:
            conditions.append({"indicator": "Disparity", "value": round(disparity, 1), "signal": "OVEREXTENDED", "desc": f"이격도 {round(disparity, 1)}% — 20MA 대비 과열, 조정 가능성"})
            sell_signals += 1
        elif disparity < 90:
            conditions.append({"indicator": "Disparity", "value": round(disparity, 1), "signal": "UNDEREXTENDED", "desc": f"이격도 {round(disparity, 1)}% — 20MA 대비 이탈, 반등 가능성"})
            buy_signals += 1

    if vol_ratio is not None:
        if vol_ratio > 2.0:
            conditions.append({"indicator": "Volume", "value": round(vol_ratio, 2), "signal": "HIGH_VOLUME", "desc": f"거래량 비율 {round(vol_ratio, 2)}x — 평균 대비 급증 (추세 확인)"})
        elif vol_ratio < 0.5:
            conditions.append({"indicator": "Volume", "value": round(vol_ratio, 2), "signal": "LOW_VOLUME", "desc": f"거래량 비율 {round(vol_ratio, 2)}x — 평균 대비 감소 (관망)"})

    # Overall stance
    if buy_signals >= 3:
        stance = "STRONG_BUY"
        stance_desc = "강력 매수 신호 — 다중 지표 매수 컨버전스"
    elif buy_signals >= 2:
        stance = "BUY"
        stance_desc = "매수 유리 — 기술적 지표 다수 매수 방향"
    elif sell_signals >= 3:
        stance = "STRONG_SELL"
        stance_desc = "강력 매도 신호 — 다중 지표 매도 컨버전스"
    elif sell_signals >= 2:
        stance = "SELL"
        stance_desc = "매도 유리 — 기술적 지표 다수 매도 방향"
    else:
        stance = "HOLD"
        stance_desc = "관망 — 명확한 방향성 없음"

    # SOXL-specific risk warnings
    risk_warnings = [
        "3x 레버리지 ETF: 일일 리밸런싱으로 장기 보유 시 감쇠(decay) 발생",
        "반도체 섹터 집중 리스크 — 단일 섹터 100% 노출",
    ]
    if volatility and volatility > 80:
        risk_warnings.append(f"현재 연환산 변동성 {volatility}% — 극단적 고변동성 상태")
    if volatility and volatility > 60:
        risk_warnings.append("고변동성 구간: 포지션 사이즈 축소 권장 (통상 대비 50%)")

    # Trading rules
    trading_rules = {
        "entry_rules": [
            {"rule": "RSI < 35 진입", "desc": "RSI 35 미만에서 분할 매수 시작"},
            {"rule": "MACD 골든크로스 확인", "desc": "MACD가 시그널선 상향 돌파 시 진입"},
            {"rule": "20MA 지지 확인", "desc": "20일 이동평균선에서 반등 확인 후 진입"},
            {"rule": "거래량 증가 동반", "desc": "평균 거래량 1.5배 이상 동반 시 신뢰도 상승"},
        ],
        "exit_rules": [
            {"rule": "RSI > 65 차익실현", "desc": "RSI 65 초과 시 단계적 차익실현 시작"},
            {"rule": "이격도 > 108% 경고", "desc": "20MA 대비 8% 이상 괴리 시 부분 청산"},
            {"rule": "MACD 데드크로스", "desc": "MACD가 시그널선 하향 돌파 시 전량 청산 고려"},
            {"rule": "손절 -7%", "desc": "매수가 대비 -7% 도달 시 손절 (3x 레버리지 고려)"},
        ],
        "position_sizing": [
            {"rule": "총 포트폴리오 15% 이내", "desc": "3x 레버리지 특성상 포트폴리오 비중 제한"},
            {"rule": "분할 매수/매도", "desc": "3회 이상 분할하여 진입/청산 (평단가 관리)"},
            {"rule": "고변동성 시 비중 축소", "desc": "VIX 30+ 또는 연환산 변동성 80%+ 시 비중 절반"},
        ],
    }

    return {
        "stance": stance,
        "stance_desc": stance_desc,
        "conditions": conditions,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "risk_warnings": risk_warnings,
        "trading_rules": trading_rules,
    }
