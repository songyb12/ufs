"""Market Season detection, Investment Clock, Yield Phase tracker, and unified risk scoring.

All functions are pure (no DB access) — they receive pre-fetched data dicts and return computed results.
Used by app.routers.macro_intel which handles data gathering.

References:
  - Uragami Kunio "4 Seasons of the Stock Market" (rate cycle × earnings cycle)
  - Investment Clock (growth × inflation quadrant model)
"""

from __future__ import annotations

# ── Market Season Labels ──

SEASON_LABELS = {
    "spring": {
        "en": "Spring",
        "kr": "금융장세",
        "icon": "🌱",
        "description_kr": "금리 하락 + 경기 회복 초기. 유동성 확대로 주식 강세 시작.",
        "strategy_kr": "주식 비중 확대, 성장주 중심 포트폴리오",
    },
    "summer": {
        "en": "Summer",
        "kr": "실적장세",
        "icon": "☀️",
        "description_kr": "금리 상승 시작이나 실적 개선이 더 강함. 실적 우량주 강세.",
        "strategy_kr": "실적 우량주 선별 매수, 섹터 로테이션 주시",
    },
    "autumn": {
        "en": "Autumn",
        "kr": "역금융장세",
        "icon": "🍂",
        "description_kr": "금리 고점/상승 지속 + 성장 둔화. 밸류에이션 부담 증가.",
        "strategy_kr": "비중 축소, 방어주 전환, 현금 비중 확대",
    },
    "winter": {
        "en": "Winter",
        "kr": "역실적장세",
        "icon": "❄️",
        "description_kr": "금리 하락 시작이나 실적 악화 지속. 본격적 하락장.",
        "strategy_kr": "현금/채권 비중 극대화, 역발상 매수 준비",
    },
}

CLOCK_LABELS = {
    "recovery": {
        "en": "Recovery",
        "kr": "회복",
        "color": "#22c55e",
        "asset_kr": "주식 유리 (성장주, 이머징)",
        "description_kr": "성장↑ 물가↓ — 가장 유리한 투자 환경",
    },
    "overheat": {
        "en": "Overheat",
        "kr": "과열",
        "color": "#f59e0b",
        "asset_kr": "원자재 유리 (에너지, 소재)",
        "description_kr": "성장↑ 물가↑ — 인플레이션 압력 증가",
    },
    "stagflation": {
        "en": "Stagflation",
        "kr": "침체",
        "color": "#ef4444",
        "asset_kr": "현금 유리 (단기채, MMF)",
        "description_kr": "성장↓ 물가↑ — 가장 불리한 투자 환경",
    },
    "reflation": {
        "en": "Reflation",
        "kr": "환기",
        "color": "#3b82f6",
        "asset_kr": "채권 유리 (장기채, 배당주)",
        "description_kr": "성장↓ 물가↓ — 금리 인하 기대, 채권 강세",
    },
}

YIELD_PHASE_LABELS = {
    "normal": {"en": "Normal", "kr": "정상", "risk": False},
    "flattening": {"en": "Flattening", "kr": "평탄화 진행", "risk": False},
    "inverted": {"en": "Inverted", "kr": "역전", "risk": True},
    "normalizing": {"en": "Normalizing", "kr": "정상화 진행", "risk": True},
    "transitioning": {"en": "Transitioning", "kr": "전환 중", "risk": False},
}


# ── Market Season Detection ──


