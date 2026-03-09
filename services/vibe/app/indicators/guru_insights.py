"""Guru Insights — Famous investor perspectives simulated on current market data.

Each guru has:
1. Profile (style, philosophy, known holdings)
2. Market view function (macro → stance + commentary)
3. Stock pick function (signals → scored watchlist picks)
"""

from typing import Any

# ── Sector Classifications ──
_VALUE_SECTORS = {"금융", "보험", "소비재", "통신", "Consumer", "Finance", "Healthcare"}
_GROWTH_SECTORS = {"반도체", "인터넷", "배터리", "Tech", "Semiconductor"}
_INNOVATION_SECTORS = {"반도체", "배터리", "인터넷", "Tech", "Semiconductor", "Auto"}
_DEFENSIVE_SECTORS = {"금융", "통신", "유틸리티", "보험", "Healthcare", "Consumer"}
_CYCLICAL_SECTORS = {"자동차", "화학", "철강", "조선/중공업", "에너지/플랜트", "Energy", "Infrastructure"}

# ── 13F / Public Holdings ──
GURU_13F: dict[str, dict] = {
    "buffett": {
        "source": "Berkshire Hathaway 13F (SEC EDGAR)",
        "as_of": "2025-Q3",
        "total_value": "$310B",
        "holdings": [
            {"symbol": "AAPL", "name": "Apple", "weight": 28.0},
            {"symbol": "BAC", "name": "Bank of America", "weight": 11.5},
            {"symbol": "AXP", "name": "American Express", "weight": 9.0},
            {"symbol": "KO", "name": "Coca-Cola", "weight": 8.2},
            {"symbol": "CVX", "name": "Chevron", "weight": 5.8},
            {"symbol": "OXY", "name": "Occidental Petroleum", "weight": 4.5},
            {"symbol": "KHC", "name": "Kraft Heinz", "weight": 3.2},
            {"symbol": "MCK", "name": "McKesson", "weight": 2.5},
        ],
    },
    "dalio": {
        "source": "Bridgewater Associates 13F (SEC EDGAR)",
        "as_of": "2025-Q3",
        "total_value": "$16B",
        "holdings": [
            {"symbol": "SPY", "name": "S&P 500 ETF", "weight": 12.0},
            {"symbol": "GLD", "name": "Gold ETF", "weight": 9.5},
            {"symbol": "VWO", "name": "Emerging Markets ETF", "weight": 7.0},
            {"symbol": "GOOGL", "name": "Alphabet", "weight": 4.0},
            {"symbol": "PG", "name": "Procter & Gamble", "weight": 3.5},
            {"symbol": "JNJ", "name": "Johnson & Johnson", "weight": 3.0},
        ],
    },
    "soros": {
        "source": "Soros Fund Management 13F (SEC EDGAR)",
        "as_of": "2025-Q3",
        "total_value": "$5B",
        "holdings": [
            {"symbol": "SPLK", "name": "Splunk", "weight": 8.0},
            {"symbol": "RIVN", "name": "Rivian", "weight": 5.5},
            {"symbol": "MSFT", "name": "Microsoft", "weight": 4.0},
            {"symbol": "AMZN", "name": "Amazon", "weight": 3.5},
        ],
    },
    "wood": {
        "source": "ARK Invest Daily Holdings",
        "as_of": "2025-Q4",
        "total_value": "$12B",
        "holdings": [
            {"symbol": "TSLA", "name": "Tesla", "weight": 11.0},
            {"symbol": "COIN", "name": "Coinbase", "weight": 6.5},
            {"symbol": "ROKU", "name": "Roku", "weight": 5.0},
            {"symbol": "SQ", "name": "Block (Square)", "weight": 4.5},
            {"symbol": "PATH", "name": "UiPath", "weight": 3.5},
            {"symbol": "PLTR", "name": "Palantir", "weight": 3.0},
        ],
    },
    "nps": {
        "source": "국민연금 공시 (금융감독원 DART)",
        "as_of": "2025-Q3",
        "total_value": "1,100조원",
        "holdings_kr": [
            {"symbol": "005930", "name": "삼성전자", "weight": 8.5},
            {"symbol": "000660", "name": "SK하이닉스", "weight": 3.2},
            {"symbol": "373220", "name": "LG에너지솔루션", "weight": 2.1},
            {"symbol": "207940", "name": "삼성바이오로직스", "weight": 1.8},
            {"symbol": "005380", "name": "현대차", "weight": 1.5},
            {"symbol": "035420", "name": "NAVER", "weight": 1.2},
            {"symbol": "068270", "name": "셀트리온", "weight": 1.0},
        ],
        "holdings_us": [
            {"symbol": "AAPL", "name": "Apple", "weight": 2.5},
            {"symbol": "MSFT", "name": "Microsoft", "weight": 2.3},
            {"symbol": "AMZN", "name": "Amazon", "weight": 1.5},
            {"symbol": "NVDA", "name": "NVIDIA", "weight": 1.2},
            {"symbol": "GOOGL", "name": "Alphabet", "weight": 1.0},
        ],
    },
    "gpfg": {
        "source": "Norges Bank Investment Mgmt Annual Report",
        "as_of": "2025-H1",
        "total_value": "$1.7T",
        "holdings": [
            {"symbol": "AAPL", "name": "Apple", "weight": 2.8},
            {"symbol": "MSFT", "name": "Microsoft", "weight": 2.5},
            {"symbol": "AMZN", "name": "Amazon", "weight": 1.3},
            {"symbol": "GOOGL", "name": "Alphabet", "weight": 1.1},
            {"symbol": "005930", "name": "Samsung Electronics", "weight": 0.5},
        ],
    },
}

