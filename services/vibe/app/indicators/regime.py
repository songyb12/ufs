"""Market regime detection, stagflation monitoring, and cross-market recommendation.

All functions are pure (no DB access) — they take data dicts and return computed results.
Used by app.routers.macro_intel which handles data gathering.
"""

from __future__ import annotations

# ── Regime Detection ──

RISK_LABELS = {
    "complacent": {"en": "Complacent", "kr": "안일"},
    "risk_on": {"en": "Risk-On", "kr": "리스크온"},
    "risk_off": {"en": "Risk-Off", "kr": "리스크오프"},
    "panic": {"en": "Panic", "kr": "패닉"},
}

DRIVER_LABELS = {
    "momentum": {"en": "Momentum-Driven", "kr": "모멘텀 주도"},
    "fundamental": {"en": "Fundamental-Driven", "kr": "펀더멘탈 주도"},
    "range_bound": {"en": "Range-Bound", "kr": "박스권"},
}


def detect_risk_regime(
    vix: float | None,
    fear_greed: int | None,
    put_call_ratio: float | None,
    vix_term_structure: str | None,
    yield_spread: float | None,
) -> dict:
    """Classify current risk regime from sentiment/macro inputs.

    Returns {"regime": str, "regime_kr": str, "score": float, "factors": {...}}
    Score range: -1.0 (panic) to +1.0 (complacent/risk-on).
    """
    score = 0.0
    factors = {}

    # VIX contribution (40% weight in risk axis)
    v = vix if vix is not None else 18.0  # default neutral
    if v < 13:
        vix_s = 0.8
        vix_label = "very_low"
    elif v < 18:
        vix_s = 0.5
        vix_label = "low"
    elif v < 22:
        vix_s = 0.0
        vix_label = "normal"
    elif v < 28:
        vix_s = -0.5
        vix_label = "elevated"
    elif v < 35:
        vix_s = -0.8
        vix_label = "high"
    else:
        vix_s = -1.0
        vix_label = "extreme"
    factors["vix"] = {"value": v, "score": vix_s, "label": vix_label}
    score += vix_s * 0.40

    # Fear & Greed (30% weight)
    fg = fear_greed if fear_greed is not None else 50
    fg_s = (fg - 50) / 50  # 0→-1, 50→0, 100→+1
    fg_label = (
        "extreme_fear" if fg < 20 else
        "fear" if fg < 40 else
        "neutral" if fg < 60 else
        "greed" if fg < 80 else
        "extreme_greed"
    )
    factors["fear_greed"] = {"value": fg, "score": round(fg_s, 2), "label": fg_label}
    score += fg_s * 0.30

    # Put/Call Ratio (15% weight) — high P/C = bearish sentiment
    pc = put_call_ratio if put_call_ratio is not None else 0.85
    if pc < 0.6:
        pc_s = 0.5  # very bullish (low put buying)
    elif pc < 0.8:
        pc_s = 0.2
    elif pc < 1.0:
        pc_s = -0.1
    elif pc < 1.2:
        pc_s = -0.4
    else:
        pc_s = -0.8  # heavy put buying
    factors["put_call"] = {"value": round(pc, 2), "score": pc_s, "label": "bullish" if pc_s > 0 else "bearish"}
    score += pc_s * 0.15

    # VIX Term Structure (10% weight)
    vts = vix_term_structure or "contango"
    vts_s = 0.3 if vts == "contango" else -0.5  # backwardation = near-term fear
    factors["vix_term"] = {"value": vts, "score": vts_s, "label": vts}
    score += vts_s * 0.10

    # Yield Spread (5% weight)
    ys = yield_spread if yield_spread is not None else 0.5
    if ys < -0.5:
        ys_s = -0.8
    elif ys < 0:
        ys_s = -0.3
    elif ys < 1.0:
        ys_s = 0.2
    else:
        ys_s = 0.5
    factors["yield_spread"] = {"value": round(ys, 2), "score": ys_s, "label": "inverted" if ys < 0 else "normal"}
    score += ys_s * 0.05

    score = round(max(-1.0, min(1.0, score)), 2)

    # Map to regime label
    if score <= -0.6:
        regime_key = "panic"
    elif score <= -0.15:
        regime_key = "risk_off"
    elif score <= 0.5:
        regime_key = "risk_on"
    else:
        regime_key = "complacent"

    return {
        "regime": RISK_LABELS[regime_key]["en"],
        "regime_kr": RISK_LABELS[regime_key]["kr"],
        "score": score,
        "factors": factors,
    }