def detect_market_season(
    macro_history: list[dict],
    kr_foreign_trend: list[dict] | None = None,
    etf_momentum: dict | None = None,
) -> dict:
    """Detect current market season (Uragami Kunio proxy model).

    Uses US 10Y yield direction as rate axis, and composite proxy
    (copper + ETF momentum + KR foreign flow) as growth/earnings axis.

    Args:
        macro_history: 60-90 days of macro_indicators rows (oldest→newest)
        kr_foreign_trend: Recent KR foreign net buy daily totals
        etf_momentum: {"spy_return_60d": float, "qqq_return_60d": float}

    Returns:
        dict with season, confidence, axis scores, description
    """
    if len(macro_history) < 10:
        return _default_season(f"데이터 부족 (현재 {len(macro_history)}일, 최소 10일 필요)")

    # Confidence penalty for partial data (10-19 days)
    data_penalty = min(1.0, len(macro_history) / 20)

    # ── Rate Axis: US 10Y Yield direction ──
    yields = [
        h.get("us_10y_yield")
        for h in macro_history
        if h.get("us_10y_yield") is not None
    ]
    if len(yields) < 15:
        rate_momentum = 0.0
        rate_direction = "flat"
    else:
        recent_10 = yields[-10:]
        older_30 = yields[:-10] if len(yields) > 10 else yields[:5]
        avg_recent = sum(recent_10) / len(recent_10)
        avg_older = sum(older_30) / len(older_30) if older_30 else avg_recent
        if abs(avg_older) < 0.001:
            rate_momentum = 0.0
        else:
            rate_momentum = (avg_recent - avg_older) / abs(avg_older)

        if rate_momentum < -0.03:
            rate_direction = "falling"
        elif rate_momentum > 0.03:
            rate_direction = "rising"
        else:
            rate_direction = "flat"

    # ── Growth Proxy Axis ──
    # Component 1: Copper momentum (40%)
    coppers = [
        _normalize_copper(h.get("copper_price"))
        for h in macro_history
        if h.get("copper_price") is not None
    ]
    if len(coppers) >= 15:
        cop_recent = sum(coppers[-10:]) / 10
        cop_older = sum(coppers[:-10]) / max(len(coppers) - 10, 1)
        copper_mom = (cop_recent - cop_older) / max(abs(cop_older), 0.01)
        copper_mom = max(-1.0, min(1.0, copper_mom))  # clamp to [-1, 1]
    else:
        copper_mom = 0.0

    # Component 2: ETF momentum (30%)
    etf = etf_momentum or {}
    spy_ret = etf.get("spy_return_60d", 0) or 0
    # Normalize: ±15% range → ±1
    etf_mom = max(-1.0, min(1.0, spy_ret / 0.15))

    # Component 3: KR foreign flow momentum (30%)
    kr_flow = kr_foreign_trend or []
    if len(kr_flow) >= 10:
        recent_flow = sum(
            (r.get("total_foreign_net") or 0) for r in kr_flow[-10:]
        )
        older_flow = sum(
            (r.get("total_foreign_net") or 0) for r in kr_flow[:-10]
        )
        # Normalize by rough scale (500B KRW)
        flow_diff = recent_flow - older_flow
        kr_flow_mom = max(-1.0, min(1.0, flow_diff / 500_000_000_000))
    else:
        kr_flow_mom = 0.0

    growth_proxy = copper_mom * 0.40 + etf_mom * 0.30 + kr_flow_mom * 0.30

    if growth_proxy > 0.02:
        growth_direction = "improving"
    elif growth_proxy < -0.02:
        growth_direction = "deteriorating"
    else:
        growth_direction = "flat"

    # ── Season Classification ──
    season_key = _classify_season(rate_direction, growth_direction)

    # ── Confidence ──
    raw_conf = abs(rate_momentum) * 5 + abs(growth_proxy) * 5
    confidence = round(max(0.2, min(1.0, raw_conf * data_penalty)), 2)

    info = SEASON_LABELS[season_key]
    return {
        "season": info["en"],
        "season_kr": info["kr"],
        "icon": info["icon"],
        "confidence": confidence,
        "description_kr": info["description_kr"],
        "strategy_kr": info["strategy_kr"],
        "axes": {
            "rate_direction": rate_direction,
            "rate_momentum": round(rate_momentum, 4),
            "growth_direction": growth_direction,
            "growth_proxy": round(growth_proxy, 4),
            "components": {
                "copper_momentum": round(copper_mom, 4),
                "etf_momentum": round(etf_mom, 4),
                "kr_flow_momentum": round(kr_flow_mom, 4),
            },
        },
    }


