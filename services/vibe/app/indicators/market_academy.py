"""Market Academy Engine — Educational content tied to live market data.

Goal: 경제적 안목 키우기 — Build investment literacy through current market context.
Each concept is explained with real-time data, making abstract ideas concrete.
"""

from datetime import date


# ── Concept Definitions ──────────────────────────────────────────────────

CONCEPTS = {
    "vix": {
        "id": "vix",
        "name_kr": "VIX (공포 지수)",
        "name_en": "VIX — Volatility Index",
        "category": "sentiment",
        "icon": "😨",
        "difficulty": 1,
        "definition_kr": (
            "CBOE에서 발표하는 S&P 500 옵션의 향후 30일 내재변동성 지수입니다. "
            "시장 참여자들이 느끼는 '두려움'을 수치화한 것으로, 숫자가 높을수록 시장 불안이 큽니다."
        ),
        "ranges": [
            {"range": "0-12", "label": "극도의 안정", "meaning_kr": "시장이 너무 안정적. 오히려 자만(complacency) 주의."},
            {"range": "12-20", "label": "정상", "meaning_kr": "일반적 시장 상태. 특별한 공포나 탐욕 없음."},
            {"range": "20-30", "label": "경계", "meaning_kr": "불확실성 증가. 변동성 확대 가능성."},
            {"range": "30-40", "label": "공포", "meaning_kr": "시장 공포. 급격한 변동 주의. 역발상 매수 기회 검토."},
            {"range": "40+", "label": "극단적 공포", "meaning_kr": "극단적 패닉. 역사적으로 중장기 저점 근처인 경우 많음."},
        ],
        "key_insight_kr": "워런 버핏의 명언: '남들이 공포에 떨 때 탐욕스러워져라'. VIX 30+ 구간에서 분할 매수는 역사적으로 높은 수익률을 보여왔습니다.",
        "related_concepts": ["fear_greed", "put_call_ratio"],
    },
    "yield_curve": {
        "id": "yield_curve",
        "name_kr": "수익률 곡선 (Yield Curve)",
        "name_en": "Yield Curve — Interest Rate Term Structure",
        "category": "macro",
        "icon": "📈",
        "difficulty": 2,
        "definition_kr": (
            "국채의 만기별 금리를 연결한 곡선입니다. 보통 장기 금리가 단기 금리보다 높은 '정상(normal)' 형태이나, "
            "이것이 뒤집히면(장단기 역전) 경기침체의 강력한 선행지표로 알려져 있습니다."
        ),
        "ranges": [
            {"range": "2.0%+", "label": "가파른 정상", "meaning_kr": "경기 회복/확장기. 은행 수익성 좋음. 성장주 유리."},
            {"range": "0.5-2.0%", "label": "완만한 정상", "meaning_kr": "일반적 경제 상태. 안정적 투자 환경."},
            {"range": "0-0.5%", "label": "평탄화", "meaning_kr": "경기 둔화 신호. 방어적 포지션 고려."},
            {"range": "마이너스", "label": "역전 (Inverted)", "meaning_kr": "경기침체 경고! 과거 역전 후 6-18개월 내 침체 발생 빈도 높음."},
        ],
        "key_insight_kr": "수익률 곡선 역전은 1970년 이후 모든 미국 경기침체를 선행했습니다. 단, 역전 후 침체까지 평균 12-18개월이 걸리므로 즉각적 패닉은 금물입니다.",
        "related_concepts": ["fed_rate", "bond_market"],
    },
    "fear_greed": {
        "id": "fear_greed",
        "name_kr": "공포 & 탐욕 지수",
        "name_en": "Fear & Greed Index",
        "category": "sentiment",
        "icon": "🎭",
        "difficulty": 1,
        "definition_kr": (
            "CNN이 발표하는 7가지 지표(주가 모멘텀, 주가 강도, 주가 범위, Put/Call 비율, "
            "시장 변동성, 안전자산 수요, 정크본드 수요)를 종합한 투자 심리 지수입니다. 0(극단적 공포)~100(극단적 탐욕)."
        ),
        "ranges": [
            {"range": "0-20", "label": "극단적 공포", "meaning_kr": "투자자들이 극도로 두려워하는 상태. 역발상 매수 기회."},
            {"range": "21-40", "label": "공포", "meaning_kr": "시장 심리 위축. 좋은 종목을 싸게 살 기회."},
            {"range": "41-60", "label": "중립", "meaning_kr": "탐욕과 공포가 균형. 정상적 시장 상태."},
            {"range": "61-80", "label": "탐욕", "meaning_kr": "과열 주의. 신규 매수보다는 보유 종목 관리."},
            {"range": "81-100", "label": "극단적 탐욕", "meaning_kr": "버블 위험! 차익 실현 고려."},
        ],
        "key_insight_kr": "공포 지수 20 이하에서 매수한 투자자의 1년 후 평균 수익률은 +15-25%였습니다. 반대로 탐욕 80 이상에서 매수하면 평균 -5-10% 손실.",
        "related_concepts": ["vix", "put_call_ratio", "contrarian"],
    },
    "rsi": {
        "id": "rsi",
        "name_kr": "RSI (상대강도지수)",
        "name_en": "RSI — Relative Strength Index",
        "category": "technical",
        "icon": "📊",
        "difficulty": 1,
        "definition_kr": (
            "14일간의 상승폭과 하락폭의 비율로 계산되는 모멘텀 지표입니다. "
            "0-100 사이의 값을 가지며, 70 이상이면 과매수(overbought), 30 이하면 과매도(oversold)로 판단합니다."
        ),
        "ranges": [
            {"range": "0-30", "label": "과매도", "meaning_kr": "과도하게 팔렸음. 기술적 반등 가능성 높음. 매수 시점 검토."},
            {"range": "30-50", "label": "약세", "meaning_kr": "하락 추세이나 과매도는 아님. 관망 또는 소량 분할 매수."},
            {"range": "50-70", "label": "정상~강세", "meaning_kr": "건강한 상승 추세. 기존 포지션 유지."},
            {"range": "70-100", "label": "과매수", "meaning_kr": "과도하게 올랐음. 조정 가능성. 추가 매수 자제, 익절 고려."},
        ],
        "key_insight_kr": "RSI 단독으로 매매 결정하면 위험합니다. 강한 상승 추세에서 RSI 70+가 오래 지속될 수 있습니다. 다른 지표(MACD, 이격도)와 함께 봐야 합니다.",
        "related_concepts": ["macd", "disparity", "bollinger"],
    },
    "macd": {
        "id": "macd",
        "name_kr": "MACD (이동평균 수렴확산)",
        "name_en": "MACD — Moving Average Convergence Divergence",
        "category": "technical",
        "icon": "〰️",
        "difficulty": 2,
        "definition_kr": (
            "12일 이동평균과 26일 이동평균의 차이(MACD선)와 그것의 9일 이동평균(시그널선)으로 구성됩니다. "
            "MACD선이 시그널선을 상향 돌파하면 골든크로스(매수), 하향 돌파하면 데드크로스(매도) 신호입니다."
        ),
        "ranges": [
            {"range": "히스토그램 양수(증가)", "label": "강세 모멘텀", "meaning_kr": "상승 추세 가속. 매수 포지션 유지/진입."},
            {"range": "히스토그램 양수(감소)", "label": "모멘텀 둔화", "meaning_kr": "상승세 약화. 이익 확보 준비."},
            {"range": "히스토그램 음수(감소)", "label": "약세 모멘텀", "meaning_kr": "하락 추세 가속. 매도 또는 관망."},
            {"range": "히스토그램 음수(증가)", "label": "바닥 형성", "meaning_kr": "하락세 약화. 반등 준비. 분할 매수 검토."},
        ],
        "key_insight_kr": "MACD 다이버전스(주가는 신고가인데 MACD는 하락)는 강력한 추세 전환 신호입니다. 이런 괴리가 발생하면 포지션 점검이 필요합니다.",
        "related_concepts": ["rsi", "moving_average"],
    },
    "disparity": {
        "id": "disparity",
        "name_kr": "이격도 (Disparity)",
        "name_en": "Disparity Index — Price vs Moving Average",
        "category": "technical",
        "icon": "↔️",
        "difficulty": 1,
        "definition_kr": (
            "현재 주가가 이동평균선에서 얼마나 벗어나 있는지 보여주는 지표입니다. "
            "(현재가/20일 이동평균) × 100으로 계산합니다. 100이면 이평선 위에 정확히 위치."
        ),
        "ranges": [
            {"range": "95% 이하", "label": "과매도", "meaning_kr": "이동평균 대비 크게 하락. 기술적 반등 가능성."},
            {"range": "95-100%", "label": "약세", "meaning_kr": "이동평균 아래. 하락 추세."},
            {"range": "100-105%", "label": "정상", "meaning_kr": "이동평균 근처. 건강한 상태."},
            {"range": "105% 이상", "label": "과열", "meaning_kr": "이동평균 대비 과도한 상승. VIBE에서 매수 차단(Hard Limit)."},
        ],
        "key_insight_kr": "VIBE 시스템에서 이격도 105% 이상이면 매수 신호가 자동 차단(HOLD로 전환)됩니다. 이는 과열 구간에서의 추격 매수를 방지하기 위한 안전장치입니다.",
        "related_concepts": ["rsi", "bollinger"],
    },
    "position_sizing": {
        "id": "position_sizing",
        "name_kr": "포지션 사이징 (자금 관리)",
        "name_en": "Position Sizing — Money Management",
        "category": "risk_management",
        "icon": "💰",
        "difficulty": 2,
        "definition_kr": (
            "한 종목에 투자금의 몇 %를 투자할지 결정하는 기법입니다. "
            "아무리 좋은 종목이라도 한 종목에 전 재산을 넣으면 큰 리스크입니다. "
            "일반적으로 단일 종목 10% 이내, 단일 섹터 30% 이내를 권장합니다."
        ),
        "ranges": [
            {"range": "3-5%", "label": "탐색적 진입", "meaning_kr": "확신이 낮은 경우. 손실 한정, 학습 목적."},
            {"range": "5-8%", "label": "기본 진입", "meaning_kr": "보통 수준의 확신. 가장 일반적인 포지션."},
            {"range": "8-10%", "label": "확신 진입", "meaning_kr": "높은 확신 + 강한 시그널. 최대 허용 비중."},
            {"range": "10%+", "label": "과도", "meaning_kr": "⚠️ 단일 종목 집중 위험! VIBE 기준 초과."},
        ],
        "key_insight_kr": "켈리 공식(Kelly Criterion): 최적 투자 비율 = (승률×수익배율 - 패배확률) / 수익배율. VIBE는 안전하게 하프 켈리(50%)를 사용합니다.",
        "related_concepts": ["stop_loss", "risk_reward"],
    },
    "stop_loss": {
        "id": "stop_loss",
        "name_kr": "손절매 (Stop-Loss)",
        "name_en": "Stop-Loss — Risk Limit",
        "category": "risk_management",
        "icon": "🛑",
        "difficulty": 1,
        "definition_kr": (
            "미리 정한 손실 한도에 도달하면 기계적으로 매도하는 전략입니다. "
            "'손실을 제한하고 수익은 달리게 한다'는 투자의 가장 기본적인 원칙입니다."
        ),
        "ranges": [
            {"range": "-3%", "label": "타이트", "meaning_kr": "단기 트레이딩. 작은 손실에도 빠르게 대응."},
            {"range": "-5~-7%", "label": "기본", "meaning_kr": "가장 일반적. VIBE 기본 설정은 -7%."},
            {"range": "-10%", "label": "느슨", "meaning_kr": "장기 투자자. 더 큰 변동성을 감내."},
            {"range": "-15%+", "label": "위험", "meaning_kr": "⚠️ 손실이 과도. 회복에 +17.6% 필요."},
        ],
        "key_insight_kr": "손실과 회복의 비대칭성: -10% 손실 회복에 +11.1% 필요, -20% 회복에 +25%, -50% 회복에 +100%가 필요합니다. 손절이 중요한 이유입니다.",
        "related_concepts": ["position_sizing", "risk_reward"],
    },
    "risk_reward": {
        "id": "risk_reward",
        "name_kr": "리스크-리워드 비율 (R:R)",
        "name_en": "Risk-Reward Ratio",
        "category": "risk_management",
        "icon": "⚖️",
        "difficulty": 1,
        "definition_kr": (
            "투자에서 감수하는 위험(손절까지 거리) 대비 기대 수익(목표가까지 거리)의 비율입니다. "
            "R:R = 2:1이면 1만원 리스크로 2만원 수익을 기대. 최소 1.5:1 이상을 목표로 합니다."
        ),
        "ranges": [
            {"range": "3:1+", "label": "우수", "meaning_kr": "매우 좋은 투자 기회. 승률 33%만 되어도 수익."},
            {"range": "2:1", "label": "양호", "meaning_kr": "기본적으로 좋은 기회. 승률 50%면 큰 수익."},
            {"range": "1.5:1", "label": "최소 기준", "meaning_kr": "투자 가치 있는 최소 비율."},
            {"range": "1:1 이하", "label": "부적합", "meaning_kr": "⚠️ 리스크 대비 보상이 부족. 진입 재고."},
        ],
        "key_insight_kr": "R:R 2:1 + 승률 50%이면 장기적으로 반드시 수익입니다. 10번 중 5번 맞추면: 5×2만원(수익) - 5×1만원(손실) = +5만원. 이것이 확률적 우위입니다.",
        "related_concepts": ["stop_loss", "position_sizing"],
    },
    "dollar_cost_averaging": {
        "id": "dollar_cost_averaging",
        "name_kr": "분할 매수 (적립식 투자)",
        "name_en": "Dollar Cost Averaging (DCA)",
        "category": "strategy",
        "icon": "📅",
        "difficulty": 1,
        "definition_kr": (
            "일정 금액을 정기적으로 투자하는 전략입니다. 주가가 높을 때 적게, 낮을 때 많이 사게 되어 "
            "평균 매수가가 자연스럽게 낮아집니다. 시장 타이밍을 잡지 못하는 개인투자자에게 최적의 전략입니다."
        ),
        "ranges": [
            {"range": "주간", "label": "적극적 DCA", "meaning_kr": "매주 투자. 변동성 높은 시기에 효과적."},
            {"range": "월간", "label": "기본 DCA", "meaning_kr": "월 1-2회. 가장 일반적."},
            {"range": "공포 구간 집중", "label": "전술적 DCA", "meaning_kr": "VIX 30+, F&G 20 이하에서 집중 분할 매수."},
        ],
        "key_insight_kr": "VIBE의 '역발상 분할 매수' 전략: 공포 극점(Peak Fear)에서 총 투자금의 20-30%를 3-5회에 나눠 매수. 한 번에 올인하지 않는 것이 핵심.",
        "related_concepts": ["contrarian", "position_sizing"],
    },
    "sector_rotation": {
        "id": "sector_rotation",
        "name_kr": "섹터 로테이션",
        "name_en": "Sector Rotation — Business Cycle Investment",
        "category": "strategy",
        "icon": "🔄",
        "difficulty": 3,
        "definition_kr": (
            "경기 사이클에 따라 유망한 섹터가 바뀝니다. "
            "경기 회복기에는 금융/산업재, 확장기에는 기술/소비재, 둔화기에는 에너지/필수소비재, "
            "침체기에는 유틸리티/헬스케어가 강세를 보이는 경향이 있습니다."
        ),
        "ranges": [
            {"range": "금융장세(Spring)", "label": "성장주 유리", "meaning_kr": "금리 하락 + 유동성 확대 → 기술/성장주 주도"},
            {"range": "실적장세(Summer)", "label": "경기민감주", "meaning_kr": "실적 개선 → 산업재/소재/금융 강세"},
            {"range": "역금융장세(Autumn)", "label": "방어주 전환", "meaning_kr": "금리 고점 → 유틸리티/헬스케어/필수소비재"},
            {"range": "역실적장세(Winter)", "label": "현금 유리", "meaning_kr": "실적 악화 → 현금/채권/금"},
        ],
        "key_insight_kr": "VIBE의 '시장 계절(Market Season)' 지표는 우라가미 구니오의 4시즌 모델을 기반으로 현재 어떤 장세인지 자동 판별합니다. 투자 시계(Investment Clock)와 함께 참고하세요.",
        "related_concepts": ["market_season", "investment_clock"],
    },
    "contrarian": {
        "id": "contrarian",
        "name_kr": "역발상 투자 (Contrarian)",
        "name_en": "Contrarian Investing",
        "category": "strategy",
        "icon": "🔄",
        "difficulty": 2,
        "definition_kr": (
            "다수의 투자자와 반대 방향으로 투자하는 전략입니다. "
            "시장이 극도의 공포에 빠졌을 때 매수하고, 극도의 탐욕에 빠졌을 때 매도합니다. "
            "워런 버핏, 하워드 막스 등 세계적 투자자들의 핵심 철학입니다."
        ),
        "ranges": [
            {"range": "F&G 0-20", "label": "극단적 공포", "meaning_kr": "역발상 매수 최적 구간"},
            {"range": "F&G 20-35", "label": "공포", "meaning_kr": "분할 매수 시작 구간"},
            {"range": "F&G 65-80", "label": "탐욕", "meaning_kr": "신규 매수 자제, 이익 확보 시작"},
            {"range": "F&G 80-100", "label": "극단적 탐욕", "meaning_kr": "역발상 매도/현금 확보 구간"},
        ],
        "key_insight_kr": "VIBE의 Fear Gauge가 'Peak Fear'를 감지하면 역발상 매수 신호입니다. 단, 한 번에 올인하지 말고 반드시 분할 매수하세요. 바닥은 아무도 모릅니다.",
        "related_concepts": ["fear_greed", "dollar_cost_averaging", "vix"],
    },
}