# ── Guru Profiles ──
GURUS: list[dict[str, Any]] = [
    {
        "id": "buffett",
        "name": "Warren Buffett",
        "name_kr": "워런 버핏",
        "org": "Berkshire Hathaway",
        "style_kr": "가치투자 · 경제적 해자",
        "avatar": "\U0001F9D3",
        "philosophy_kr": "좋은 기업을 합리적 가격에 사서 영원히 보유하라",
    },
    {
        "id": "dalio",
        "name": "Ray Dalio",
        "name_kr": "레이 달리오",
        "org": "Bridgewater Associates",
        "style_kr": "올웨더 · 매크로 사이클",
        "avatar": "\U0001F30A",
        "philosophy_kr": "경제는 기계처럼 작동한다. 모든 환경에 대비하라",
    },
    {
        "id": "lynch",
        "name": "Peter Lynch",
        "name_kr": "피터 린치",
        "org": "Fidelity Magellan Fund",
        "style_kr": "합리적 성장 · GARP",
        "avatar": "\U0001F4C8",
        "philosophy_kr": "아는 것에 투자하라. 성장하는 기업을 합리적 가격에",
    },
    {
        "id": "soros",
        "name": "George Soros",
        "name_kr": "조지 소로스",
        "org": "Soros Fund Management",
        "style_kr": "글로벌 매크로 · 반사성",
        "avatar": "\U0001F30D",
        "philosophy_kr": "시장은 항상 편향되어 있다. 반사성을 이용하라",
    },
    {
        "id": "marks",
        "name": "Howard Marks",
        "name_kr": "하워드 막스",
        "org": "Oaktree Capital",
        "style_kr": "사이클 · 리스크 관리",
        "avatar": "\U0001F4D6",
        "philosophy_kr": "가장 중요한 것은 사이클의 위치를 아는 것이다",
    },
    {
        "id": "wood",
        "name": "Cathie Wood",
        "name_kr": "캐시 우드",
        "org": "ARK Invest",
        "style_kr": "파괴적 혁신 · 5년 투자",
        "avatar": "\U0001F680",
        "philosophy_kr": "파괴적 혁신은 S-커브를 따라 기하급수적으로 성장한다",
    },
    {
        "id": "nps",
        "name": "National Pension Service",
        "name_kr": "국민연금",
        "org": "국민연금공단 (NPS)",
        "style_kr": "장기 분산투자 · 스튜어드십",
        "avatar": "\U0001F3DB",
        "philosophy_kr": "국민의 노후를 위한 장기·안정·분산 투자",
    },
    {
        "id": "gpfg",
        "name": "Norway GPFG",
        "name_kr": "노르웨이 국부펀드",
        "org": "Government Pension Fund Global",
        "style_kr": "글로벌 분산 · 책임투자",
        "avatar": "\U0001F1F3\U0001F1F4",
        "philosophy_kr": "전 세계 9,000개 기업에 분산, 세대를 초월한 투자",
    },
]


# ═══════════════════════════════════════════════
# Main analysis function
# ═══════════════════════════════════════════════

def analyze_all_gurus(
    macro: dict,
    signals: list[dict],
) -> list[dict]:
    """Run all guru analyses on current market data.

    Args:
        macro: Latest macro_indicators row (vix, fear_greed, us10y, etc.)
        signals: Latest signals enriched with 'sector' and 'name' fields.

    Returns:
        List of guru results with market_view, picks, and holdings.
    """
    results = []
    for guru in GURUS:
        gid = guru["id"]
        view_fn = _VIEW_FNS.get(gid, _default_view)
        pick_fn = _PICK_FNS.get(gid, _default_picks)

        view = view_fn(macro)
        picks = pick_fn(signals, macro)
        holdings = GURU_13F.get(gid, {})

        # Find overlaps with user's watchlist
        watchlist_symbols = {s["symbol"] for s in signals}
        all_h = holdings.get("holdings", []) + holdings.get("holdings_kr", []) + holdings.get("holdings_us", [])
        overlaps = [h["symbol"] for h in all_h if h["symbol"] in watchlist_symbols]

        results.append({
            **guru,
            "market_view": view,
            "picks": picks[:5],  # top 5 picks
            "portfolio": {
                "source": holdings.get("source", ""),
                "as_of": holdings.get("as_of", ""),
                "total_value": holdings.get("total_value", ""),
                "top_holdings": all_h[:8],
                "watchlist_overlaps": overlaps,
            },
        })
    return results