def _classify_season(rate_dir: str, growth_dir: str) -> str:
    """Map rate×growth directions to season key."""
    if rate_dir == "falling" and growth_dir in ("improving", "flat"):
        return "spring"
    if rate_dir in ("rising", "flat") and growth_dir == "improving":
        return "summer"
    # (flat, flat) → neutral continuation, not bearish autumn
    if rate_dir == "flat" and growth_dir == "flat":
        return "summer"
    if rate_dir in ("rising", "flat") and growth_dir == "deteriorating":
        return "autumn"
    if rate_dir == "rising" and growth_dir == "flat":
        return "autumn"
    if rate_dir == "falling" and growth_dir == "deteriorating":
        return "winter"
    # Ambiguous — default to autumn (conservative)
    return "autumn"


def _default_season(reason: str) -> dict:
    """Return unknown season with reason."""
    return {
        "season": "Unknown",
        "season_kr": "판별불가",
        "icon": "❓",
        "confidence": 0.0,
        "description_kr": reason,
        "strategy_kr": "데이터 축적 후 판단",
        "axes": {
            "rate_direction": "unknown",
            "rate_momentum": 0.0,
            "growth_direction": "unknown",
            "growth_proxy": 0.0,
            "components": {
                "copper_momentum": 0.0,
                "etf_momentum": 0.0,
                "kr_flow_momentum": 0.0,
            },
        },
    }


def _normalize_copper(copper: float | None) -> float:
    """Normalize copper from cents/lb to $/lb if needed."""
    if copper is None:
        return 4.0
    if copper > 100:
        return copper / 100
    return copper


# ── Investment Clock ──


def compute_investment_clock(
    macro_data: dict | None,
    macro_history: list[dict] | None = None,
) -> dict:
    """Compute Investment Clock quadrant from growth × inflation axes.

    Growth axis: Copper health + Yield curve health + VIX calm
    Inflation axis: Oil pressure + Gold/Copper ratio + DXY tightening

    Both axes range from -1.0 to +1.0.
    """
    macro = macro_data or {}
    history = macro_history or []

    # ── Growth Axis (-1 to +1) ──
    # Copper: strong = high growth, weak = contraction
    copper = _normalize_copper(macro.get("copper_price"))
    if copper < 3.0:
        copper_g = -0.8
    elif copper < 3.5:
        copper_g = -0.3
    elif copper < 4.0:
        copper_g = 0.2
    elif copper < 4.5:
        copper_g = 0.6
    else:
        copper_g = 0.4  # overheating pullback risk

    # Also consider copper trend if history available
    if len(history) >= 20:
        cop_vals = [
            _normalize_copper(h.get("copper_price"))
            for h in history
            if h.get("copper_price") is not None
        ]
        if len(cop_vals) >= 15:
            cop_trend = (
                sum(cop_vals[-5:]) / 5 - sum(cop_vals[:5]) / 5
            ) / max(sum(cop_vals[:5]) / 5, 0.01)
            copper_g += max(-0.3, min(0.3, cop_trend * 3))
            copper_g = max(-1.0, min(1.0, copper_g))

    # Yield spread: steep = growth, inverted = recession
    ys = macro.get("us_yield_spread")
    if ys is None:
        yield_g = 0.0
    elif ys > 1.5:
        yield_g = 0.8
    elif ys > 0.5:
        yield_g = 0.4
    elif ys > 0:
        yield_g = 0.0
    elif ys > -0.5:
        yield_g = -0.5
    else:
        yield_g = -0.9

    # VIX inverse: low VIX = calm = growth confidence
    vix = macro.get("vix")
    if vix is None:
        vix_g = 0.0
    elif vix < 13:
        vix_g = 0.7
    elif vix < 18:
        vix_g = 0.5
    elif vix < 22:
        vix_g = 0.0
    elif vix < 28:
        vix_g = -0.4
    else:
        vix_g = -0.8

    growth_score = round(
        copper_g * 0.40 + yield_g * 0.35 + vix_g * 0.25, 3
    )
    growth_score = max(-1.0, min(1.0, growth_score))

    # ── Inflation Axis (-1 to +1) ──
    # WTI oil: high = inflationary
    wti = macro.get("wti_crude")
    if wti is None:
        oil_inf = 0.0
    elif wti > 100:
        oil_inf = 0.9
    elif wti > 90:
        oil_inf = 0.6
    elif wti > 75:
        oil_inf = 0.2
    elif wti > 55:
        oil_inf = -0.2
    elif wti > 40:
        oil_inf = -0.5
    else:
        oil_inf = -0.8

    # Gold/Copper ratio: high = stagflation signal
    gold = macro.get("gold_price") or 2000
    gc_ratio = gold / max(copper, 0.01)
    if gc_ratio > 700:
        gc_inf = 0.9
    elif gc_ratio > 600:
        gc_inf = 0.5
    elif gc_ratio > 500:
        gc_inf = 0.1
    elif gc_ratio > 400:
        gc_inf = -0.3
    else:
        gc_inf = -0.6

    # DXY: strong dollar = tightening = inflationary pressure for EM
    dxy = macro.get("dxy_index")
    if dxy is None:
        dxy_inf = 0.0
    elif dxy > 110:
        dxy_inf = 0.8
    elif dxy > 106:
        dxy_inf = 0.4
    elif dxy > 103:
        dxy_inf = 0.0
    elif dxy > 100:
        dxy_inf = -0.3
    else:
        dxy_inf = -0.6

    inflation_score = round(
        oil_inf * 0.40 + gc_inf * 0.35 + dxy_inf * 0.25, 3
    )
    inflation_score = max(-1.0, min(1.0, inflation_score))

    # ── Quadrant Classification ──
    if growth_score >= 0 and inflation_score < 0:
        quadrant = "recovery"
    elif growth_score >= 0 and inflation_score >= 0:
        quadrant = "overheat"
    elif growth_score < 0 and inflation_score >= 0:
        quadrant = "stagflation"
    else:
        quadrant = "reflation"

    info = CLOCK_LABELS[quadrant]
    return {
        "quadrant": info["en"],
        "quadrant_kr": info["kr"],
        "color": info["color"],
        "asset_kr": info["asset_kr"],
        "description_kr": info["description_kr"],
        "growth_score": round(growth_score, 2),
        "inflation_score": round(inflation_score, 2),
        "growth_components": {
            "copper": round(copper_g, 2),
            "yield_curve": round(yield_g, 2),
            "vix_inverse": round(vix_g, 2),
        },
        "inflation_components": {
            "oil": round(oil_inf, 2),
            "gold_copper_ratio": round(gc_inf, 2),
            "dxy": round(dxy_inf, 2),
        },
    }