# ── Today's Lesson Generator ─────────────────────────────────────────────

def generate_todays_lesson(macro: dict, sentiment: dict | None = None) -> dict:
    """Select the most relevant concept to teach today based on current market."""
    vix = macro.get("vix")
    fg = None
    if sentiment:
        fg = sentiment.get("fear_greed_index")
    spread = macro.get("us_yield_spread")
    wti = macro.get("wti_crude")

    # Priority: teach what's most relevant NOW
    lesson_id = "position_sizing"  # default
    current_value = None
    current_status = ""
    why_now_kr = ""

    if vix and vix > 30:
        lesson_id = "vix"
        current_value = round(vix, 1)
        current_status = "🔴 공포 구간"
        why_now_kr = f"현재 VIX {vix:.1f}로 공포 구간입니다. 이런 시기에 VIX의 의미를 정확히 이해하는 것이 중요합니다."
    elif fg is not None and fg <= 25:
        lesson_id = "fear_greed"
        current_value = fg
        current_status = "🔴 극단적 공포"
        why_now_kr = f"F&G 지수가 {fg}으로 극단적 공포 상태입니다. 역사적으로 이런 구간은 매수 기회였습니다."
    elif fg is not None and fg >= 75:
        lesson_id = "contrarian"
        current_value = fg
        current_status = "🔴 극단적 탐욕"
        why_now_kr = f"F&G 지수가 {fg}으로 탐욕 구간입니다. 역발상 투자 원칙을 복습할 때입니다."
    elif spread is not None and spread < 0:
        lesson_id = "yield_curve"
        current_value = round(spread, 2)
        current_status = "⚠️ 역전"
        why_now_kr = f"수익률 곡선이 역전({spread:.2f}%)되었습니다. 경기침체 선행지표를 이해하세요."
    elif vix and vix > 20:
        lesson_id = "vix"
        current_value = round(vix, 1)
        current_status = "🟡 경계"
        why_now_kr = f"VIX {vix:.1f}로 변동성이 높아지고 있습니다. 공포 지수의 의미를 점검하세요."
    elif wti and wti > 85:
        lesson_id = "sector_rotation"
        current_value = round(wti, 1)
        current_status = "고유가"
        why_now_kr = f"WTI ${wti:.0f}로 고유가입니다. 유가에 따른 섹터 로테이션을 이해하세요."

    concept = CONCEPTS[lesson_id]
    return {
        "concept": concept,
        "current_value": current_value,
        "current_status": current_status,
        "why_now_kr": why_now_kr,
        "date": date.today().isoformat(),
    }