def detect_driver_regime(
    avg_technical_score: float | None,
    avg_macro_score: float | None,
    avg_fund_flow_score: float | None,
) -> dict:
    """Classify market driver: fundamental, momentum, or range-bound.

    Compares magnitude of technical vs macro scoring influence.
    """
    tech = abs(avg_technical_score) if avg_technical_score is not None else 0
    macro = abs(avg_macro_score) if avg_macro_score is not None else 0
    flow = abs(avg_fund_flow_score) if avg_fund_flow_score is not None else 0

    # Combine macro + flow as "fundamental" signal
    fundamental_strength = macro + flow * 0.5
    momentum_strength = tech

    if momentum_strength > fundamental_strength * 1.3 and momentum_strength > 5:
        driver_key = "momentum"
        confidence = min(1.0, momentum_strength / max(fundamental_strength, 1) * 0.5)
    elif fundamental_strength > momentum_strength * 1.3 and fundamental_strength > 5:
        driver_key = "fundamental"
        confidence = min(1.0, fundamental_strength / max(momentum_strength, 1) * 0.5)
    else:
        driver_key = "range_bound"
        confidence = 0.5

    rationale_parts = []
    if tech > 0:
        rationale_parts.append(f"기술적 강도 {tech:.1f}")
    if macro > 0:
        rationale_parts.append(f"매크로 강도 {macro:.1f}")
    if flow > 0:
        rationale_parts.append(f"수급 강도 {flow:.1f}")

    return {
        "driver": DRIVER_LABELS[driver_key]["en"],
        "driver_kr": DRIVER_LABELS[driver_key]["kr"],
        "confidence": round(confidence, 2),
        "rationale": ", ".join(rationale_parts) if rationale_parts else "데이터 부족",
        "breakdown": {
            "technical_strength": round(tech, 1),
            "fundamental_strength": round(fundamental_strength, 1),
        },
    }


def detect_combined_regime(
    macro_data: dict | None,
    sentiment_data: dict | None,
    signal_stats: dict | None,
) -> dict:
    """Full regime detection combining risk + driver axes."""
    macro = macro_data or {}
    sent = sentiment_data or {}
    stats = signal_stats or {}

    risk = detect_risk_regime(
        vix=macro.get("vix"),
        fear_greed=sent.get("fear_greed_index"),
        put_call_ratio=sent.get("put_call_ratio"),
        vix_term_structure=sent.get("vix_term_structure"),
        yield_spread=macro.get("us_yield_spread"),
    )

    # Average across markets for driver detection
    all_tech = []
    all_macro = []
    all_flow = []
    for mkt_stats in stats.values():
        if isinstance(mkt_stats, dict):
            if mkt_stats.get("avg_technical") is not None:
                all_tech.append(mkt_stats["avg_technical"])
            if mkt_stats.get("avg_macro") is not None:
                all_macro.append(mkt_stats["avg_macro"])
            if mkt_stats.get("avg_fund_flow") is not None:
                all_flow.append(mkt_stats["avg_fund_flow"])

    driver = detect_driver_regime(
        avg_technical_score=sum(all_tech) / len(all_tech) if all_tech else None,
        avg_macro_score=sum(all_macro) / len(all_macro) if all_macro else None,
        avg_fund_flow_score=sum(all_flow) / len(all_flow) if all_flow else None,
    )

    label_en = f"{risk['regime']} / {driver['driver']}"
    label_kr = f"{risk['regime_kr']} / {driver['driver_kr']}"

    return {
        "risk_regime": risk,
        "driver_regime": driver,
        "label": label_en,
        "label_kr": label_kr,
    }


# ── Stagflation Monitoring ──


