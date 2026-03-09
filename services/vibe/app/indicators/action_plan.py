"""Action Plan Engine — Synthesizes all VIBE data into clear, actionable recommendations.

Goal: "하라는대로만 해도 수익" — Follow instructions → Profit.
Combines signals, macro regime, portfolio state, guru consensus, and risk management
into a prioritized daily action plan.
"""

import math
from datetime import date


# ── Position Sizing ──────────────────────────────────────────────────────

def compute_kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly criterion for position sizing. Returns fraction of capital to bet.

    f* = (p * b - q) / b
    where p = win_rate, q = 1 - p, b = avg_win / avg_loss
    """
    if avg_loss == 0 or win_rate <= 0:
        return 0.0
    b = abs(avg_win / avg_loss)
    q = 1.0 - win_rate
    kelly = (win_rate * b - q) / b
    # Half-Kelly for safety (standard practice)
    return max(0.0, min(0.25, kelly * 0.5))


def recommend_position_size(
    total_capital: float,
    signal_score: float,
    confidence: float,
    max_single_pct: float = 0.10,
    existing_exposure_pct: float = 0.0,
) -> dict:
    """Calculate recommended position size based on signal strength + confidence.

    Returns:
        dict with amount, pct, rationale
    """
    # Base allocation: signal_score maps to 3-10% of capital
    score_factor = min(1.0, abs(signal_score) / 50.0)  # Normalize to 0-1
    conf_factor = (confidence if confidence is not None else 50) / 100.0

    # Combined factor: higher score + higher confidence → larger position
    combined = score_factor * 0.6 + conf_factor * 0.4

    # Scale: 3% (weak) to max_single_pct (strong)
    min_pct = 0.03
    target_pct = min_pct + (max_single_pct - min_pct) * combined

    # Reduce if already exposed to same sector
    if existing_exposure_pct > 0.2:
        target_pct *= 0.5
    elif existing_exposure_pct > 0.1:
        target_pct *= 0.75

    target_pct = round(min(max_single_pct, target_pct), 4)
    amount = round(total_capital * target_pct)

    return {
        "amount": amount,
        "pct": round(target_pct * 100, 1),
        "rationale": _size_rationale(target_pct, score_factor, conf_factor),
    }


def _size_rationale(pct: float, score_f: float, conf_f: float) -> str:
    if pct >= 0.08:
        return "강한 신호 + 높은 확신 → 적극 진입"
    elif pct >= 0.05:
        return "보통 신호 → 기본 비중 진입"
    else:
        return "약한 신호 → 소량 탐색 진입"


# ── Price Target Calculation ─────────────────────────────────────────────

def compute_price_targets(
    current_price: float,
    rsi: float | None,
    signal_type: str,
    ma_20: float | None = None,
    ma_60: float | None = None,
) -> dict:
    """Compute target price and stop-loss based on technicals."""
    if current_price <= 0:
        return {"target": None, "stop_loss": None, "rr_ratio": None, "target_pct": None}

    # Target: based on signal strength
    if signal_type == "BUY":
        # Target: 8-15% upside depending on RSI
        if rsi is not None and rsi < 35:
            target_pct = 0.15  # Oversold → bigger target
        elif rsi is not None and rsi < 45:
            target_pct = 0.12
        else:
            target_pct = 0.08
        target = round(current_price * (1 + target_pct))
        stop_loss = round(current_price * 0.93)  # -7% stop loss
    elif signal_type == "SELL":
        target = round(current_price * 0.92)  # Target -8% (short thesis)
        stop_loss = round(current_price * 1.05)  # +5% stop loss
        target_pct = -0.08
    else:
        # HOLD — use MA-based targets
        target = round(ma_60) if ma_60 else round(current_price * 1.05)
        stop_loss = round(current_price * 0.93)
        target_pct = 0.05

    # Risk-Reward ratio
    risk = abs(current_price - stop_loss)
    reward = abs(target - current_price)
    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        "target": target,
        "stop_loss": stop_loss,
        "rr_ratio": rr,
        "target_pct": round(target_pct * 100, 1),
    }


# ── Portfolio Action Items ───────────────────────────────────────────────

def generate_portfolio_actions(positions: list[dict], signals: list[dict]) -> list[dict]:
    """Generate action items for existing portfolio positions.

    Actions: TAKE_PROFIT, CUT_LOSS, ADD_MORE, WATCH, REDUCE
    """
    signal_map = {s["symbol"]: s for s in signals}
    actions = []

    for pos in positions:
        symbol = pos.get("symbol", "")
        pnl_pct = pos.get("pnl_pct")
        entry_price = pos.get("entry_price", 0)
        current_price = pos.get("current_price")
        position_size = pos.get("position_size", 0)
        signal = signal_map.get(symbol, {})

        if pnl_pct is None or current_price is None:
            continue

        action = _determine_position_action(pnl_pct, signal, pos)
        actions.append({
            "symbol": symbol,
            "name": pos.get("name", symbol),
            "market": pos.get("market", ""),
            "action": action["action"],
            "action_kr": action["action_kr"],
            "urgency": action["urgency"],  # high/medium/low
            "reason_kr": action["reason_kr"],
            "pnl_pct": round(pnl_pct, 2),
            "current_price": current_price,
            "position_size": position_size,
            "signal": signal.get("final_signal", "HOLD"),
            "signal_score": signal.get("raw_score", 0),
        })

    # Sort by urgency (high first) then by abs(pnl)
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda x: (urgency_order.get(x["urgency"], 3), -abs(x.get("pnl_pct", 0))))

    return actions


def _determine_position_action(pnl_pct: float, signal: dict, pos: dict) -> dict:
    """Decide action for a single position."""
    final_signal = signal.get("final_signal", "HOLD")
    raw_score = signal.get("raw_score", 0)
    rsi = signal.get("rsi_value")

    # CUT LOSS: below stop-loss threshold
    if pnl_pct <= -7.0:
        return {
            "action": "CUT_LOSS",
            "action_kr": "🔴 손절",
            "urgency": "high",
            "reason_kr": f"손실 {pnl_pct:.1f}% — 손절선(-7%) 돌파. 즉시 정리 권장.",
        }

    # TAKE PROFIT: big gains
    if pnl_pct >= 15.0:
        return {
            "action": "TAKE_PROFIT",
            "action_kr": "🟢 익절",
            "urgency": "high",
            "reason_kr": f"수익 +{pnl_pct:.1f}% — 목표 수익 달성. 최소 50% 이상 차익 실현 권장.",
        }

    if pnl_pct >= 10.0:
        return {
            "action": "PARTIAL_PROFIT",
            "action_kr": "🟡 부분 익절",
            "urgency": "medium",
            "reason_kr": f"수익 +{pnl_pct:.1f}% — 30-50% 부분 익절로 수익 확보 후 잔여분 보유.",
        }

    # SELL signal on held position
    if final_signal == "SELL":
        return {
            "action": "REDUCE",
            "action_kr": "🟠 비중 축소",
            "urgency": "high",
            "reason_kr": f"매도 시그널(스코어 {raw_score:.1f}) 발생. 비중 50% 이상 축소 권장.",
        }

    # Near stop loss — warning
    if -7.0 < pnl_pct <= -5.0:
        return {
            "action": "WATCH_CLOSELY",
            "action_kr": "⚠️ 주의 관찰",
            "urgency": "medium",
            "reason_kr": f"손실 {pnl_pct:.1f}% — 손절선(-7%) 접근 중. 추가 하락 시 즉시 대응 준비.",
        }

    # BUY signal on existing → ADD
    if final_signal == "BUY" and pnl_pct > -3.0:
        return {
            "action": "ADD_MORE",
            "action_kr": "🔵 추가 매수",
            "urgency": "low",
            "reason_kr": f"매수 시그널(스코어 +{raw_score:.1f}) 지속. 비중 확대 고려.",
        }

    # RSI overbought warning
    if rsi is not None and rsi > 70:
        return {
            "action": "WATCH_OVERBOUGHT",
            "action_kr": "⚠️ 과매수 주의",
            "urgency": "medium",
            "reason_kr": f"RSI {rsi:.0f} — 과매수 구간. 추가 매수 자제, 익절 타이밍 준비.",
        }

    # Default: hold
    return {
        "action": "HOLD",
        "action_kr": "⏳ 보유 유지",
        "urgency": "low",
        "reason_kr": f"현재 P&L {pnl_pct:+.1f}%. 시그널 {final_signal}. 특별한 액션 불필요.",
    }


# ── Daily Strategy Recommendation ────────────────────────────────────────

def generate_daily_strategy(
    macro_data: dict,
    regime: dict,
    season: dict,
    fear_gauge: dict,
    signal_summary: dict,
    guru_consensus: dict | None = None,
) -> dict:
    """Generate a daily overall strategy recommendation.

    Returns:
        dict with stance, cash_ratio, sector_bias, action_items, weekly_outlook
    """
    # Determine stance from multiple sources
    risk_score = regime.get("risk_score", {}).get("score", 50)
    fear_phase = fear_gauge.get("phase", "Calm")
    season_name = season.get("season", "unknown").lower()
    clock_quadrant = season.get("clock", {}).get("quadrant_kr", "")

    # Stance logic
    stance, stance_kr, stance_reason = _compute_stance(risk_score, fear_phase, season_name)

    # Cash allocation based on risk level
    cash_ratio = _compute_cash_ratio(risk_score, fear_phase, season_name)

    # Sector bias
    sector_bias = _compute_sector_bias(season_name, clock_quadrant, macro_data)

    # Generate action items
    action_items = _generate_strategic_actions(
        stance, risk_score, fear_phase, season_name,
        signal_summary, cash_ratio
    )

    # Weekly outlook
    weekly_outlook = _generate_weekly_outlook(
        stance, season_name, risk_score, fear_phase, macro_data
    )

    # Guru alignment
    guru_summary = None
    if guru_consensus:
        guru_summary = _summarize_guru_consensus(guru_consensus)

    return {
        "stance": stance,
        "stance_kr": stance_kr,
        "stance_reason": stance_reason,
        "risk_level": _risk_level_kr(risk_score),
        "risk_score": round(risk_score, 1),
        "cash_ratio": cash_ratio,
        "cash_ratio_kr": f"현금 비중 {cash_ratio}% 권장",
        "sector_bias": sector_bias,
        "action_items": action_items,
        "weekly_outlook": weekly_outlook,
        "guru_summary": guru_summary,
        "fear_phase": fear_phase,
        "season": season_name,
    }


def _compute_stance(risk_score: float, fear_phase: str, season: str) -> tuple[str, str, str]:
    """Determine market stance. Returns (stance_key, stance_kr, reason_kr)."""
    if fear_phase == "Peak Fear":
        return ("contrarian_buy", "🟢 역발상 분할 매수",
                "공포 극점(Peak Fear) 감지 → 리스크 점수 무시, 역발상 매수 기회")
    if fear_phase == "Initial Panic":
        return ("defensive", "🔴 방어 태세",
                "공포 초기(Initial Panic) 감지 → 리스크 점수와 무관하게 방어 우선")
    if risk_score >= 75:
        return ("very_defensive", "🔴 매우 보수적",
                f"리스크 점수 {risk_score:.0f}/100 (≥75) → 고위험 구간")
    if risk_score >= 60:
        return ("cautious", "🟡 신중 접근",
                f"리스크 점수 {risk_score:.0f}/100 (≥60) → 경계 구간")
    if season in ("autumn", "winter"):
        s_kr = {"autumn": "역금융장세", "winter": "역실적장세"}.get(season, season)
        return ("cautious", f"🟡 신중 접근 ({s_kr})",
                f"시장 계절: {s_kr} → 하락 사이클 구간")
    if risk_score <= 30 and season in ("spring", "summer"):
        s_kr = {"spring": "금융장세", "summer": "실적장세"}.get(season, season)
        return ("aggressive", "🟢 적극 매수",
                f"리스크 점수 {risk_score:.0f}/100 (≤30) + {s_kr} → 최적 매수 구간")
    if risk_score <= 45:
        return ("moderate_buy", "🟢 완만한 매수",
                f"리스크 점수 {risk_score:.0f}/100 (≤45) → 선별 매수 유효")
    return ("neutral", "⚪ 중립 관망",
            f"리스크 점수 {risk_score:.0f}/100 (중간) → 명확한 방향 없음")


def _compute_cash_ratio(risk_score: float, fear_phase: str, season: str) -> int:
    """Recommend cash allocation percentage."""
    if fear_phase in ("Initial Panic",):
        return 50
    if risk_score >= 75:
        return 40
    if season == "winter":
        return 35
    if risk_score >= 60 or season == "autumn":
        return 30
    if risk_score <= 30 and season in ("spring", "summer"):
        return 10
    if risk_score <= 45:
        return 15
    return 20


def _compute_sector_bias(season: str, clock: str, macro: dict) -> list[dict]:
    """Recommend sector allocation bias."""
    biases = []

    season_sectors = {
        "spring": [
            {"sector": "성장주/기술주", "bias": "overweight", "reason": "금융장세 — 유동성 확대 수혜"},
            {"sector": "금융", "bias": "overweight", "reason": "금리 하락 기대 → 자산 가치 상승"},
        ],
        "summer": [
            {"sector": "우량 대형주", "bias": "overweight", "reason": "실적장세 — 실적 개선 기업 집중"},
            {"sector": "경기민감주", "bias": "overweight", "reason": "경기 확장 수혜"},
        ],
        "autumn": [
            {"sector": "방어주/유틸리티", "bias": "overweight", "reason": "역금융장세 — 금리 고점, 안전 자산 선호"},
            {"sector": "성장주", "bias": "underweight", "reason": "고금리 환경 → 밸류에이션 부담"},
        ],
        "winter": [
            {"sector": "현금/단기채", "bias": "overweight", "reason": "역실적장세 — 실적 악화 구간"},
            {"sector": "경기민감주", "bias": "underweight", "reason": "경기 하강 → 실적 타격"},
        ],
    }

    biases = season_sectors.get(season, [
        {"sector": "분산 투자", "bias": "neutral", "reason": "시즌 판별 불가 — 균형 배분 유지"},
    ])

    # Add macro-specific adjustments
    vix = macro.get("vix")
    if vix and vix > 25:
        biases.append({"sector": "금/안전자산", "bias": "overweight", "reason": f"VIX {vix:.0f} — 변동성 대비"})

    wti = macro.get("wti_crude")
    if wti and wti > 85:
        biases.append({"sector": "에너지", "bias": "overweight", "reason": f"WTI ${wti:.0f} — 고유가 수혜"})

    return biases


def _generate_strategic_actions(
    stance: str, risk_score: float, fear_phase: str,
    season: str, signal_summary: dict, cash_ratio: int,
) -> list[dict]:
    """Generate prioritized strategic action items."""
    actions = []

    buy_count = signal_summary.get("buy_count", 0)
    sell_count = signal_summary.get("sell_count", 0)
    total = signal_summary.get("total", 0)

    # Core strategic action
    stance_actions = {
        "contrarian_buy": {
            "title": "역발상 분할 매수 개시",
            "detail_kr": "공포 극점 구간입니다. 전체 투자금의 20-30%를 3-5회에 나눠 분할 매수하세요. 한 번에 올인하지 마세요.",
            "priority": 1,
        },
        "defensive": {
            "title": "방어 태세 전환",
            "detail_kr": "패닉 초기 구간입니다. 신규 매수를 중단하고, 손실 종목은 손절선 준수하세요. 현금 비중을 높이세요.",
            "priority": 1,
        },
        "very_defensive": {
            "title": "현금 비중 확대",
            "detail_kr": f"리스크 스코어 {risk_score:.0f}/100 (고위험). 주식 비중을 줄이고 현금 {cash_ratio}% 이상 확보하세요.",
            "priority": 1,
        },
        "aggressive": {
            "title": "적극 매수 구간",
            "detail_kr": f"리스크 낮음 + {season}장세. BUY 시그널 종목 중 상위 스코어 종목에 집중 매수하세요.",
            "priority": 1,
        },
        "moderate_buy": {
            "title": "선별적 매수",
            "detail_kr": f"BUY 시그널 {buy_count}개 중 스코어 상위 3-5개에 집중하세요. 분산 투자 원칙 준수.",
            "priority": 1,
        },
    }

    core = stance_actions.get(stance, {
        "title": "관망 유지",
        "detail_kr": "명확한 방향성이 없습니다. 기존 포지션 유지하며 시그널 변화를 모니터링하세요.",
        "priority": 2,
    })
    actions.append(core)

    # Signal-based actions
    if buy_count > 0 and stance not in ("defensive", "very_defensive"):
        actions.append({
            "title": f"BUY 시그널 {buy_count}개 확인",
            "detail_kr": f"총 {total}개 종목 중 {buy_count}개 매수 시그널. 아래 '추천 매수' 목록에서 상위 종목 확인.",
            "priority": 2,
        })

    if sell_count > 0:
        actions.append({
            "title": f"SELL 시그널 {sell_count}개 — 보유 종목 점검",
            "detail_kr": f"{sell_count}개 매도 시그널 발생. 보유 중인 종목이 포함되어 있는지 확인하세요.",
            "priority": 2,
        })

    # Risk management reminder
    actions.append({
        "title": "리스크 관리 체크",
        "detail_kr": f"현금 비중 목표: {cash_ratio}%. 단일 종목 비중 10% 이내, 섹터 비중 30% 이내 준수.",
        "priority": 3,
    })

    return actions


def _generate_weekly_outlook(
    stance: str, season: str, risk_score: float,
    fear_phase: str, macro: dict,
) -> dict:
    """Generate weekly market outlook summary."""
    vix = macro.get("vix") if macro.get("vix") is not None else 0
    usd_krw = macro.get("usd_krw") if macro.get("usd_krw") is not None else 0

    # Key events to watch
    watch_items = []
    if vix > 20:
        watch_items.append(f"VIX {vix:.1f} — 변동성 모니터링")
    if usd_krw > 1400:
        watch_items.append(f"USD/KRW {usd_krw:.0f} — 원화 약세 주시")
    watch_items.append("FOMC/경제지표 발표 일정 확인")
    watch_items.append("주요 기업 실적 발표 체크")

    return {
        "summary_kr": _weekly_summary(stance, season, risk_score, fear_phase),
        "watch_items": watch_items,
        "next_week_bias": stance,
    }


def _weekly_summary(stance: str, season: str, risk_score: float, fear_phase: str) -> str:
    season_kr = {
        "spring": "금융장세", "summer": "실적장세",
        "autumn": "역금융장세", "winter": "역실적장세",
    }.get(season, "판별 중")

    if fear_phase == "Peak Fear":
        return f"시장 공포가 극점에 달했습니다({season_kr}). 역사적으로 이 구간은 중장기 매수 기회입니다. 분할 매수로 접근하세요."
    if risk_score >= 70:
        return f"리스크 스코어 {risk_score:.0f}/100으로 높은 수준입니다({season_kr}). 보수적 운영으로 자산을 보전하세요."
    if risk_score <= 35:
        return f"리스크 스코어 {risk_score:.0f}/100으로 양호합니다({season_kr}). 시그널 기반 선별 매수 유효합니다."
    return f"현재 {season_kr} 구간이며, 리스크 스코어 {risk_score:.0f}/100입니다. 중립적 관점에서 선별적으로 접근하세요."


def _risk_level_kr(score: float) -> str:
    if score >= 75:
        return "🔴 매우 높음"
    if score >= 60:
        return "🟠 높음"
    if score >= 40:
        return "🟡 보통"
    if score >= 25:
        return "🟢 낮음"
    return "🟢 매우 낮음"


def _summarize_guru_consensus(guru_data) -> dict:
    """Summarize guru consensus view."""
    if isinstance(guru_data, list):
        gurus = guru_data
    elif isinstance(guru_data, dict):
        gurus = guru_data.get("gurus", [])
    else:
        return None
    if not gurus:
        return None

    stances = {"bullish": 0, "bearish": 0, "neutral": 0, "selective_buy": 0}
    total_conviction = 0

    for g in gurus:
        view = g.get("market_view", {})
        stance = view.get("stance", "neutral")
        conviction = view.get("conviction", 50)
        total_conviction += conviction

        if stance in ("bullish", "strong_bullish"):
            stances["bullish"] += 1
        elif stance in ("bearish", "strong_bearish"):
            stances["bearish"] += 1
        elif "buy" in stance:
            stances["selective_buy"] += 1
        else:
            stances["neutral"] += 1

    dominant = max(stances, key=stances.get)
    avg_conviction = total_conviction / len(gurus) if gurus else 50

    return {
        "consensus": dominant,
        "consensus_kr": {
            "bullish": "강세 전망 우세",
            "bearish": "약세 전망 우세",
            "neutral": "관망 의견 다수",
            "selective_buy": "선별적 매수 우세",
        }.get(dominant, "혼재"),
        "avg_conviction": round(avg_conviction, 1),
        "breakdown": stances,
        "guru_count": len(gurus),
    }


# ── Top Picks Ranking ────────────────────────────────────────────────────

def rank_top_picks(
    signals: list[dict],
    positions: list[dict],
    total_capital: float,
    max_picks: int = 5,
) -> list[dict]:
    """Rank and return top BUY recommendations with full action details."""
    held_symbols = {p["symbol"] for p in positions}

    # Filter to BUY signals only, exclude already-held
    buy_signals = [
        s for s in signals
        if s.get("final_signal") == "BUY" and s["symbol"] not in held_symbols
    ]

    # Sort by raw_score descending
    buy_signals.sort(key=lambda s: s.get("raw_score", 0), reverse=True)

    picks = []
    for s in buy_signals[:max_picks]:
        score = s.get("raw_score", 0)
        confidence = s.get("confidence", 50)
        rsi = s.get("rsi_value")

        # Position sizing
        sizing = recommend_position_size(
            total_capital, score, confidence,
        )

        # Price targets
        current = s.get("current_price") or s.get("close")
        targets = compute_price_targets(
            current or 0, rsi, "BUY",
        )

        picks.append({
            "rank": len(picks) + 1,
            "symbol": s["symbol"],
            "name": s.get("name", s["symbol"]),
            "market": s.get("market", ""),
            "signal_score": round(score, 1),
            "confidence": round(confidence if confidence is not None else 0, 1),
            "rsi": round(rsi, 1) if rsi else None,
            "current_price": current,
            "target_price": targets["target"],
            "stop_loss": targets["stop_loss"],
            "rr_ratio": targets["rr_ratio"],
            "target_return_pct": targets["target_pct"],
            "recommended_size": sizing["amount"],
            "recommended_pct": sizing["pct"],
            "size_rationale_kr": sizing["rationale"],
            "rationale": s.get("rationale", ""),
        })

    return picks