# ═══════════════════════════════════════════════
# Helper: classify market fear/greed level
# ═══════════════════════════════════════════════

def _market_mood(m: dict) -> str:
    """Classify: 'extreme_fear' | 'fear' | 'neutral' | 'greed' | 'extreme_greed'."""
    fg = m.get("fear_greed_index") or m.get("fear_greed") or 50
    if fg <= 15:
        return "extreme_fear"
    if fg <= 30:
        return "fear"
    if fg >= 80:
        return "extreme_greed"
    if fg >= 65:
        return "greed"
    return "neutral"


def _vix_level(m: dict) -> str:
    vix = m.get("vix") or 15
    if vix >= 35:
        return "panic"
    if vix >= 25:
        return "elevated"
    if vix <= 14:
        return "complacent"
    return "normal"


# ═══════════════════════════════════════════════
# Market View Functions (macro → stance + commentary)
# ═══════════════════════════════════════════════

def _buffett_view(m: dict) -> dict:
    mood = _market_mood(m)
    vix = _vix_level(m)
    fg = m.get("fear_greed_index") or m.get("fear_greed") or 50

    if mood in ("extreme_fear", "fear"):
        stance, stance_kr, conviction = "bullish", "매수 적극", 80
        summary = (
            f"'다른 사람들이 공포에 떨 때 탐욕을 부려라.' "
            f"현재 공포·탐욕 지수 {fg}은 시장이 과도한 공포 상태입니다. "
            f"경제적 해자가 넓은 우량 기업을 할인된 가격에 매수할 기회입니다."
        )
        points = [
            "시장 공포 = 가치투자자의 기회",
            "현금 보유량 충분하다면 분할 매수 적기",
            "단기 변동에 흔들리지 말고 기업 본질에 집중",
        ]
    elif mood in ("extreme_greed", "greed"):
        stance, stance_kr, conviction = "cautious", "관망 · 현금 확보", 30
        summary = (
            f"'다른 사람들이 탐욕스러울 때 공포를 느껴라.' "
            f"공포·탐욕 지수 {fg}은 시장이 과열 구간입니다. "
            f"현금 비중을 높이고, 진정한 가치 이하로 떨어지는 기업을 기다리세요."
        )
        points = [
            "시장 과열 시 현금이 왕",
            "새로운 매수보다 기존 포지션 점검",
            "밸류에이션 부담 높은 종목 비중 축소 고려",
        ]
    else:
        stance, stance_kr, conviction = "neutral", "선별적 매수", 55
        summary = (
            "시장은 합리적 수준입니다. 경제적 해자가 넓은 기업을 "
            "합리적 가격에 매수하는 본업에 집중하세요. "
            "과도한 트레이딩보다 장기 보유가 답입니다."
        )
        points = [
            "적정 가치 이하의 우량주 선별 매수",
            "배당수익률 높은 가치주에 주목",
            "10년 이상 보유할 기업만 매수",
        ]

    return {
        "stance": stance, "stance_kr": stance_kr,
        "conviction": conviction, "summary_kr": summary,
        "key_points_kr": points,
    }


def _dalio_view(m: dict) -> dict:
    vix = m.get("vix") or 15
    us10y = m.get("us_10y_yield") or m.get("us10y") or 4.0
    us02y = m.get("us_2y_yield") or m.get("us02y") or 4.0
    dxy = m.get("dxy_index") or m.get("dxy") or 100
    gold = m.get("gold_price") or m.get("gold") or 2000
    spread = us10y - us02y

    # Simple economic machine classification
    if spread < 0:
        phase, phase_kr = "late_cycle", "경기 후반 · 침체 전조"
    elif us10y > 4.5:
        phase, phase_kr = "tightening", "긴축 사이클"
    elif us10y < 2.5:
        phase, phase_kr = "easing", "완화 사이클"
    else:
        phase, phase_kr = "mid_cycle", "경기 중반"

    if vix > 28:
        stance, stance_kr, conviction = "risk_parity", "리스크 패리티 강화", 60
        summary = (
            f"변동성(VIX {vix:.0f})이 높아진 환경입니다. "
            f"올웨더 원칙에 따라 주식·채권·원자재·금을 균형 있게 배분하세요. "
            f"현재 {phase_kr} 국면에서 금({gold:.0f}$)과 장기채에 비중을 높이는 것이 유효합니다."
        )
    elif dxy > 106:
        stance, stance_kr, conviction = "cautious", "달러 강세 경계", 45
        summary = (
            f"달러 인덱스(DXY {dxy:.1f})가 강세 구간입니다. "
            f"신흥국 자산에 부정적이며, 원화 약세(USD/KRW {m.get('usd_krw', 0):.0f})에 유의하세요. "
            f"금과 달러 자산 비중을 유지하는 올웨더 전략이 유효합니다."
        )
    else:
        stance, stance_kr, conviction = "balanced", "균형 배분", 55
        summary = (
            f"경제 기계는 {phase_kr} 구간에서 작동 중입니다. "
            f"금리 스프레드 {spread:.2f}%를 모니터링하며, "
            f"주식 60% + 채권 25% + 원자재/금 15%의 전략적 배분을 유지하세요."
        )

    points = [
        f"금리 스프레드: {spread:.2f}% ({phase_kr})",
        f"올웨더 핵심: 분산으로 리스크 최소화",
        f"현재 환경에 맞는 자산: {'금·장기채' if vix > 25 else '주식·원자재 균형'}",
    ]

    return {
        "stance": stance, "stance_kr": stance_kr,
        "conviction": conviction, "summary_kr": summary,
        "key_points_kr": points,
    }


