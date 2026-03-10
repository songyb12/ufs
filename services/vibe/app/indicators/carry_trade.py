"""Carry trade (엔캐리 트레이드) and global macro risk factor indicators.

Pure computation functions — no DB access.
Used by app.routers.macro_intel for carry trade, forex, and global risk endpoints.
"""

from __future__ import annotations

# ── Carry Trade Analysis ──

# Major carry trade pairs: funding currencies (low rate) → investing currencies (high rate)
CARRY_PAIRS = {
    "JPY_USD": {
        "funding": "JPY",
        "investing": "USD",
        "label": "엔캐리 (JPY→USD)",
        "label_en": "Yen Carry (JPY→USD)",
        "fx_symbol": "USD/JPY",
        "description_kr": "일본 저금리 자금으로 미국 고금리 자산 투자",
    },
    "JPY_KRW": {
        "funding": "JPY",
        "investing": "KRW",
        "label": "엔캐리 (JPY→KRW)",
        "label_en": "Yen Carry (JPY→KRW)",
        "fx_symbol": "JPY/KRW",
        "description_kr": "일본 저금리 자금으로 한국 자산 투자 (외인 수급 영향)",
    },
    "CHF_USD": {
        "funding": "CHF",
        "investing": "USD",
        "label": "스위스캐리 (CHF→USD)",
        "label_en": "Swiss Carry (CHF→USD)",
        "fx_symbol": "USD/CHF",
        "description_kr": "스위스 저금리 자금으로 미국 자산 투자",
    },
    "EUR_USD": {
        "funding": "EUR",
        "investing": "USD",
        "label": "유로캐리 (EUR→USD)",
        "label_en": "Euro Carry (EUR→USD)",
        "fx_symbol": "EUR/USD",
        "description_kr": "유럽 저금리 자금으로 미국 자산 투자",
    },
    "CNY_USD": {
        "funding": "CNY",
        "investing": "USD",
        "label": "위안캐리 (CNY→USD)",
        "label_en": "Yuan Carry (CNY→USD)",
        "fx_symbol": "USD/CNY",
        "description_kr": "중국 위안화 약세 시 달러 자산 선호",
    },
}


def compute_carry_trade_risk(
    interest_rates: dict[str, float | None],
    fx_data: dict[str, dict | None],
    vix: float | None = None,
    dxy: float | None = None,
) -> dict:
    """Compute carry trade risk assessment.

    Args:
        interest_rates: {"JPY": 0.1, "USD": 5.25, "KRW": 3.5, ...} — central bank rates
        fx_data: {"USD/JPY": {"current": 150.5, "change_1d": -0.5, "change_1w": 1.2, "change_1m": -3.0}, ...}
        vix: VIX index value
        dxy: Dollar Index value

    Returns:
        Comprehensive carry trade risk analysis dict
    """
    rates = interest_rates or {}
    pairs_analysis = []

    for pair_id, pair_info in CARRY_PAIRS.items():
        funding_rate = rates.get(pair_info["funding"])
        investing_rate = rates.get(pair_info["investing"])

        fx = (fx_data or {}).get(pair_info["fx_symbol"], {}) or {}
        fx_current = fx.get("current")
        fx_change_1d = fx.get("change_1d", 0)
        fx_change_1w = fx.get("change_1w", 0)
        fx_change_1m = fx.get("change_1m", 0)

        # Rate differential
        if funding_rate is not None and investing_rate is not None:
            rate_diff = investing_rate - funding_rate
        else:
            rate_diff = None

        # Carry attractiveness (0-100)
        carry_score = _compute_carry_score(rate_diff, fx_change_1m)

        # Unwind risk assessment
        unwind_risk = _compute_unwind_risk(
            fx_change_1d=fx_change_1d,
            fx_change_1w=fx_change_1w,
            fx_change_1m=fx_change_1m,
            vix=vix,
            funding_currency=pair_info["funding"],
        )

        # Market impact
        impact = _assess_market_impact(
            pair_info["funding"],
            pair_info["investing"],
            unwind_risk["risk_level"],
            rate_diff,
        )

        pairs_analysis.append({
            "pair_id": pair_id,
            **pair_info,
            "funding_rate": funding_rate,
            "investing_rate": investing_rate,
            "rate_differential": round(rate_diff, 2) if rate_diff is not None else None,
            "fx_current": fx_current,
            "fx_change_1d_pct": round(fx_change_1d, 2) if fx_change_1d else 0,
            "fx_change_1w_pct": round(fx_change_1w, 2) if fx_change_1w else 0,
            "fx_change_1m_pct": round(fx_change_1m, 2) if fx_change_1m else 0,
            "carry_score": carry_score,
            "unwind_risk": unwind_risk,
            "market_impact": impact,
        })

    # Overall carry trade risk
    overall_risk = _compute_overall_carry_risk(pairs_analysis, vix, dxy)

    return {
        "pairs": pairs_analysis,
        "overall_risk": overall_risk,
        "vix": vix,
        "dxy": dxy,
    }


