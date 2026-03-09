"""
Geopolitical Event Dashboard Router

Provides structured geopolitical event analysis with market impact data.
Currently focused on the 2026 Iran-US conflict.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(prefix="/geopolitical", tags=["geopolitical"])
logger = logging.getLogger("vibe.geopolitical")


# ── Iran-US Conflict Timeline & Analysis (2026.02.28 ~) ──

IRAN_US_TIMELINE = [
    {"date": "2026-02-06", "event": "미국-이란 간접 협상 (오만 무스카트)", "impact": "neutral", "detail": "협상 '좋은 출발' 평가, 시장 낙관론"},
    {"date": "2026-02-25", "event": "이란 외무장관: '역사적 합의 임박' 발언", "impact": "positive", "detail": "시장 리스크 프리미엄 축소"},
    {"date": "2026-02-28", "event": "미국-이스라엘 이란 공습 개시 (Epic Fury 작전)", "impact": "severe_negative", "detail": "12시간 내 900회 공습, 이란 최고지도자 사망. 유가 급등, 글로벌 증시 급락"},
    {"date": "2026-03-02", "event": "이란 반격: 두바이·아부다비·도하·쿠웨이트 타격", "impact": "severe_negative", "detail": "유조선 2척 피격, IRGC 호르무즈 해협 봉쇄 위협. 쿠웨이트 미대사관 폐쇄"},
    {"date": "2026-03-06", "event": "미국/이스라엘 이란 석유 시설 공습", "impact": "negative", "detail": "석유 저장고·정유 시설 최초 공격. 누적 사망 1,332명+"},
    {"date": "2026-03-08", "event": "이란: 호르무즈 해협 개방 유지, 미/이 선박 표적 경고", "impact": "negative", "detail": "해상 교역 불확실성 지속. 트럼프 대통령 '4주 내 종전' 전망"},
]

MARKET_IMPACT = {
    "oil": {
        "title": "원유 시장",
        "before": "~$70/bbl (Brent)",
        "after": "$110+/bbl (Brent)",
        "change_pct": "+57%",
        "detail": "호르무즈 해협(글로벌 석유 20% 통과) 봉쇄 위협. $100~$200 전망 분기",
    },
    "gold": {
        "title": "금",
        "before": "~$4,800/oz",
        "after": "$5,400+/oz",
        "change_pct": "+12.5%",
        "detail": "안전자산 수요 급증. 사상 최고가 경신",
    },
    "usd": {
        "title": "미국 달러 (DXY)",
        "change_pct": "+0.95%",
        "detail": "안전자산 수요로 달러 강세. 5주 최고치",
    },
    "equities": {
        "title": "글로벌 증시",
        "sp500": "+0.04% (장중 600pt 변동)",
        "nikkei": "-3.06%",
        "dax": "-3.44%",
        "kospi": "역대 최대 일일 하락",
        "euro_stoxx": "-5.5%",
        "detail": "미국 증시 상대적 견조, 아시아·유럽 급락",
    },
}

SECTOR_IMPACT = [
    {"sector": "에너지 (석유/가스)", "direction": "up", "magnitude": "high", "tickers": ["XLE", "XOM", "CVX"], "reason": "유가 급등 직접 수혜"},
    {"sector": "방산/항공우주", "direction": "up", "magnitude": "high", "tickers": ["LMT", "NOC", "RTX", "ITA"], "reason": "군수 지출 급증, 방산 ETF(ITA) YTD +14%"},
    {"sector": "금/귀금속", "direction": "up", "magnitude": "high", "tickers": ["GLD", "GDX", "NEM"], "reason": "안전자산 수요, 금 $5,400+ 신고가"},
    {"sector": "해운/탱커", "direction": "up", "magnitude": "very_high", "tickers": ["BWET", "FRO", "STNG"], "reason": "해운 물류 우회 프리미엄, BWET YTD +200%"},
    {"sector": "유틸리티", "direction": "up", "magnitude": "low", "tickers": ["XLU"], "reason": "방어적 포지셔닝"},
    {"sector": "반도체", "direction": "down", "magnitude": "high", "tickers": ["SOXL", "SOXX", "005930.KS", "000660.KS"], "reason": "헬륨/원자재 공급 차질, 에너지 비용 상승, 리스크 오프"},
    {"sector": "항공/관광", "direction": "down", "magnitude": "high", "tickers": ["JETS", "UAL", "DAL"], "reason": "걸프만 항공편 중단, 여행 수요 급감"},
    {"sector": "이머징 마켓 (아시아)", "direction": "down", "magnitude": "high", "tickers": ["EWY", "EWT", "EEM"], "reason": "에너지 수입 의존도 높은 한국/대만 직격. EWY -13%/주"},
    {"sector": "테크/성장주", "direction": "down", "magnitude": "medium", "tickers": ["QQQ", "ARKK"], "reason": "리스크 오프 로테이션, 금리 인하 기대 소멸"},
    {"sector": "중동 인프라", "direction": "down", "magnitude": "very_high", "tickers": [], "reason": "UAE/바레인 아마존 데이터센터 드론 피격, AI 인프라 차질"},
]

SEMICONDUCTOR_RISKS = [
    {"risk": "헬륨 공급 차단", "severity": "critical", "detail": "반도체 제조 필수 가스. 중동 주요 공급원이며 대체재 없음"},
    {"risk": "원자재 14종+ 공급 위협", "severity": "high", "detail": "한국 반도체 산업이 중동에서 조달하는 14개 이상 원자재 차질 가능"},
    {"risk": "해상 운송 우회", "severity": "high", "detail": "호르무즈 해협 우회 시 아프리카 경유 → 리드타임 2~3주 증가"},
    {"risk": "에너지 비용 급등", "severity": "high", "detail": "팹(fab) 가동은 에너지 집약적. 유가 $110+ → 제조 원가 직접 상승"},
    {"risk": "군수용 칩 수요 전환", "severity": "medium", "detail": "방위산업 향 반도체 우선 배정 → 민수용 공급 축소 가능"},
    {"risk": "데이터센터 건설 지연", "severity": "medium", "detail": "UAE/바레인 데이터센터 피해 → AI 인프라 투자 일시 위축"},
]

HISTORICAL_PRECEDENTS = [
    {
        "event": "1990 걸프전 (이라크 쿠웨이트 침공)",
        "market_decline": "-15.9%",
        "recovery": "공습 개시 후 6개월 내 +15%",
        "key_factor": "유가 급등 후 안정화",
    },
    {
        "event": "2003 이라크 침공",
        "market_decline": "미미한 하락",
        "recovery": "침공 1개월 후 DJIA +8.4%, 연말 S&P +26.7%",
        "key_factor": "전쟁 불확실성 해소 후 급반등",
    },
    {
        "event": "1973 석유 금수 조치",
        "market_decline": "심각한 하락",
        "recovery": "장기 회복 (에너지 공급 문제가 핵심)",
        "key_factor": "에너지 공급 차질 장기화",
    },
    {
        "event": "역사적 평균 (20개 주요 군사 개입)",
        "market_decline": "S&P -6% (평균)",
        "recovery": "바닥: 평균 19거래일, 회복: 평균 42거래일",
        "key_factor": "경기 확장기 충격 → 12개월 +9.8%, 침체기 → -9.8%",
    },
]

KEY_VARIABLES = [
    {"variable": "호르무즈 해협 상태", "current": "개방 (미/이 선박 표적 경고)", "bullish": "완전 개방 복귀", "bearish": "전면 봉쇄"},
    {"variable": "유가 경로", "current": "$110+/bbl", "bullish": "$80 이하 복귀", "bearish": "$150+ 지속"},
    {"variable": "분쟁 기간", "current": "10일차 (2026.03.08 기준)", "bullish": "4주 내 종전", "bearish": "수개월 장기화"},
    {"variable": "연준 대응", "current": "금리 동결 예상", "bullish": "인플레 안정 시 인하 재개", "bearish": "유가발 인플레 → 금리 인상"},
    {"variable": "확전 범위", "current": "이란+레바논(헤즈볼라)", "bullish": "현 수준 제한", "bearish": "걸프국 참전, 전면전"},
]

HEDGING_STRATEGIES = [
    {"strategy": "원유 롱 (USO, UCO)", "rationale": "호르무즈 봉쇄 시 추가 상승 여력. 포트폴리오 에너지 헤지"},
    {"strategy": "금 롱 (GLD, GDX)", "rationale": "지정학 리스크 지속 시 안전자산 수요. 인플레 헤지 겸용"},
    {"strategy": "방산 ETF (ITA, XAR)", "rationale": "군수 지출 확대 직접 수혜. 분쟁 장기화 시 추가 상승"},
    {"strategy": "반도체 숏헤지 (SOXS)", "rationale": "SOXL 보유 시 SOXS 소량으로 방향성 리스크 헤지"},
    {"strategy": "VIX 콜 (UVXY)", "rationale": "변동성 급등 시 포트폴리오 보호"},
    {"strategy": "현금 비중 확대", "rationale": "불확실성 극대화 구간 — 기회 자금 확보"},
]


@router.get("/iran-us")
async def iran_us_dashboard():
    """Iran-US conflict dashboard with timeline, market impact, and strategy."""
    from app.database.connection import get_db

    db = await get_db()

    # Fetch live data for affected tickers
    affected_symbols = ["SOXL", "SPY", "QQQ"]
    live_data = {}
    for sym in affected_symbols:
        cursor = await db.execute(
            """SELECT trade_date, close FROM price_history
               WHERE symbol=? AND market='US'
               ORDER BY trade_date DESC LIMIT 30""",
            (sym,),
        )
        rows = await cursor.fetchall()
        if rows:
            prices = [{"date": r[0], "close": r[1]} for r in rows]
            prices.reverse()
            live_data[sym] = prices

    # Latest macro for VIX, oil context
    cursor = await db.execute(
        """SELECT indicator_date, vix, wti_crude, gold_price, usd_krw, dxy_index
           FROM macro_indicators
           ORDER BY indicator_date DESC LIMIT 1"""
    )
    macro_row = await cursor.fetchone()
    macro_snapshot = None
    if macro_row:
        macro_snapshot = {
            "date": macro_row[0],
            "vix": macro_row[1],
            "wti_crude": macro_row[2],
            "gold": macro_row[3],
            "usd_krw": macro_row[4],
            "dxy": macro_row[5],
        }

    return {
        "event_name": "2026 이란-미국 분쟁",
        "status": "진행 중",
        "start_date": "2026-02-28",
        "days_elapsed": (datetime.now(timezone.utc).date() - datetime(2026, 2, 28).date()).days,
        "timeline": IRAN_US_TIMELINE,
        "market_impact": MARKET_IMPACT,
        "sector_impact": SECTOR_IMPACT,
        "semiconductor_risks": SEMICONDUCTOR_RISKS,
        "historical_precedents": HISTORICAL_PRECEDENTS,
        "key_variables": KEY_VARIABLES,
        "hedging_strategies": HEDGING_STRATEGIES,
        "live_data": live_data,
        "macro_snapshot": macro_snapshot,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "soxl_specific": {
            "impact_summary": "3x 레버리지로 반도체 섹터 손실 3배 증폭. 헬륨/원자재/에너지 트리플 역풍",
            "key_level": "47~48$ 지지선 — 이탈 시 37~41$ 영역 열림",
            "recovery_condition": "분쟁 4주 내 종결 + 유가 $80 복귀 시 역사적 패턴상 급반등 가능",
        },
    }