def compute_stagflation_index(
    gold_price: float | None,
    copper_price: float | None,
    wti_crude: float | None,
    yield_spread: float | None,
    dxy_index: float | None,
) -> dict:
    """Compute composite stagflation risk index (0-100).

    Components (weighted):
      - Gold/Copper ratio (30%): high = stagflation signal
      - Yield curve (25%): inverted = recession risk
      - Oil pressure (20%): high oil = inflation
      - DXY tightening (15%): strong dollar = EM squeeze
      - Copper demand (10%): weak copper = low growth
    """
    components = {}

    # 1. Gold/Copper ratio (30%) — higher = more stagflation risk
    gold = gold_price or 2000
    copper = copper_price or 4.0
    # HG=F COMEX may return cents/lb (e.g., 420 = $4.20/lb) — normalize to $/lb
    if copper > 100:
        copper = copper / 100
    gc_ratio = gold / max(copper, 0.01)
    if gc_ratio > 700:
        gc_score = 100
    elif gc_ratio > 600:
        gc_score = 70 + (gc_ratio - 600) / 100 * 30
    elif gc_ratio > 500:
        gc_score = 40 + (gc_ratio - 500) / 100 * 30
    elif gc_ratio > 400:
        gc_score = 10 + (gc_ratio - 400) / 100 * 30
    else:
        gc_score = max(0, gc_ratio / 400 * 10)
    components["gold_copper_ratio"] = {
        "value": round(gc_ratio, 1),
        "score": round(gc_score, 1),
        "signal": "high_risk" if gc_score > 60 else "watch" if gc_score > 35 else "normal",
        "weight": 0.30,
    }

    # 2. Yield curve (25%) — inverted = recession risk
    ys = yield_spread if yield_spread is not None else 0.5
    if ys < -0.5:
        yc_score = 90
    elif ys < 0:
        yc_score = 60 + abs(ys) / 0.5 * 30
    elif ys < 0.5:
        yc_score = 30 + (0.5 - ys) / 0.5 * 30
    elif ys < 1.5:
        yc_score = max(0, 30 - (ys - 0.5) / 1.0 * 30)
    else:
        yc_score = 0
    components["yield_curve"] = {
        "value": round(ys, 2),
        "score": round(yc_score, 1),
        "signal": "inverted" if ys < 0 else "flat" if ys < 0.5 else "normal",
        "weight": 0.25,
    }

    # 3. Oil pressure (20%) — high oil = inflation pressure
    oil = wti_crude or 70
    if oil > 100:
        oil_score = 80 + min(20, (oil - 100) / 20 * 20)
    elif oil > 90:
        oil_score = 55 + (oil - 90) / 10 * 25
    elif oil > 75:
        oil_score = 25 + (oil - 75) / 15 * 30
    elif oil > 55:
        oil_score = max(0, (oil - 55) / 20 * 25)
    else:
        oil_score = 0
    components["oil_pressure"] = {
        "value": round(oil, 2),
        "score": round(oil_score, 1),
        "signal": "high_inflation" if oil_score > 55 else "moderate" if oil_score > 25 else "stable",
        "weight": 0.20,
    }

    # 4. DXY tightening (15%) — strong dollar = tightening
    dxy = dxy_index or 103
    if dxy > 110:
        dxy_score = 85
    elif dxy > 106:
        dxy_score = 50 + (dxy - 106) / 4 * 35
    elif dxy > 103:
        dxy_score = 25 + (dxy - 103) / 3 * 25
    elif dxy > 100:
        dxy_score = max(0, (dxy - 100) / 3 * 25)
    else:
        dxy_score = 0
    components["dxy_tightening"] = {
        "value": round(dxy, 2),
        "score": round(dxy_score, 1),
        "signal": "tight" if dxy_score > 50 else "moderate" if dxy_score > 25 else "easy",
        "weight": 0.15,
    }

    # 5. Copper demand (10%) — weak copper = low growth
    cop = copper_price or 4.0
    if cop > 100:
        cop = cop / 100
    if cop < 3.0:
        cop_score = 80
    elif cop < 3.5:
        cop_score = 50 + (3.5 - cop) / 0.5 * 30
    elif cop < 4.0:
        cop_score = 20 + (4.0 - cop) / 0.5 * 30
    elif cop < 4.5:
        cop_score = max(0, (4.5 - cop) / 0.5 * 20)
    else:
        cop_score = 0
    components["copper_demand"] = {
        "value": round(cop, 2),
        "score": round(cop_score, 1),
        "signal": "weak_demand" if cop_score > 50 else "moderate" if cop_score > 20 else "strong",
        "weight": 0.10,
    }

    # Weighted composite
    index = (
        gc_score * 0.30
        + yc_score * 0.25
        + oil_score * 0.20
        + dxy_score * 0.15
        + cop_score * 0.10
    )
    index = round(max(0, min(100, index)), 1)

    if index < 30:
        level, level_kr = "Low", "양호"
    elif index < 50:
        level, level_kr = "Watch", "주의"
    elif index < 70:
        level, level_kr = "Elevated", "경계"
    else:
        level, level_kr = "High", "위험"

    return {
        "index": index,
        "level": level,
        "level_kr": level_kr,
        "components": components,
    }