def _compute_carry_score(rate_diff: float | None, fx_change_1m: float) -> int:
    """0-100 score for carry attractiveness. Higher = more attractive."""
    if rate_diff is None:
        return 50

    score = 50.0

    # Rate differential contribution (±30)
    if rate_diff > 4:
        score += 30
    elif rate_diff > 3:
        score += 20
    elif rate_diff > 2:
        score += 10
    elif rate_diff > 1:
        score += 5
    elif rate_diff < 0:
        score -= 20

    # FX stability contribution (±20)
    if abs(fx_change_1m) < 1:
        score += 20  # Stable FX = good for carry
    elif abs(fx_change_1m) < 3:
        score += 10
    elif abs(fx_change_1m) > 5:
        score -= 15  # Volatile = risky

    return max(0, min(100, int(score)))


def _compute_unwind_risk(
    fx_change_1d: float,
    fx_change_1w: float,
    fx_change_1m: float,
    vix: float | None,
    funding_currency: str,
) -> dict:
    """Assess carry trade unwind risk."""
    risk_score = 0.0
    signals = []

    # Sudden FX move (funding currency strengthening = unwind)
    # For JPY carry: JPY strengthening = USD/JPY dropping = negative change
    if funding_currency == "JPY":
        # USD/JPY dropping means JPY strengthening = unwind signal
        if fx_change_1d < -1.0:
            risk_score += 30
            signals.append(f"JPY 급등 (1일 {fx_change_1d:+.1f}%) — 급격한 엔고")
        elif fx_change_1d < -0.5:
            risk_score += 15
            signals.append(f"JPY 강세 (1일 {fx_change_1d:+.1f}%)")

        if fx_change_1w < -2.0:
            risk_score += 25
            signals.append(f"주간 엔고 추세 ({fx_change_1w:+.1f}%)")

        if fx_change_1m < -5.0:
            risk_score += 20
            signals.append(f"월간 엔고 가속 ({fx_change_1m:+.1f}%) — 대규모 청산 우려")
    else:
        # Generic: funding currency strengthening check
        if fx_change_1d < -1.0:
            risk_score += 25
            signals.append(f"{funding_currency} 급등 (1일 {fx_change_1d:+.1f}%)")
        if fx_change_1w < -2.0:
            risk_score += 20
            signals.append(f"{funding_currency} 주간 강세 ({fx_change_1w:+.1f}%)")

    # VIX spike = risk-off = carry unwind
    v = vix or 18
    if v > 30:
        risk_score += 25
        signals.append(f"VIX {v:.0f} — 극단적 리스크오프, 캐리 청산 가속")
    elif v > 25:
        risk_score += 15
        signals.append(f"VIX {v:.0f} — 리스크오프 확대")
    elif v > 20:
        risk_score += 5

    risk_score = min(100, risk_score)

    if risk_score >= 60:
        risk_level = "HIGH"
        risk_level_kr = "위험"
    elif risk_score >= 35:
        risk_level = "ELEVATED"
        risk_level_kr = "경계"
    elif risk_score >= 15:
        risk_level = "WATCH"
        risk_level_kr = "주의"
    else:
        risk_level = "LOW"
        risk_level_kr = "양호"

    if not signals:
        signals.append("현재 특이 신호 없음")

    return {
        "risk_score": int(risk_score),
        "risk_level": risk_level,
        "risk_level_kr": risk_level_kr,
        "signals": signals,
    }