def _lynch_view(m: dict) -> dict:
    mood = _market_mood(m)
    fg = m.get("fear_greed_index") or m.get("fear_greed") or 50

    if mood in ("extreme_fear", "fear"):
        stance, stance_kr, conviction = "bullish", "성장주 저가 매수", 75
        summary = (
            "시장 공포는 성장주를 할인된 가격에 살 기회입니다. "
            "일상에서 좋은 제품/서비스를 만드는 기업을 찾으세요. "
            "PEG 비율 1 이하이면서 매출이 꾸준히 성장하는 기업이 최고의 투자입니다."
        )
    elif mood in ("extreme_greed", "greed"):
        stance, stance_kr, conviction = "selective", "성장 검증 후 매수", 40
        summary = (
            "시장이 들떠 있을 때일수록 펀더멘털 확인이 중요합니다. "
            "인기 테마에 편승하지 말고, 실제 매출과 이익이 성장하는지 확인하세요. "
            "10배 주식은 군중이 아닌 실적에서 나옵니다."
        )
    else:
        stance, stance_kr, conviction = "growth_hunting", "텐배거 발굴", 60
        summary = (
            "10배 주식(텐배거)을 찾으세요. 주변에서 인기 있는 제품, "
            "변화하는 산업의 선두주자를 관찰하세요. "
            "성장률 > PER인 종목이 핵심입니다."
        )

    return {
        "stance": stance, "stance_kr": stance_kr,
        "conviction": conviction, "summary_kr": summary,
        "key_points_kr": [
            "아는 기업에 투자 — 이해 못하면 사지 마라",
            "성장률 대비 저평가(PEG<1) 종목 발굴",
            "일상에서 좋은 제품 만드는 기업이 좋은 주식",
        ],
    }


def _soros_view(m: dict) -> dict:
    vix = m.get("vix") or 15
    usd_krw = m.get("usd_krw") or 1300
    dxy = m.get("dxy_index") or m.get("dxy") or 100
    fg = m.get("fear_greed_index") or m.get("fear_greed") or 50

    # Reflexivity: trends feed on themselves
    if vix > 30 and fg < 20:
        stance, stance_kr, conviction = "contrarian_long", "반전 매수 준비", 70
        summary = (
            f"반사성이 극대화 구간입니다. 공포가 더 큰 공포를 낳는 악순환이나, "
            f"VIX {vix:.0f}, F&G {fg}은 반전 직전의 극단을 시사합니다. "
            f"정책 개입 또는 매크로 반전 시 급반등이 가능합니다. "
            f"포지션 사이즈를 줄이되, 반전 트리거에 대비하세요."
        )
    elif dxy > 107:
        stance, stance_kr, conviction = "fx_play", "달러 롱 · 원화 쇼트", 65
        summary = (
            f"달러 강세 추세(DXY {dxy:.1f})가 자기 강화 중입니다. "
            f"원/달러 {usd_krw:.0f}원에서 신흥국 자본 유출 압력이 있습니다. "
            f"달러 표시 자산 비중 확대가 유효합니다."
        )
    elif fg > 75:
        stance, stance_kr, conviction = "short_ready", "과열 경계 · 숏 준비", 55
        summary = (
            "시장의 낙관이 자기 강화 중이나, 반사성은 양방향입니다. "
            "과열 구간에서의 급반전에 대비하여 헤지 포지션을 구축하세요."
        )
    else:
        stance, stance_kr, conviction = "trend_follow", "추세 추종", 50
        summary = (
            "뚜렷한 반사성 트리거가 없는 구간입니다. "
            "매크로 추세를 따르되, 정책 변화와 FX 흐름에 주목하세요."
        )

    return {
        "stance": stance, "stance_kr": stance_kr,
        "conviction": conviction, "summary_kr": summary,
        "key_points_kr": [
            f"USD/KRW {usd_krw:.0f} — {'원화 약세 주의' if usd_krw > 1400 else '안정 구간'}",
            f"VIX {vix:.0f} — {'극단적 공포, 반전 임박 가능' if vix > 30 else '정상 범위'}",
            "반사성: 추세가 자기 강화하다 급반전하는 패턴 주시",
        ],
    }