# ── Historical Pattern Matching ──────────────────────────────────────────

HISTORICAL_PATTERNS = [
    {
        "id": "covid_crash",
        "name_kr": "2020 코로나 폭락",
        "period": "2020.02 ~ 2020.03",
        "trigger_kr": "글로벌 팬데믹",
        "vix_peak": 82.7,
        "fg_low": 2,
        "sp500_drop": -34,
        "recovery_months": 5,
        "lesson_kr": "극단적 공포(VIX 80+)에서 분할 매수한 투자자는 5개월 만에 원금 회복, 1년 후 +70% 수익.",
        "conditions": {"vix_min": 35, "fg_max": 15},
    },
    {
        "id": "rate_hike_2022",
        "name_kr": "2022 금리 인상 하락장",
        "period": "2022.01 ~ 2022.10",
        "trigger_kr": "연준 급격한 금리 인상 (0%→4.5%)",
        "vix_peak": 36.5,
        "fg_low": 6,
        "sp500_drop": -25,
        "recovery_months": 14,
        "lesson_kr": "금리 인상기에는 성장주가 큰 타격. 가치주/배당주가 상대적 강세. 금리 피크를 기다리는 인내가 핵심.",
        "conditions": {"vix_min": 25, "yield_spread_max": 0},
    },
    {
        "id": "gfc_2008",
        "name_kr": "2008 글로벌 금융위기",
        "period": "2008.09 ~ 2009.03",
        "trigger_kr": "서브프라임 모기지 + 리먼 파산",
        "vix_peak": 89.5,
        "fg_low": 0,
        "sp500_drop": -57,
        "recovery_months": 48,
        "lesson_kr": "극단적 위기에서도 분산 투자와 분할 매수로 대응. S&P 500은 5년 후 전고점 돌파. 포기하지 않는 것이 핵심.",
        "conditions": {"vix_min": 40, "fg_max": 10},
    },
    {
        "id": "tech_bubble_2000",
        "name_kr": "2000 닷컴 버블 붕괴",
        "period": "2000.03 ~ 2002.10",
        "trigger_kr": "인터넷 기업 과대평가 붕괴",
        "vix_peak": 45.7,
        "fg_low": 5,
        "sp500_drop": -49,
        "recovery_months": 84,
        "lesson_kr": "극단적 탐욕(F&G 95+) 구간에서의 투기적 매수는 10년 이상 회복에 걸릴 수 있음. 밸류에이션을 무시하지 마세요.",
        "conditions": {"fg_min": 80},
    },
]