def _assess_market_impact(
    funding: str,
    investing: str,
    risk_level: str,
    rate_diff: float | None,
) -> dict:
    """Assess market impact of carry trade / unwind."""
    impacts = []

    if funding == "JPY":
        if risk_level in ("HIGH", "ELEVATED"):
            impacts.append({
                "market": "KR",
                "direction": "negative",
                "reason_kr": "엔캐리 청산 시 KR 외인 자금 유출 가속",
                "sectors_affected": ["반도체", "자동차", "바이오"],
            })
            impacts.append({
                "market": "US",
                "direction": "negative",
                "reason_kr": "글로벌 리스크오프, 미국 성장주 매도 압력",
                "sectors_affected": ["Tech", "Growth"],
            })
            impacts.append({
                "market": "GLOBAL",
                "direction": "negative",
                "reason_kr": "글로벌 유동성 축소, 이머징 시장 자금 유출",
                "sectors_affected": ["EM Equity", "High Yield"],
            })
        else:
            impacts.append({
                "market": "KR",
                "direction": "positive",
                "reason_kr": "엔캐리 유지 시 KR 외인 자금 유입 지속",
                "sectors_affected": ["반도체", "금융"],
            })

    if investing == "USD" and rate_diff is not None and rate_diff > 3:
        impacts.append({
            "market": "EM",
            "direction": "negative",
            "reason_kr": f"금리차 {rate_diff:.1f}% — 이머징 자금 유출 압력",
            "sectors_affected": ["EM Bonds", "EM Equity"],
        })

    return {"impacts": impacts}


def _compute_overall_carry_risk(
    pairs: list[dict],
    vix: float | None,
    dxy: float | None,
) -> dict:
    """Compute overall carry trade environment risk."""
    if not pairs:
        return {"score": 0, "level": "Unknown", "level_kr": "데이터 없음", "advice": []}

    # Weighted average of unwind risks (JPY carry has 2x weight)
    total_weight = 0
    weighted_score = 0
    for p in pairs:
        weight = 2.0 if p["funding"] == "JPY" else 1.0
        weighted_score += p["unwind_risk"]["risk_score"] * weight
        total_weight += weight

    avg_risk = weighted_score / total_weight if total_weight else 0

    # DXY contribution
    d = dxy or 103
    if d > 108:
        avg_risk += 10  # Strong dollar = pressure on carry
    elif d > 105:
        avg_risk += 5

    avg_risk = min(100, avg_risk)

    if avg_risk >= 60:
        level, level_kr = "HIGH", "위험"
    elif avg_risk >= 35:
        level, level_kr = "ELEVATED", "경계"
    elif avg_risk >= 15:
        level, level_kr = "WATCH", "주의"
    else:
        level, level_kr = "LOW", "양호"

    advice = _generate_carry_advice(avg_risk, pairs, vix, dxy)

    return {
        "score": int(avg_risk),
        "level": level,
        "level_kr": level_kr,
        "advice": advice,
    }


def _generate_carry_advice(
    risk_score: float,
    pairs: list[dict],
    vix: float | None,
    dxy: float | None,
) -> list[str]:
    """Generate actionable Korean advice for carry trade environment."""
    advice = []

    if risk_score >= 60:
        advice.append("캐리 트레이드 대규모 청산 위험 — 리스크 자산 비중 즉시 축소")
        advice.append("KR 시장 외인 매도 가속 가능성 — 방어주/현금 비중 확대")
        advice.append("VIX 안정 및 엔화 약세 전환 확인 후 재진입")
    elif risk_score >= 35:
        advice.append("캐리 트레이드 환경 악화 중 — 신규 매수 자제")
        advice.append("환율 및 BOJ 정책 발표 모니터링 강화")
    elif risk_score >= 15:
        advice.append("캐리 환경 소폭 변동 — 포지션 유지하되 헤지 고려")
    else:
        advice.append("캐리 트레이드 환경 안정 — 리스크 자산 투자 가능")

    # JPY-specific
    jpy_pair = next((p for p in pairs if p["funding"] == "JPY"), None)
    if jpy_pair:
        jpy_risk = jpy_pair["unwind_risk"]["risk_score"]
        if jpy_risk >= 50:
            advice.append(f"엔캐리 청산 위험 {jpy_risk}점 — 일본 BOJ 금리인상/YCC 조정 확인 필요")

    v = vix or 18
    if v > 25:
        advice.append(f"VIX {v:.0f} 고수준 — 캐리 청산과 리스크오프 동시 진행 가능")

    return advice