# ── Yield Curve Phase Tracker ──


def detect_yield_phase(
    yield_spread_history: list[float | None],
) -> dict:
    """Detect yield curve phase from spread history.

    Phases:
      Normal (>1.0) → Flattening (0-1.0, declining) → Inverted (<0) →
      Normalizing (rising from inversion) ⚠️ → Normal

    The Normalizing phase is historically the most dangerous — it often
    precedes recessions as the curve un-inverts right before downturns.

    Args:
        yield_spread_history: list of yield spreads, oldest→newest.
            None values are skipped.
    """
    # Filter out None values
    spreads = [s for s in yield_spread_history if s is not None]

    if len(spreads) < 10:
        return {
            "phase": "Unknown",
            "phase_kr": "데이터 부족",
            "risk_flag": False,
            "current_spread": None,
            "avg_10d": None,
            "trend": "unknown",
            "description_kr": "Yield spread 히스토리 부족 (최소 10일 필요)",
        }

    current = spreads[-1]
    avg_recent = sum(spreads[-10:]) / 10
    older_spreads = spreads[:-10]
    avg_older = sum(older_spreads) / len(older_spreads) if older_spreads else avg_recent

    # Determine trend direction
    if avg_recent > avg_older + 0.05:
        trend = "steepening"
    elif avg_recent < avg_older - 0.05:
        trend = "flattening"
    else:
        trend = "stable"

    # Phase classification
    if current < 0:
        if trend == "steepening":
            phase_key = "normalizing"
            desc = f"수익률곡선 역전 중 정상화 진행 (spread={current:.2f}%). 역사적으로 경기침체 직전 시그널."
        else:
            phase_key = "inverted"
            desc = f"수익률곡선 역전 (spread={current:.2f}%). 경기침체 경고."
    elif current < 0.5:
        # Was it recently inverted?
        recent_min = min(spreads[-20:]) if len(spreads) >= 20 else min(spreads[-10:])
        if recent_min < 0 and trend == "steepening":
            phase_key = "normalizing"
            desc = f"최근 역전 후 정상화 진행 (spread={current:.2f}%). 경기침체 위험 지속."
        elif trend == "flattening":
            phase_key = "flattening"
            desc = f"수익률곡선 평탄화 진행 (spread={current:.2f}%). 역전 가능성 주시."
        else:
            phase_key = "transitioning"
            desc = f"수익률곡선 전환 구간 (spread={current:.2f}%)."
    elif current < 1.0:
        if trend == "flattening":
            phase_key = "flattening"
            desc = f"수익률곡선 평탄화 진행 (spread={current:.2f}%). 주의 필요."
        else:
            phase_key = "normal"
            desc = f"수익률곡선 정상 범위 (spread={current:.2f}%)."
    else:
        phase_key = "normal"
        desc = f"수익률곡선 건전한 기울기 (spread={current:.2f}%)."

    info = YIELD_PHASE_LABELS[phase_key]
    return {
        "phase": info["en"],
        "phase_kr": info["kr"],
        "risk_flag": info["risk"],
        "current_spread": round(current, 3),
        "avg_10d": round(avg_recent, 3),
        "trend": trend,
        "description_kr": desc,
    }