def _marks_view(m: dict) -> dict:
    vix = m.get("vix") or 15
    fg = m.get("fear_greed_index") or m.get("fear_greed") or 50
    mood = _market_mood(m)

    # Where are we in the cycle?
    if mood == "extreme_fear":
        cycle_pos, cycle_kr = "bottom", "사이클 바닥 근처"
        stance, stance_kr, conviction = "aggressive_buy", "적극 매수", 85
        summary = (
            f"'가장 안전한 투자는 모두가 위험하다고 판단할 때 하는 것입니다.' "
            f"공포·탐욕 {fg}, VIX {vix:.0f}는 사이클의 바닥에 가깝습니다. "
            f"우량 자산을 할인된 가격에 매수하는 최적의 시기입니다. "
            f"다만 진정한 바닥 확인 전까지 분할 매수가 현명합니다."
        )
    elif mood == "fear":
        cycle_pos, cycle_kr = "lower_half", "사이클 하반기"
        stance, stance_kr, conviction = "accumulate", "분할 매수", 70
        summary = (
            "사이클 하반기에 진입했습니다. 리스크 프리미엄이 높아져 있어 "
            "보상 대비 리스크가 유리한 구간입니다. "
            "인내심을 갖고 우량 자산을 축적하세요."
        )
    elif mood == "extreme_greed":
        cycle_pos, cycle_kr = "top", "사이클 정점 근처"
        stance, stance_kr, conviction = "defensive", "방어 · 현금 확보", 25
        summary = (
            "'모든 것이 좋을 때, 가장 위험한 시기입니다.' "
            f"공포·탐욕 {fg}은 사이클 정점을 시사합니다. "
            "공격적 포지션을 줄이고, 방어적 자산과 현금 비중을 높이세요."
        )
    else:
        cycle_pos, cycle_kr = "mid_cycle", "사이클 중반"
        stance, stance_kr, conviction = "selective", "선별적 접근", 50
        summary = (
            "사이클 중반부입니다. 극단적 기회도, 극단적 위험도 아닌 구간입니다. "
            "리스크 대비 보상이 유리한 자산을 선별적으로 접근하되, "
            "과도한 레버리지는 피하세요."
        )

    return {
        "stance": stance, "stance_kr": stance_kr,
        "conviction": conviction, "summary_kr": summary,
        "cycle_position": cycle_pos,
        "cycle_position_kr": cycle_kr,
        "key_points_kr": [
            f"사이클 위치: {cycle_kr}",
            "리스크 = 영구적 자본 손실 가능성",
            "'2차 사고(second-level thinking)'로 군중과 반대로",
        ],
    }


def _wood_view(m: dict) -> dict:
    mood = _market_mood(m)
    vix = m.get("vix") or 15

    if mood in ("extreme_fear", "fear"):
        stance, stance_kr, conviction = "buy_innovation", "혁신주 적극 매수", 85
        summary = (
            "시장 공포는 혁신 기업의 5년 비전을 바꾸지 않습니다. "
            "AI, 로보틱스, 에너지 혁신, 디지털 자산 분야의 선도 기업은 "
            "오히려 지금이 가장 좋은 진입 기회입니다. "
            "단기 변동성은 장기 투자자에게 선물입니다."
        )
    elif mood in ("extreme_greed", "greed"):
        stance, stance_kr, conviction = "hold_conviction", "확신 보유 유지", 65
        summary = (
            "혁신 기업의 장기 성장 궤도는 시장 사이클과 무관합니다. "
            "S-커브 성장 중인 기업은 보유를 유지하되, "
            "신규 진입은 밸류에이션 부담을 고려해 선별적으로 하세요."
        )
    else:
        stance, stance_kr, conviction = "accumulate_disruptors", "혁신 기업 축적", 70
        summary = (
            "파괴적 혁신은 S-커브를 따라 기하급수적으로 성장합니다. "
            "AI, 자율주행, 에너지 저장, 바이오테크 분야에서 "
            "5년 후 시장을 지배할 기업을 지금 축적하세요."
        )

    return {
        "stance": stance, "stance_kr": stance_kr,
        "conviction": conviction, "summary_kr": summary,
        "key_points_kr": [
            "파괴적 혁신 = 5년 투자 관점",
            "AI, 로보틱스, 에너지 전환, 디지털 자산",
            "단기 하락 = 장기 투자자의 매수 기회",
        ],
    }