# ── Global Forex Analysis ──

CURRENCY_INFO = {
    "USD": {"name": "미국 달러", "country": "미국", "lat": 38.9, "lon": -77.0, "flag": "🇺🇸"},
    "JPY": {"name": "일본 엔", "country": "일본", "lat": 35.7, "lon": 139.7, "flag": "🇯🇵"},
    "EUR": {"name": "유로", "country": "유럽연합", "lat": 50.8, "lon": 4.4, "flag": "🇪🇺"},
    "GBP": {"name": "영국 파운드", "country": "영국", "lat": 51.5, "lon": -0.1, "flag": "🇬🇧"},
    "CHF": {"name": "스위스 프랑", "country": "스위스", "lat": 46.9, "lon": 7.4, "flag": "🇨🇭"},
    "CNY": {"name": "중국 위안", "country": "중국", "lat": 39.9, "lon": 116.4, "flag": "🇨🇳"},
    "KRW": {"name": "한국 원", "country": "한국", "lat": 37.6, "lon": 127.0, "flag": "🇰🇷"},
    "AUD": {"name": "호주 달러", "country": "호주", "lat": -33.9, "lon": 151.2, "flag": "🇦🇺"},
    "CAD": {"name": "캐나다 달러", "country": "캐나다", "lat": 45.4, "lon": -75.7, "flag": "🇨🇦"},
    "INR": {"name": "인도 루피", "country": "인도", "lat": 28.6, "lon": 77.2, "flag": "🇮🇳"},
    "BRL": {"name": "브라질 헤알", "country": "브라질", "lat": -15.8, "lon": -47.9, "flag": "🇧🇷"},
    "MXN": {"name": "멕시코 페소", "country": "멕시코", "lat": 19.4, "lon": -99.1, "flag": "🇲🇽"},
    "TWD": {"name": "대만 달러", "country": "대만", "lat": 25.0, "lon": 121.5, "flag": "🇹🇼"},
    "SGD": {"name": "싱가포르 달러", "country": "싱가포르", "lat": 1.3, "lon": 103.8, "flag": "🇸🇬"},
    "HKD": {"name": "홍콩 달러", "country": "홍콩", "lat": 22.3, "lon": 114.2, "flag": "🇭🇰"},
    "SEK": {"name": "스웨덴 크로나", "country": "스웨덴", "lat": 59.3, "lon": 18.1, "flag": "🇸🇪"},
    "NOK": {"name": "노르웨이 크로네", "country": "노르웨이", "lat": 59.9, "lon": 10.8, "flag": "🇳🇴"},
    "ZAR": {"name": "남아공 랜드", "country": "남아공", "lat": -25.7, "lon": 28.2, "flag": "🇿🇦"},
    "TRY": {"name": "터키 리라", "country": "터키", "lat": 39.9, "lon": 32.9, "flag": "🇹🇷"},
    "THB": {"name": "태국 바트", "country": "태국", "lat": 13.8, "lon": 100.5, "flag": "🇹🇭"},
    "VND": {"name": "베트남 동", "country": "베트남", "lat": 21.0, "lon": 105.8, "flag": "🇻🇳"},
    "IDR": {"name": "인도네시아 루피아", "country": "인도네시아", "lat": -6.2, "lon": 106.8, "flag": "🇮🇩"},
    "PHP": {"name": "필리핀 페소", "country": "필리핀", "lat": 14.6, "lon": 121.0, "flag": "🇵🇭"},
    "PLN": {"name": "폴란드 즐로티", "country": "폴란드", "lat": 52.2, "lon": 21.0, "flag": "🇵🇱"},
    "CZK": {"name": "체코 코루나", "country": "체코", "lat": 50.1, "lon": 14.4, "flag": "🇨🇿"},
    "RUB": {"name": "러시아 루블", "country": "러시아", "lat": 55.8, "lon": 37.6, "flag": "🇷🇺"},
    "SAR": {"name": "사우디 리얄", "country": "사우디", "lat": 24.7, "lon": 46.7, "flag": "🇸🇦"},
    "NZD": {"name": "뉴질랜드 달러", "country": "뉴질랜드", "lat": -41.3, "lon": 174.8, "flag": "🇳🇿"},
}