# ── Portfolio Strategy Match ──


def check_strategy_match(
    season: str,
    clock_quadrant: str,
    portfolio_summary: dict | None = None,
    signal_summary: dict | None = None,
) -> dict:
    """Check if portfolio positioning aligns with current market season.

    Args:
        season: One of "Spring", "Summer", "Autumn", "Winter", "Unknown"
        clock_quadrant: One of "Recovery", "Overheat", "Stagflation", "Reflation"
        portfolio_summary: {
            "total_positions": int,
            "kr_pct": float (0-100),
            "us_pct": float (0-100),
            "tech_pct": float (0-100),
            "total_invested": float,
        }
        signal_summary: {
            "buy_count": int,
            "sell_count": int,
            "hold_count": int,
        }

    Returns:
        dict with warnings list and match_score (0-100)
    """
    warnings: list[dict] = []
    port = portfolio_summary or {}
    sig = signal_summary or {}

    buy_count = sig.get("buy_count", 0)
    sell_count = sig.get("sell_count", 0)
    total_positions = port.get("total_positions", 0)
    kr_pct = port.get("kr_pct", 50)
    tech_pct = port.get("tech_pct", 0)
    total_invested = port.get("total_invested", 0)

    season_lower = season.lower()
    quad_lower = clock_quadrant.lower()

    # ── Season-based warnings ──
    if season_lower == "winter":
        if buy_count > sell_count and buy_count > 3:
            warnings.append({
                "level": "warning",
                "message": "겨울(역실적) 장세에서 매수 시그널 다수 발생. 신규 매수 자제, 비중 축소 검토.",
            })
        if total_positions > 10:
            warnings.append({
                "level": "info",
                "message": "역실적 국면에서 다수 포지션 보유 중. 핵심 종목 외 정리 검토.",
            })

    elif season_lower == "autumn":
        if kr_pct > 65:
            warnings.append({
                "level": "warning",
                "message": f"역금융장세 진입, KR 비중 {kr_pct:.0f}% 과다. 분산 또는 축소 필요.",
            })
        if buy_count > sell_count:
            warnings.append({
                "level": "info",
                "message": "금리 고점/성장 둔화 국면. 공격적 매수보다 선별적 접근 권장.",
            })

    elif season_lower == "spring":
        if total_invested == 0 or total_positions == 0:
            warnings.append({
                "level": "opportunity",
                "message": "금융장세 시작, 포지션 없음. 주식 비중 확대 기회.",
            })

    elif season_lower == "summer":
        if sell_count > buy_count and sell_count > 3:
            warnings.append({
                "level": "info",
                "message": "실적장세인데 매도 시그널 우세. 개별 종목 리스크 점검.",
            })

    # ── Clock-based warnings ──
    if quad_lower == "stagflation":
        if total_positions > 5:
            warnings.append({
                "level": "warning",
                "message": "침체(Stagflation) 국면. 현금/채권 비중 확대, 주식 축소 검토.",
            })

    elif quad_lower == "overheat":
        if tech_pct > 50:
            warnings.append({
                "level": "warning",
                "message": f"과열 국면, 기술주 비중 {tech_pct:.0f}% 집중. 원자재/가치주 분산 검토.",
            })

    elif quad_lower == "recovery":
        if total_invested == 0:
            warnings.append({
                "level": "opportunity",
                "message": "회복 국면. 주식 비중 적극 확대 가장 유리한 시점.",
            })

    elif quad_lower == "reflation":
        if tech_pct > 40:
            warnings.append({
                "level": "info",
                "message": "환기(Reflation) 국면. 성장주보다 배당주/채권 유리.",
            })

    # ── Match Score ──
    # Higher = better alignment
    match_score = _compute_match_score(season_lower, quad_lower, port, sig)

    return {
        "match_score": match_score,
        "warnings": warnings,
        "warning_count": len(warnings),
        "season": season,
        "clock_quadrant": clock_quadrant,
    }