def _nps_view(m: dict) -> dict:
    mood = _market_mood(m)
    usd_krw = m.get("usd_krw") or 1300

    if mood in ("extreme_fear", "fear"):
        stance, stance_kr, conviction = "rebalance_buy", "리밸런싱 매수", 65
        summary = (
            "국민연금은 장기 투자 관점에서 시장 하락을 리밸런싱 기회로 활용합니다. "
            "목표 자산배분 비중 대비 주식 비중이 하락했다면 매수로 복원하는 전략입니다. "
            "국내 대형 우량주와 글로벌 분산 투자를 병행합니다."
        )
    elif mood in ("extreme_greed", "greed"):
        stance, stance_kr, conviction = "rebalance_trim", "리밸런싱 축소", 40
        summary = (
            "주식 비중이 목표 대비 과대해졌습니다. "
            "이익 실현을 통해 채권·대체투자 비중을 복원하는 리밸런싱이 필요합니다. "
            "장기적으로 안정적 수익을 위해 규율 있는 배분을 유지합니다."
        )
    else:
        stance, stance_kr, conviction = "strategic_hold", "전략적 배분 유지", 55
        summary = (
            "현재 목표 자산배분(국내주식 17%, 해외주식 30%, 채권 35%, 대체 18%)에 "
            "근접한 수준입니다. 장기 수익률 목표(5.5% 실질수익률)를 위해 "
            "규율 있는 분산 투자를 유지합니다."
        )

    return {
        "stance": stance, "stance_kr": stance_kr,
        "conviction": conviction, "summary_kr": summary,
        "key_points_kr": [
            f"해외 자산: 원화 약세(USD/KRW {usd_krw:.0f}) {'환헤지 비중 조절' if usd_krw > 1400 else '현행 유지'}",
            "스튜어드십 코드: ESG 고려한 책임 투자",
            "연금 특성상 10~30년 장기 투자 관점 필수",
        ],
    }


def _gpfg_view(m: dict) -> dict:
    mood = _market_mood(m)
    gold = m.get("gold_price") or m.get("gold") or 2000
    wti = m.get("wti_crude") or m.get("wti_oil") or 70

    if mood in ("extreme_fear", "fear"):
        stance, stance_kr, conviction = "systematic_buy", "체계적 매수", 60
        summary = (
            "GPFG는 전 세계 9,000개 이상 기업에 분산 투자합니다. "
            "시장 하락 시 벤치마크 대비 비중이 줄어든 섹터를 체계적으로 매수합니다. "
            "패닉 매도와 반대로 움직이는 것이 장기 수익의 원천입니다."
        )
    else:
        stance, stance_kr, conviction = "index_plus", "인덱스 플러스", 55
        summary = (
            "글로벌 주식 70%, 채권 25%, 부동산/인프라 5%의 전략적 배분을 유지합니다. "
            f"원유({wti:.0f}$)·금({gold:.0f}$) 등 원자재는 노르웨이 경제 헤지 관점에서 모니터링합니다."
        )

    return {
        "stance": stance, "stance_kr": stance_kr,
        "conviction": conviction, "summary_kr": summary,
        "key_points_kr": [
            "전 세계 70개국 9,000+ 기업 분산 투자",
            "주식 70% / 채권 25% / 리얼에셋 5%",
            "세대를 초월한 장기 투자 (100년+)",
        ],
    }


def _default_view(m: dict) -> dict:
    return {
        "stance": "neutral", "stance_kr": "중립",
        "conviction": 50, "summary_kr": "분석 준비 중",
        "key_points_kr": [],
    }


# ═══════════════════════════════════════════════
# Stock Pick Functions (signals → scored picks)
# ═══════════════════════════════════════════════

def _score_and_sort(signals: list[dict], score_fn) -> list[dict]:
    """Score each signal, filter positives, sort desc."""
    scored = []
    for s in signals:
        score, reason = score_fn(s)
        if score > 0:
            scored.append({
                "symbol": s["symbol"],
                "name": s.get("name", s["symbol"]),
                "market": s.get("market", ""),
                "fit_score": min(100, round(score)),
                "reason_kr": reason,
                "signal": s.get("final_signal", ""),
                "rsi": s.get("rsi_value"),
            })
    scored.sort(key=lambda x: x["fit_score"], reverse=True)
    return scored