# FDR-compatible symbols for major forex pairs
FOREX_FDR_SYMBOLS = {
    "USD/JPY": "USD/JPY",
    "EUR/USD": "EUR/USD",
    "GBP/USD": "GBP/USD",
    "USD/CHF": "USD/CHF",
    "USD/CNY": "USD/CNY",
    "USD/KRW": "USD/KRW",
    "AUD/USD": "AUD/USD",
    "USD/CAD": "USD/CAD",
    "USD/INR": "USD/INR",
    "USD/BRL": "USD/BRL",
    "USD/MXN": "USD/MXN",
    "USD/TWD": "USD/TWD",
    "USD/SGD": "USD/SGD",
    "USD/HKD": "USD/HKD",
    "USD/SEK": "USD/SEK",
    "USD/NOK": "USD/NOK",
    "USD/ZAR": "USD/ZAR",
    "USD/TRY": "USD/TRY",
    "USD/THB": "USD/THB",
    "USD/IDR": "USD/IDR",
    "USD/PHP": "USD/PHP",
    "USD/PLN": "USD/PLN",
    "NZD/USD": "NZD/USD",
}


def compute_forex_map_data(
    fx_rates: dict[str, dict],
    interest_rates: dict[str, float | None],
    dxy: float | None = None,
    vix: float | None = None,
) -> dict:
    """Compute world map data for forex visualization.

    Args:
        fx_rates: {"USD/JPY": {"current": 150.5, "change_1d": -0.3, "change_1w": 1.2, ...}, ...}
        interest_rates: {"USD": 5.25, "JPY": 0.1, ...}
        dxy: Dollar Index
        vix: VIX

    Returns:
        World map ready data with countries, flows, and analysis
    """
    countries = []

    for currency, info in CURRENCY_INFO.items():
        rate_info = interest_rates.get(currency)

        # Find FX pair vs USD
        fx_pair = None
        fx_data = {}
        if currency != "USD":
            for pair_key, pair_val in fx_rates.items():
                if currency in pair_key:
                    fx_pair = pair_key
                    fx_data = pair_val or {}
                    break

        # Strength indicator: how is this currency performing vs USD
        strength = _compute_currency_strength(currency, fx_data)

        countries.append({
            "currency": currency,
            **info,
            "interest_rate": rate_info,
            "fx_pair": fx_pair,
            "fx_current": fx_data.get("current"),
            "fx_change_1d": fx_data.get("change_1d", 0),
            "fx_change_1w": fx_data.get("change_1w", 0),
            "fx_change_1m": fx_data.get("change_1m", 0),
            "strength": strength,
        })

    # Capital flow arrows (from low-rate to high-rate countries)
    flows = _compute_capital_flows(countries)

    # DXY impact
    dxy_analysis = _analyze_dxy_impact(dxy)

    return {
        "countries": countries,
        "flows": flows,
        "dxy": dxy,
        "dxy_analysis": dxy_analysis,
        "vix": vix,
    }


def _compute_currency_strength(currency: str, fx_data: dict) -> dict:
    """Compute currency strength indicator."""
    change_1d = fx_data.get("change_1d", 0) or 0
    change_1w = fx_data.get("change_1w", 0) or 0
    change_1m = fx_data.get("change_1m", 0) or 0

    if currency == "USD":
        # USD strength is measured by DXY, handled separately
        return {"score": 0, "label": "기준통화", "label_en": "Base", "color": "#6b7280"}

    # For pairs like USD/XXX: positive change = XXX weakening
    # For pairs like XXX/USD: positive change = XXX strengthening
    # We need to normalize: positive = currency strengthening

    # Composite score (weighted)
    score = -(change_1d * 0.3 + change_1w * 0.3 + change_1m * 0.4)

    if score > 3:
        label, label_en, color = "강세", "Strong", "#22c55e"
    elif score > 1:
        label, label_en, color = "소폭 강세", "Mild Strong", "#86efac"
    elif score > -1:
        label, label_en, color = "보합", "Neutral", "#6b7280"
    elif score > -3:
        label, label_en, color = "소폭 약세", "Mild Weak", "#fca5a5"
    else:
        label, label_en, color = "약세", "Weak", "#ef4444"

    return {
        "score": round(score, 2),
        "label": label,
        "label_en": label_en,
        "color": color,
    }