def _compute_match_score(
    season: str, quadrant: str, port: dict, sig: dict
) -> int:
    """Compute 0-100 alignment score between position and market phase."""
    score = 50  # neutral start

    buy_count = sig.get("buy_count", 0)
    sell_count = sig.get("sell_count", 0)
    total_positions = port.get("total_positions", 0)

    # Season alignment
    if season in ("spring", "summer"):
        # Bullish seasons: more positions = better alignment
        if total_positions > 5:
            score += 15
        if buy_count > sell_count:
            score += 10
    elif season in ("autumn", "winter"):
        # Bearish seasons: fewer positions / sell signals = better alignment
        if total_positions < 5:
            score += 15
        if sell_count >= buy_count:
            score += 10
        if total_positions > 10:
            score -= 15

    # Clock alignment
    if quadrant == "recovery":
        if total_positions > 0:
            score += 10
    elif quadrant == "stagflation":
        if total_positions < 3:
            score += 15
        elif total_positions > 8:
            score -= 20

    return max(0, min(100, score))


# ── Unified Macro Risk Score ──


def compute_unified_risk_score(
    stagflation_index: float,
    risk_regime_score: float,
    clock_quadrant: str,
) -> dict:
    """Compute unified Macro Risk Score (0-100).

    Combines three existing signals:
      - Stagflation Index (0-100): 40% weight
      - Risk Regime Score (-1 to +1): 30% weight (inverted)
      - Investment Clock quadrant: 30% weight

    Higher score = higher risk.
    """
    # Component 1: Stagflation (already 0-100)
    stag_component = stagflation_index * 0.40

    # Component 2: Risk Regime (-1=panic→100, +1=complacent→0)
    risk_normalized = ((1.0 - risk_regime_score) / 2.0) * 100
    risk_component = risk_normalized * 0.30

    # Component 3: Clock quadrant
    clock_risk_map = {
        "recovery": 15,
        "reflation": 35,
        "overheat": 55,
        "stagflation": 85,
    }
    clock_val = clock_risk_map.get(clock_quadrant.lower(), 50)
    clock_component = clock_val * 0.30

    unified = stag_component + risk_component + clock_component
    unified = round(max(0.0, min(100.0, unified)), 1)

    # Risk level
    if unified < 25:
        level, level_kr = "Low", "양호"
    elif unified < 45:
        level, level_kr = "Moderate", "보통"
    elif unified < 65:
        level, level_kr = "Elevated", "경계"
    elif unified < 80:
        level, level_kr = "High", "위험"
    else:
        level, level_kr = "Critical", "심각"

    return {
        "score": unified,
        "level": level,
        "level_kr": level_kr,
        "components": {
            "stagflation": {
                "value": round(stagflation_index, 1),
                "weight": 0.40,
                "contribution": round(stag_component, 1),
            },
            "risk_regime": {
                "value": round(risk_regime_score, 2),
                "normalized": round(risk_normalized, 1),
                "weight": 0.30,
                "contribution": round(risk_component, 1),
            },
            "investment_clock": {
                "quadrant": clock_quadrant,
                "risk_value": clock_val,
                "weight": 0.30,
                "contribution": round(clock_component, 1),
            },
        },
    }