# ── Cross-Market Recommendation ──


def compute_cross_market_recommendation(
    macro_data: dict | None,
    sentiment_data: dict | None,
    kr_fund_flow_summary: dict | None,
    us_etf_flow_summary: dict | None,
    kr_signal_stats: dict | None,
    us_signal_stats: dict | None,
) -> dict:
    """Compare KR vs US conditions and recommend market allocation bias.

    5 factors (each 20%): FX trend, volatility, yield environment,
    fund flow direction, signal momentum.

    Returns recommendation with factor breakdown and action items.
    """
    macro = macro_data or {}
    sent = sentiment_data or {}
    kr_flow = kr_fund_flow_summary or {}
    us_flow = us_etf_flow_summary or {}
    kr_stats = kr_signal_stats or {}
    us_stats = us_signal_stats or {}

    factors = {}
    kr_total = 0.0
    us_total = 0.0

    # Factor 1: FX trend (USD/KRW)
    usd_krw = macro.get("usd_krw") or 1350
    if usd_krw < 1300:
        fx_kr, fx_us = 0.8, -0.3
        fx_label = f"원화 강세 ({usd_krw:.0f}원) - KR 자금유입 유리"
    elif usd_krw < 1350:
        fx_kr, fx_us = 0.4, 0.0
        fx_label = f"환율 안정 ({usd_krw:.0f}원)"
    elif usd_krw < 1400:
        fx_kr, fx_us = -0.2, 0.3
        fx_label = f"원화 약세 ({usd_krw:.0f}원) - US 상대 유리"
    else:
        fx_kr, fx_us = -0.7, 0.5
        fx_label = f"원화 급락 ({usd_krw:.0f}원) - KR 외인매도 가속"
    factors["fx_trend"] = {"label": fx_label, "kr_impact": fx_kr, "us_impact": fx_us}
    kr_total += fx_kr * 0.20
    us_total += fx_us * 0.20

    # Factor 2: Volatility
    vix = macro.get("vix") or 18
    if vix < 15:
        vol_kr, vol_us = 0.5, 0.5
        vol_label = f"VIX 저변동성 ({vix:.1f}) - 양쪽 유리"
    elif vix < 20:
        vol_kr, vol_us = 0.3, 0.3
        vol_label = f"VIX 정상 ({vix:.1f})"
    elif vix < 28:
        vol_kr, vol_us = -0.3, 0.1
        vol_label = f"VIX 상승 ({vix:.1f}) - 이머징 불리"
    else:
        vol_kr, vol_us = -0.7, -0.3
        vol_label = f"VIX 급등 ({vix:.1f}) - 매수 자제"
    factors["volatility"] = {"label": vol_label, "kr_impact": vol_kr, "us_impact": vol_us}
    kr_total += vol_kr * 0.20
    us_total += vol_us * 0.20

    # Factor 3: Yield environment
    us_10y = macro.get("us_10y_yield") if macro.get("us_10y_yield") is not None else 4.0
    spread = macro.get("us_yield_spread") if macro.get("us_yield_spread") is not None else 0.5
    if us_10y < 3.5 and spread > 0:
        yld_kr, yld_us = 0.2, 0.6
        yld_label = f"금리 하락 (10Y={us_10y:.1f}%) - 성장주/US 유리"
    elif us_10y < 4.5 and spread > 0:
        yld_kr, yld_us = 0.2, 0.3
        yld_label = f"금리 안정 (10Y={us_10y:.1f}%)"
    elif spread < 0:
        yld_kr, yld_us = -0.4, -0.2
        yld_label = f"수익률곡선 역전 (spread={spread:.2f}%) - 경기침체 우려"
    else:
        yld_kr, yld_us = -0.2, -0.3
        yld_label = f"금리 상승 (10Y={us_10y:.1f}%) - 밸류에이션 부담"
    factors["yield_env"] = {"label": yld_label, "kr_impact": yld_kr, "us_impact": yld_us}
    kr_total += yld_kr * 0.20
    us_total += yld_us * 0.20

    # Factor 4: Fund flow direction
    kr_foreign = kr_flow.get("total_foreign_net", 0)
    us_etf_score = us_flow.get("risk_appetite_score", 0)
    if kr_foreign > 0:
        flow_kr = min(0.7, kr_foreign / 500_000_000_000 * 0.7)  # scale by 5000억
    else:
        flow_kr = max(-0.7, kr_foreign / 500_000_000_000 * 0.7)
    flow_us = min(0.7, max(-0.7, us_etf_score * 0.7)) if us_etf_score else 0
    flow_label_parts = []
    if kr_foreign != 0:
        flow_label_parts.append(f"KR 외국인 {'순매수' if kr_foreign > 0 else '순매도'}")
    if us_etf_score:
        flow_label_parts.append(f"US ETF {'Risk-On' if us_etf_score > 0 else 'Risk-Off'}")
    flow_label = " / ".join(flow_label_parts) if flow_label_parts else "수급 데이터 부족"
    factors["fund_flow"] = {"label": flow_label, "kr_impact": round(flow_kr, 2), "us_impact": round(flow_us, 2)}
    kr_total += flow_kr * 0.20
    us_total += flow_us * 0.20

    # Factor 5: Signal momentum
    kr_avg = kr_stats.get("avg_score") if kr_stats.get("avg_score") is not None else 0
    us_avg = us_stats.get("avg_score") if us_stats.get("avg_score") is not None else 0
    mom_kr = min(0.7, max(-0.7, kr_avg / 30))  # normalize from -30..+30 range
    mom_us = min(0.7, max(-0.7, us_avg / 30))
    mom_label = f"KR 평균스코어 {kr_avg:.1f} / US 평균스코어 {us_avg:.1f}"
    factors["signal_momentum"] = {"label": mom_label, "kr_impact": round(mom_kr, 2), "us_impact": round(mom_us, 2)}
    kr_total += mom_kr * 0.20
    us_total += mom_us * 0.20

    kr_total = round(kr_total, 2)
    us_total = round(us_total, 2)

    # Determine recommendation
    diff = kr_total - us_total
    if kr_total < -0.2 and us_total < -0.2:
        rec, rec_kr = "Caution", "관망"
    elif diff > 0.15:
        rec, rec_kr = "KR Favorable", "KR유리"
    elif diff < -0.15:
        rec, rec_kr = "US Favorable", "US유리"
    else:
        rec, rec_kr = "Both OK", "양쪽유리"

    # Generate action items
    action_items = _generate_action_items(macro, sent, factors, rec)

    return {
        "recommendation": rec,
        "recommendation_kr": rec_kr,
        "kr_score": kr_total,
        "us_score": us_total,
        "factors": factors,
        "action_items": action_items,
    }