def _compute_capital_flows(countries: list[dict]) -> list[dict]:
    """Compute capital flow arrows between countries based on rate differentials."""
    flows = []
    rated_countries = [c for c in countries if c.get("interest_rate") is not None]

    # Sort by rate to find natural carry flow direction
    rated_countries.sort(key=lambda x: x["interest_rate"])

    # Low rate (funding) → High rate (investing)
    if len(rated_countries) >= 2:
        lowest = rated_countries[:3]  # Top 3 funding currencies
        highest = rated_countries[-3:]  # Top 3 investing currencies

        for funder in lowest:
            for investor in highest:
                if funder["currency"] == investor["currency"]:
                    continue
                rate_diff = investor["interest_rate"] - funder["interest_rate"]
                if rate_diff > 1.0:  # Only show meaningful differentials
                    intensity = min(1.0, rate_diff / 5.0)
                    flows.append({
                        "from_currency": funder["currency"],
                        "from_country": funder["country"],
                        "from_lat": funder["lat"],
                        "from_lon": funder["lon"],
                        "to_currency": investor["currency"],
                        "to_country": investor["country"],
                        "to_lat": investor["lat"],
                        "to_lon": investor["lon"],
                        "rate_diff": round(rate_diff, 2),
                        "intensity": round(intensity, 2),
                        "label_kr": f"{funder['flag']}{funder['currency']}({funder['interest_rate']:.1f}%) → {investor['flag']}{investor['currency']}({investor['interest_rate']:.1f}%)",
                    })

    return flows


def _analyze_dxy_impact(dxy: float | None) -> dict:
    """Analyze Dollar Index impact on global markets."""
    d = dxy or 103

    if d > 108:
        level, level_kr = "Very Strong", "매우 강세"
        impact_kr = "달러 초강세 — 이머징 시장 자금유출 가속, 원자재 하락 압력, KR 외인 매도 압력"
        color = "#ef4444"
    elif d > 105:
        level, level_kr = "Strong", "강세"
        impact_kr = "달러 강세 — 이머징 통화 약세, 수출주 상대 유리, KR 환율 상승 부담"
        color = "#f97316"
    elif d > 100:
        level, level_kr = "Neutral", "보합"
        impact_kr = "달러 보합 — 글로벌 자금흐름 안정적"
        color = "#6b7280"
    elif d > 97:
        level, level_kr = "Weak", "약세"
        impact_kr = "달러 약세 — 이머징 자금유입, 원자재 상승, KR 외인 매수 기대"
        color = "#22c55e"
    else:
        level, level_kr = "Very Weak", "매우 약세"
        impact_kr = "달러 급락 — 글로벌 리스크온, 이머징/원자재 강세"
        color = "#16a34a"

    return {
        "value": round(d, 2),
        "level": level,
        "level_kr": level_kr,
        "impact_kr": impact_kr,
        "color": color,
    }


# ── Global Market Risk Factors ──