def _buffett_picks(signals: list[dict], m: dict) -> list[dict]:
    def score(s):
        sc = 0
        reasons = []
        sector = s.get("sector", "")
        rsi = s.get("rsi_value") or 50

        if sector in _VALUE_SECTORS:
            sc += 20
            reasons.append("가치 섹터")
        if rsi < 35:
            sc += 25
            reasons.append(f"과매도(RSI {rsi:.0f})")
        elif rsi < 45:
            sc += 15
            reasons.append(f"저평가 구간(RSI {rsi:.0f})")
        fund = s.get("fundamental_score") or 0
        if fund > 0:
            sc += 20
            reasons.append("펀더멘털 양호")
        if s.get("final_signal") == "BUY":
            sc += 10
            reasons.append("매수 시그널")
        # Buffett avoids high-volatility tech
        if sector in ("인터넷", "배터리"):
            sc -= 10

        return sc, " · ".join(reasons) if reasons else "해당 없음"

    return _score_and_sort(signals, score)


def _dalio_picks(signals: list[dict], m: dict) -> list[dict]:
    def score(s):
        sc = 0
        reasons = []
        sector = s.get("sector", "")
        rsi = s.get("rsi_value") or 50

        # Dalio likes balanced, diversified
        if 30 < rsi < 70:
            sc += 15
            reasons.append("균형 RSI 구간")
        if sector in _DEFENSIVE_SECTORS:
            sc += 15
            reasons.append("방어 섹터")
        if s.get("final_signal") in ("BUY", "HOLD"):
            sc += 10
            reasons.append("안정적 시그널")
        # ETFs for diversification
        if sector == "ETF":
            sc += 20
            reasons.append("분산 투자 수단")
        fund = s.get("fundamental_score") or 0
        if fund > 0:
            sc += 10

        return sc, " · ".join(reasons) if reasons else "해당 없음"

    return _score_and_sort(signals, score)


def _lynch_picks(signals: list[dict], m: dict) -> list[dict]:
    def score(s):
        sc = 0
        reasons = []
        sector = s.get("sector", "")
        rsi = s.get("rsi_value") or 50

        if sector in _GROWTH_SECTORS:
            sc += 20
            reasons.append("성장 섹터")
        if s.get("final_signal") == "BUY":
            sc += 15
            reasons.append("매수 시그널")
        tech = s.get("technical_score") or 0
        if tech > 20:
            sc += 15
            reasons.append(f"기술적 강세({tech:.0f})")
        if 35 < rsi < 65:
            sc += 10
            reasons.append("합리적 RSI 구간")
        elif rsi > 70:
            sc -= 15  # too expensive

        return sc, " · ".join(reasons) if reasons else "해당 없음"

    return _score_and_sort(signals, score)


def _soros_picks(signals: list[dict], m: dict) -> list[dict]:
    def score(s):
        sc = 0
        reasons = []
        raw = s.get("raw_score") or 0

        # Soros follows momentum and macro
        if raw > 15:
            sc += 25
            reasons.append(f"강한 모멘텀(score {raw:.0f})")
        elif raw > 5:
            sc += 15
            reasons.append("양호한 모멘텀")
        macro = s.get("macro_score") or 0
        if macro > 10:
            sc += 15
            reasons.append("매크로 순풍")
        if s.get("final_signal") == "BUY":
            sc += 15
            reasons.append("매수 시그널")
        # FX play: if USD/KRW is high, prefer US stocks
        usd_krw = m.get("usd_krw") or 1300
        if usd_krw > 1400 and s.get("market") == "US":
            sc += 10
            reasons.append("달러 강세 수혜(US)")

        return sc, " · ".join(reasons) if reasons else "해당 없음"

    return _score_and_sort(signals, score)


def _marks_picks(signals: list[dict], m: dict) -> list[dict]:
    mood = _market_mood(m)

    def score(s):
        sc = 0
        reasons = []
        rsi = s.get("rsi_value") or 50

        # Marks is contrarian: buy beaten-down quality in fear
        if mood in ("extreme_fear", "fear"):
            if rsi < 30:
                sc += 30
                reasons.append(f"극도의 과매도(RSI {rsi:.0f}) — 역발상 매수")
            elif rsi < 40:
                sc += 20
                reasons.append(f"과매도(RSI {rsi:.0f})")
            if s.get("final_signal") == "SELL":
                sc += 15
                reasons.append("군중의 매도 = 역발상 기회")
        else:
            # In neutral/greed: prefers defensive quality
            if s.get("sector", "") in _DEFENSIVE_SECTORS:
                sc += 15
                reasons.append("방어적 우량주")
            if rsi < 45:
                sc += 10
                reasons.append("저평가 구간")

        fund = s.get("fundamental_score") or 0
        if fund > 0:
            sc += 15
            reasons.append("펀더멘털 양호")

        return sc, " · ".join(reasons) if reasons else "해당 없음"

    return _score_and_sort(signals, score)