def _generate_action_items(macro: dict, sent: dict, factors: dict, rec: str) -> list[str]:
    """Generate actionable Korean advice from analysis."""
    items = []
    vix = macro.get("vix") or 18
    fg = sent.get("fear_greed_index") or 50
    usd_krw = macro.get("usd_krw") or 1350

    if vix > 25:
        items.append(f"VIX {vix:.0f} 고수준 — 신규 매수 자제, VIX 20 이하 안정 시 진입 검토")
    elif vix < 15:
        items.append(f"VIX {vix:.0f} 극저변동 — 풋옵션 헤지 고려 (급등 가능)")

    if fg < 25:
        items.append(f"공포지수 {fg} (극단 공포) — 역발상 매수 기회 탐색")
    elif fg > 75:
        items.append(f"공포지수 {fg} (극단 탐욕) — 익절/비중 축소 검토")

    if usd_krw > 1380:
        items.append(f"환율 {usd_krw:.0f}원 고수준 — KR 비중 축소, 환율 1350 하회 시 KR 비중 확대")
    elif usd_krw < 1300:
        items.append(f"환율 {usd_krw:.0f}원 안정 — KR 외인 수급 양호 예상")

    if rec == "Caution":
        items.append("양쪽 시장 모두 불리한 환경 — 현금 비중 확대, 분할 매수 전략")
    elif rec == "KR Favorable":
        items.append("KR 시장 상대 유리 — 원화 예수금 활용, KR 비중 확대 검토")
    elif rec == "US Favorable":
        items.append("US 시장 상대 유리 — 환전 후 US 주식/ETF 투자 검토")

    if not items:
        items.append("현재 특이 시그널 없음 — 기존 포지션 유지")

    return items