def find_matching_patterns(macro: dict, sentiment: dict | None = None) -> list[dict]:
    """Find historical patterns similar to current conditions."""
    vix = macro.get("vix") or 0
    fg = (sentiment or {}).get("fear_greed_index")
    spread = macro.get("us_yield_spread")

    matches = []
    for pattern in HISTORICAL_PATTERNS:
        cond = pattern["conditions"]
        match_score = 0
        match_reasons = []

        if "vix_min" in cond and vix >= cond["vix_min"]:
            match_score += 40
            match_reasons.append(f"VIX {vix:.0f} ≥ {cond['vix_min']}")
        if "fg_max" in cond and fg is not None and fg <= cond["fg_max"]:
            match_score += 40
            match_reasons.append(f"F&G {fg} ≤ {cond['fg_max']}")
        if "fg_min" in cond and fg is not None and fg >= cond["fg_min"]:
            match_score += 40
            match_reasons.append(f"F&G {fg} ≥ {cond['fg_min']}")
        if "yield_spread_max" in cond and spread is not None and spread <= cond["yield_spread_max"]:
            match_score += 30
            match_reasons.append(f"Spread {spread:.2f}% ≤ {cond['yield_spread_max']}")

        if match_score >= 30:
            matches.append({
                **pattern,
                "match_score": match_score,
                "match_reasons": match_reasons,
            })

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches


# ── Concept Catalog ──────────────────────────────────────────────────────

def get_all_concepts() -> list[dict]:
    """Return all concepts grouped by category."""
    categories = {}
    for concept in CONCEPTS.values():
        cat = concept["category"]
        if cat not in categories:
            categories[cat] = {
                "category": cat,
                "category_kr": {
                    "sentiment": "📊 시장 심리",
                    "macro": "🌐 거시경제",
                    "technical": "📈 기술적 분석",
                    "risk_management": "🛡️ 리스크 관리",
                    "strategy": "🎯 투자 전략",
                }.get(cat, cat),
                "concepts": [],
            }
        categories[cat]["concepts"].append({
            "id": concept["id"],
            "name_kr": concept["name_kr"],
            "icon": concept["icon"],
            "difficulty": concept["difficulty"],
        })

    return sorted(categories.values(), key=lambda c: c["category"])


def get_concept_detail(concept_id: str, macro: dict = None) -> dict | None:
    """Get detailed concept with current market value annotation."""
    concept = CONCEPTS.get(concept_id)
    if not concept:
        return None

    result = {**concept}

    # Annotate with current value if available
    if macro:
        current = _get_current_value_for_concept(concept_id, macro)
        if current is not None:
            result["current_value"] = current["value"]
            result["current_label"] = current["label"]
            result["current_zone"] = current["zone"]

    return result


def _get_current_value_for_concept(concept_id: str, macro: dict) -> dict | None:
    """Map concept to current market value."""
    mappings = {
        "vix": ("vix", lambda v: (
            "극도의 안정" if v < 12 else "정상" if v < 20 else "경계" if v < 30 else "공포" if v < 40 else "극단적 공포"
        )),
        "yield_curve": ("us_yield_spread", lambda v: (
            "가파른 정상" if v > 2 else "완만한 정상" if v > 0.5 else "평탄화" if v >= 0 else "역전"
        )),
    }

    if concept_id not in mappings:
        return None

    key, label_fn = mappings[concept_id]
    val = macro.get(key)
    if val is None:
        return None

    label = label_fn(val)
    # Determine zone for styling
    zones = {"극도의 안정": "neutral", "정상": "safe", "경계": "warning", "공포": "danger",
             "극단적 공포": "danger", "가파른 정상": "safe", "완만한 정상": "safe",
             "평탄화": "warning", "역전": "danger"}

    return {
        "value": round(val, 2),
        "label": label,
        "zone": zones.get(label, "neutral"),
    }