def _wood_picks(signals: list[dict], m: dict) -> list[dict]:
    def score(s):
        sc = 0
        reasons = []
        sector = s.get("sector", "")

        if sector in _INNOVATION_SECTORS:
            sc += 25
            reasons.append("혁신 섹터")
        if s.get("final_signal") == "BUY":
            sc += 15
            reasons.append("매수 시그널")
        tech = s.get("technical_score") or 0
        if tech > 10:
            sc += 10
            reasons.append("기술적 양호")
        # Wood specifically likes EV, batteries, AI
        if sector in ("배터리", "반도체", "Auto", "Semiconductor"):
            sc += 10
            reasons.append("핵심 혁신 테마")

        return sc, " · ".join(reasons) if reasons else "해당 없음"

    return _score_and_sort(signals, score)


def _nps_picks(signals: list[dict], m: dict) -> list[dict]:
    def score(s):
        sc = 0
        reasons = []
        sector = s.get("sector", "")
        rsi = s.get("rsi_value") or 50

        # NPS prefers blue-chip, diversified
        if sector in _DEFENSIVE_SECTORS or sector in ("반도체", "자동차"):
            sc += 15
            reasons.append("대형 우량 섹터")
        if s.get("final_signal") in ("BUY", "HOLD"):
            sc += 10
            reasons.append("안정적 시그널")
        if 30 < rsi < 65:
            sc += 10
            reasons.append("적정 RSI")
        fund = s.get("fundamental_score") or 0
        if fund > 0:
            sc += 15
            reasons.append("펀더멘털 양호")
        # Prefer KR large caps (NPS mandate)
        if s.get("market") == "KR":
            sc += 10
            reasons.append("국내 핵심 종목")

        return sc, " · ".join(reasons) if reasons else "해당 없음"

    return _score_and_sort(signals, score)


def _gpfg_picks(signals: list[dict], m: dict) -> list[dict]:
    def score(s):
        sc = 0
        reasons = []

        # GPFG: broad global diversification
        if s.get("market") == "US":
            sc += 10
            reasons.append("글로벌 종목")
        if s.get("final_signal") in ("BUY", "HOLD"):
            sc += 10
            reasons.append("안정적 시그널")
        fund = s.get("fundamental_score") or 0
        if fund > 0:
            sc += 15
            reasons.append("펀더멘털 양호")
        rsi = s.get("rsi_value") or 50
        if 35 < rsi < 65:
            sc += 10
            reasons.append("균형 구간")

        return sc, " · ".join(reasons) if reasons else "해당 없음"

    return _score_and_sort(signals, score)


def _default_picks(signals: list[dict], m: dict) -> list[dict]:
    return []


# ── Dispatch Tables ──
_VIEW_FNS = {
    "buffett": _buffett_view, "dalio": _dalio_view, "lynch": _lynch_view,
    "soros": _soros_view, "marks": _marks_view, "wood": _wood_view,
    "nps": _nps_view, "gpfg": _gpfg_view,
}
_PICK_FNS = {
    "buffett": _buffett_picks, "dalio": _dalio_picks, "lynch": _lynch_picks,
    "soros": _soros_picks, "marks": _marks_picks, "wood": _wood_picks,
    "nps": _nps_picks, "gpfg": _gpfg_picks,
}


# ═══════════════════════════════════════════════
# LLM-Enhanced Analysis (optional)
# ═══════════════════════════════════════════════

def build_guru_llm_prompt(guru_id: str, macro: dict, signals_summary: str) -> str:
    """Build LLM prompt for deep guru analysis."""
    guru = next((g for g in GURUS if g["id"] == guru_id), None)
    if not guru:
        return ""

    macro_summary = (
        f"VIX: {macro.get('vix', 'N/A')}, "
        f"Fear&Greed: {macro.get('fear_greed_index') or macro.get('fear_greed', 'N/A')}, "
        f"US10Y: {macro.get('us_10y_yield') or macro.get('us10y', 'N/A')}%, "
        f"USD/KRW: {macro.get('usd_krw', 'N/A')}, "
        f"DXY: {macro.get('dxy_index') or macro.get('dxy', 'N/A')}, "
        f"Gold: ${macro.get('gold_price') or macro.get('gold', 'N/A')}, "
        f"WTI: ${macro.get('wti_crude') or macro.get('wti_oil', 'N/A')}, "
        f"Put/Call: {macro.get('put_call_ratio', 'N/A')}"
    )

    return f"""당신은 {guru['name']}({guru['name_kr']})입니다.
투자 스타일: {guru['style_kr']}
투자 철학: {guru['philosophy_kr']}
소속: {guru['org']}

아래 매크로 데이터와 시그널 요약을 바탕으로, {guru['name_kr']}의 관점에서 한국어로 시장 분석을 해주세요.

## 현재 매크로 데이터
{macro_summary}

## 시그널 요약
{signals_summary}

## 요청사항
1. 현재 시장에 대한 {guru['name_kr']}의 관점 (3-4문장)
2. 주목할 종목 3-5개와 이유
3. 리스크 요인 2-3개
4. 핵심 조언 1줄

{guru['name_kr']}의 어투와 투자 철학을 반영하여 작성해주세요. 간결하게 답변하세요."""