# ── Sector Fund Flow Aggregation ──


def aggregate_sector_fund_flow(
    fund_flow_rows: list[dict],
    sector_map: dict[str, str],
) -> list[dict]:
    """Aggregate symbol-level fund flow into sector-level totals.

    Returns list sorted by total_net descending.
    """
    sector_agg: dict[str, dict] = {}

    for row in fund_flow_rows:
        symbol = row.get("symbol", "")
        sector = sector_map.get(symbol, "기타")
        if sector not in sector_agg:
            sector_agg[sector] = {
                "sector": sector,
                "foreign_net": 0,
                "institution_net": 0,
                "individual_net": 0,
                "total_net": 0,
                "symbol_count": 0,
                "symbols": {},
            }
        s = sector_agg[sector]
        fn = row.get("foreign_net_buy") or 0
        inst = row.get("institution_net_buy") or 0
        ind = row.get("individual_net_buy") or 0
        s["foreign_net"] += fn
        s["institution_net"] += inst
        s["individual_net"] += ind
        s["total_net"] += fn + inst
        if symbol not in s["symbols"]:
            s["symbols"][symbol] = 0
            s["symbol_count"] += 1
        s["symbols"][symbol] += fn + inst

    results = []
    for s in sector_agg.values():
        # Convert symbols dict to sorted top list
        top = sorted(s["symbols"].items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        s["top_symbols"] = [{"symbol": sym, "net": round(n)} for sym, n in top]
        del s["symbols"]
        s["foreign_net"] = round(s["foreign_net"])
        s["institution_net"] = round(s["institution_net"])
        s["individual_net"] = round(s["individual_net"])
        s["total_net"] = round(s["total_net"])
        results.append(s)

    results.sort(key=lambda x: x["total_net"], reverse=True)
    return results


def compute_sector_rotation(
    current_flow: list[dict],
    previous_flow: list[dict],
) -> list[dict]:
    """Detect sector rotation by comparing current vs previous period flow.

    Both inputs are outputs of aggregate_sector_fund_flow().
    """
    curr_ranked = {s["sector"]: (i + 1, s["total_net"]) for i, s in enumerate(current_flow)}
    prev_ranked = {s["sector"]: (i + 1, s["total_net"]) for i, s in enumerate(previous_flow)}

    all_sectors = set(curr_ranked.keys()) | set(prev_ranked.keys())
    results = []

    for sector in all_sectors:
        curr_rank, curr_net = curr_ranked.get(sector, (len(all_sectors), 0))
        prev_rank, prev_net = prev_ranked.get(sector, (len(all_sectors), 0))
        rank_change = prev_rank - curr_rank  # positive = improved

        if curr_net > 0 and rank_change > 0:
            signal = "Inflow"
        elif curr_net < 0 and rank_change < 0:
            signal = "Outflow"
        elif abs(rank_change) <= 1:
            signal = "Stable"
        elif rank_change > 0:
            signal = "Inflow"
        else:
            signal = "Outflow"

        flow_change = curr_net - prev_net
        results.append({
            "sector": sector,
            "current_rank": curr_rank,
            "previous_rank": prev_rank,
            "rank_change": rank_change,
            "current_net": curr_net,
            "flow_change": round(flow_change),
            "signal": signal,
        })

    results.sort(key=lambda x: x["current_rank"])
    return results


# ── Crisis Hedge: Relative Strength ──

DEFENSE_SECTORS = {
    "방산/항공", "에너지/플랜트", "유틸리티", "통신", "보험",
    "Energy", "Healthcare",
}

# KR symbols → "KR", US symbols → "US"
_KR_SECTOR_PREFIXES = {
    "반도체", "배터리", "바이오", "자동차", "인터넷", "금융",
    "방산/항공", "조선/중공업", "전기/전력장비", "유틸리티",
    "화학", "철강", "통신", "지주", "보험", "전자", "소비재",
    "에너지/플랜트",
}


def compute_relative_strength(
    symbol_returns: dict[str, float],
    benchmark_returns: dict[str, float],
    sector_map: dict[str, str],
    risk_regime_score: float | None = None,
) -> list[dict]:
    """Compute relative strength for symbols vs their market benchmark.

    Args:
        symbol_returns: {symbol: N-day return pct} (e.g. {"005930": -2.5})
        benchmark_returns: {"KR": float, "US": float} (benchmark returns)
        sector_map: {symbol: sector} mapping
        risk_regime_score: If < -0.3, defense sectors with RS > 1.0
                          are flagged as hedge candidates.

    Returns:
        Sorted list (by rs_ratio desc) of symbol RS data.
    """
    results = []

    for symbol, ret in symbol_returns.items():
        sector = sector_map.get(symbol, "Unknown")
        if sector in ("ETF",):
            continue  # Skip benchmark ETFs

        # Determine market
        if sector in _KR_SECTOR_PREFIXES:
            market = "KR"
        else:
            market = "US"

        bench_ret = benchmark_returns.get(market, 0.0)

        # RS ratio: (1 + stock_return) / (1 + benchmark_return)
        stock_factor = 1.0 + ret / 100.0
        bench_factor = 1.0 + bench_ret / 100.0

        if abs(bench_factor) < 0.001:
            # Benchmark near zero — use raw return comparison
            rs_ratio = 1.0 + (ret - bench_ret) / 100.0
        else:
            rs_ratio = stock_factor / bench_factor

        is_defense = sector in DEFENSE_SECTORS
        is_hedge = (
            is_defense
            and rs_ratio > 1.0
            and risk_regime_score is not None
            and risk_regime_score < -0.3
        )

        results.append({
            "symbol": symbol,
            "sector": sector,
            "market": market,
            "return_pct": round(ret, 2),
            "benchmark_return": round(bench_ret, 2),
            "rs_ratio": round(rs_ratio, 4),
            "is_defense_sector": is_defense,
            "is_hedge_candidate": is_hedge,
        })

    results.sort(key=lambda x: x["rs_ratio"], reverse=True)
    return results


# ── Scenario Entry Levels ──


def compute_entry_scenarios(
    benchmark_prices: dict[str, list[dict]],
    fx_prices: list[dict] | None = None,
    macro_data: dict | None = None,
    risk_score: float | None = None,
) -> dict:
    """Compute 3-scenario entry level matrix from MA support/resistance.

    Args:
        benchmark_prices: {"KOSPI": [...], "SPY": [...]}
            Each list: [{"trade_date": str, "close": float}, ...] oldest→newest
        fx_prices: [{"indicator_date": str, "close": float}, ...] for USD/KRW
        macro_data: Latest macro_indicators row
        risk_score: Unified risk score (0-100) for probability bias

    Returns:
        dict with benchmarks MA data, fx data, scenarios, and probability_bias
    """
    benchmarks: dict[str, dict] = {}

    for key in ("KOSPI", "SPY"):
        prices = benchmark_prices.get(key, [])
        closes = [p.get("close", 0) for p in prices if p.get("close")]
        if not closes:
            benchmarks[key] = _empty_benchmark()
            continue

        current = closes[-1]
        ma20 = sum(closes[-20:]) / min(len(closes), 20) if len(closes) >= 20 else current
        ma60 = sum(closes[-60:]) / min(len(closes), 60) if len(closes) >= 60 else current
        ma120 = sum(closes[-120:]) / min(len(closes), 120) if len(closes) >= 120 else current

        benchmarks[key] = {
            "current": round(current, 2),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
            "ma120": round(ma120, 2),
            "support_zone": [round(min(ma60, ma120), 2), round(max(ma60, ma120), 2)],
            "resistance_zone": [round(min(current, ma20), 2), round(max(current, ma20), 2)],
        }

    # FX data
    fx_result: dict = {"usd_krw_current": None, "ma20": None, "ma60": None, "ma120": None}
    if fx_prices:
        fx_closes = [p.get("close") or p.get("usd_krw") for p in fx_prices if (p.get("close") or p.get("usd_krw"))]
        if fx_closes:
            fx_result["usd_krw_current"] = round(fx_closes[-1], 1)
            if len(fx_closes) >= 20:
                fx_result["ma20"] = round(sum(fx_closes[-20:]) / 20, 1)
            if len(fx_closes) >= 60:
                fx_result["ma60"] = round(sum(fx_closes[-60:]) / 60, 1)
            if len(fx_closes) >= 120:
                fx_result["ma120"] = round(sum(fx_closes[-120:]) / 120, 1)

            # Inflection zone: between MA60 and MA120
            if fx_result["ma60"] and fx_result["ma120"]:
                fx_result["inflection_zone"] = [
                    round(min(fx_result["ma60"], fx_result["ma120"]), 1),
                    round(max(fx_result["ma60"], fx_result["ma120"]), 1),
                ]

    # Build 3 scenarios
    kospi = benchmarks.get("KOSPI", _empty_benchmark())
    spy = benchmarks.get("SPY", _empty_benchmark())

    scenarios = {
        "best": {
            "label": "Best",
            "label_kr": "낙관",
            "conditions_kr": "VIX 정상화(<20), 환율 안정, 매크로 개선",
            "kospi_range": _scenario_range(kospi, "best"),
            "spy_range": _scenario_range(spy, "best"),
            "usd_krw_range": _fx_scenario_range(fx_result, "best"),
            "action_kr": "적극적 분할 매수 시작. MA20 돌파 시 추가 매수.",
        },
        "base": {
            "label": "Base",
            "label_kr": "기본",
            "conditions_kr": "현재 추세 지속, 매크로 횡보",
            "kospi_range": _scenario_range(kospi, "base"),
            "spy_range": _scenario_range(spy, "base"),
            "usd_krw_range": _fx_scenario_range(fx_result, "base"),
            "action_kr": "MA60 지지 확인 후 선별적 분할 매수. 비중 30% 이내.",
        },
        "worst": {
            "label": "Worst",
            "label_kr": "비관",
            "conditions_kr": "위기 심화, VIX 30+, 환율 급등, 글로벌 리스크 오프",
            "kospi_range": _scenario_range(kospi, "worst"),
            "spy_range": _scenario_range(spy, "worst"),
            "usd_krw_range": _fx_scenario_range(fx_result, "worst"),
            "action_kr": "현금 비중 극대화. MA120 이탈 시 전량 방어. 역발상 매수는 VIX 피크 확인 후.",
        },
    }

    # Probability bias from risk score
    if risk_score is not None:
        if risk_score > 60:
            prob_bias = "worst"
        elif risk_score < 30:
            prob_bias = "best"
        else:
            prob_bias = "base"
    else:
        prob_bias = "base"

    return {
        "benchmarks": benchmarks,
        "fx": fx_result,
        "scenarios": scenarios,
        "probability_bias": prob_bias,
    }


def _empty_benchmark() -> dict:
    return {"current": 0, "ma20": 0, "ma60": 0, "ma120": 0,
            "support_zone": [0, 0], "resistance_zone": [0, 0]}


def _scenario_range(bm: dict, scenario: str) -> list[float]:
    """Compute benchmark range for a scenario."""
    current = bm.get("current", 0)
    ma20 = bm.get("ma20", 0)
    ma60 = bm.get("ma60", 0)
    ma120 = bm.get("ma120", 0)

    if current == 0:
        return [0, 0]

    if scenario == "best":
        low, high = round(ma20, 2), round(current * 1.05, 2)
    elif scenario == "base":
        low, high = round(ma60, 2), round(ma20, 2)
    else:  # worst
        low, high = round(ma120 * 0.95, 2), round(ma60, 2)

    # Ensure [low, high] order even when MAs cross in downtrends
    return [min(low, high), max(low, high)]


def _fx_scenario_range(fx: dict, scenario: str) -> list[float]:
    """Compute USD/KRW range for a scenario."""
    current = fx.get("usd_krw_current")
    ma60 = fx.get("ma60")
    ma120 = fx.get("ma120")

    if current is None:
        return [0, 0]

    if scenario == "best":
        # Currency stabilizing / KRW strengthening
        target_low = current * 0.97
        target_high = current
        return [round(target_low, 1), round(target_high, 1)]
    elif scenario == "base":
        # Current range continues
        return [round(current * 0.98, 1), round(current * 1.02, 1)]
    else:  # worst
        # KRW weakening further
        return [round(current, 1), round(current * 1.05, 1)]