def compute_global_risk_factors(
    macro_data: dict | None,
    fx_data: dict[str, dict] | None,
    interest_rates: dict[str, float | None] | None,
    carry_risk: dict | None = None,
) -> list[dict]:
    """Compute major global risk factors affecting financial markets.

    Returns list of risk factors with severity, description, and market impact.
    """
    macro = macro_data or {}
    rates = interest_rates or {}
    factors = []

    # 1. Carry Trade Unwind Risk
    if carry_risk:
        overall = carry_risk.get("overall_risk", {})
        if overall.get("score", 0) >= 35:
            factors.append({
                "factor": "carry_trade_unwind",
                "name_kr": "캐리 트레이드 청산",
                "severity": overall["level"],
                "severity_kr": overall["level_kr"],
                "score": overall["score"],
                "description_kr": "저금리 통화(엔, 유로)로 조달한 자금의 고금리 자산 투자 청산 위험",
                "market_impact_kr": "글로벌 주식 하락, 이머징 자금유출, 원화 약세",
                "trigger_kr": "BOJ 금리인상, VIX 급등, 엔화 급격한 강세",
            })

    # 2. Dollar Strength
    dxy = macro.get("dxy_index")
    if dxy and dxy > 105:
        factors.append({
            "factor": "dollar_strength",
            "name_kr": "달러 강세",
            "severity": "HIGH" if dxy > 108 else "ELEVATED",
            "severity_kr": "위험" if dxy > 108 else "경계",
            "score": min(100, int((dxy - 100) * 10)),
            "description_kr": f"DXY {dxy:.1f} — 달러 강세로 이머징 시장 자금유출 압력",
            "market_impact_kr": "KR 외인 매도, 이머징 통화 약세, 원자재 하락",
            "trigger_kr": "Fed 금리인상 지속, 미국 경기 독주, 글로벌 불확실성",
        })

    # 3. Yield Curve Inversion
    spread = macro.get("us_yield_spread")
    if spread is not None and spread < 0:
        factors.append({
            "factor": "yield_curve_inversion",
            "name_kr": "수익률 곡선 역전",
            "severity": "HIGH" if spread < -0.5 else "ELEVATED",
            "severity_kr": "위험" if spread < -0.5 else "경계",
            "score": min(100, int(abs(spread) * 50)),
            "description_kr": f"10Y-2Y 스프레드 {spread:.2f}% — 경기침체 선행 지표",
            "market_impact_kr": "은행주 약세, 경기민감주 부진, 방어주/채권 선호",
            "trigger_kr": "Fed 긴축 지속, 장기 성장 전망 악화",
        })

    # 4. Oil Price Shock
    oil = macro.get("wti_crude")
    if oil and oil > 90:
        factors.append({
            "factor": "oil_price_shock",
            "name_kr": "유가 급등",
            "severity": "HIGH" if oil > 100 else "ELEVATED",
            "severity_kr": "위험" if oil > 100 else "경계",
            "score": min(100, int((oil - 70) * 2)),
            "description_kr": f"WTI ${oil:.1f} — 인플레이션 재점화 위험",
            "market_impact_kr": "소비자 지출 감소, 기업 비용 증가, 물가 상승",
            "trigger_kr": "OPEC 감산, 중동 지정학 리스크, 공급 차질",
        })

    # 5. VIX Extreme
    vix = macro.get("vix")
    if vix and vix > 25:
        factors.append({
            "factor": "volatility_spike",
            "name_kr": "변동성 급등",
            "severity": "HIGH" if vix > 30 else "ELEVATED",
            "severity_kr": "위험" if vix > 30 else "경계",
            "score": min(100, int((vix - 15) * 4)),
            "description_kr": f"VIX {vix:.1f} — 시장 공포 확대",
            "market_impact_kr": "주식 전반 하락, 안전자산 선호, 유동성 경색",
            "trigger_kr": "지정학 이벤트, 은행 위기, 통화정책 충격",
        })

    # 6. FX Volatility (KRW specific)
    usd_krw = macro.get("usd_krw")
    if usd_krw and usd_krw > 1380:
        factors.append({
            "factor": "krw_weakness",
            "name_kr": "원화 약세",
            "severity": "HIGH" if usd_krw > 1420 else "ELEVATED",
            "severity_kr": "위험" if usd_krw > 1420 else "경계",
            "score": min(100, int((usd_krw - 1300) * 0.5)),
            "description_kr": f"USD/KRW {usd_krw:.0f} — 외인 자금유출 압력",
            "market_impact_kr": "KR 외인 순매도, 수입물가 상승, 수출주 환율이익",
            "trigger_kr": "미중 갈등, 글로벌 리스크오프, 경상수지 악화",
        })

    # 7. Interest Rate Differential Widening
    us_rate = rates.get("USD")
    kr_rate = rates.get("KRW")
    if us_rate is not None and kr_rate is not None:
        diff = us_rate - kr_rate
        if diff > 1.5:
            factors.append({
                "factor": "rate_differential",
                "name_kr": "한미 금리차 확대",
                "severity": "ELEVATED" if diff > 2.0 else "WATCH",
                "severity_kr": "경계" if diff > 2.0 else "주의",
                "score": min(100, int(diff * 25)),
                "description_kr": f"미국 {us_rate:.1f}% vs 한국 {kr_rate:.1f}% (차이 {diff:.1f}%p)",
                "market_impact_kr": "자본 유출 압력, 원화 약세, KR 채권 매력 감소",
                "trigger_kr": "Fed 금리 동결/인상, 한국은행 금리 인하",
            })

    # Sort by score
    factors.sort(key=lambda x: x.get("score", 0), reverse=True)
    return factors
