"""Sector classification and exposure calculations."""

# Hardcoded sector mappings for the 49 seed symbols
SECTOR_MAP: dict[str, str] = {
    # ── KR Stocks ──
    "005930": "반도체",       # 삼성전자
    "000660": "반도체",       # SK하이닉스
    "373220": "배터리",       # LG에너지솔루션
    "207940": "바이오",       # 삼성바이오로직스
    "005380": "자동차",       # 현대차
    "006400": "배터리",       # 삼성SDI
    "035420": "인터넷",       # NAVER
    "000270": "자동차",       # 기아
    "051910": "화학",         # LG화학
    "035720": "인터넷",       # 카카오
    "068270": "바이오",       # 셀트리온
    "003670": "철강",         # 포스코홀딩스
    "105560": "금융",         # KB금융
    "055550": "금융",         # 신한지주
    "017670": "통신",         # SK텔레콤
    "034730": "지주",         # SK
    "015760": "유틸리티",     # 한국전력
    "032830": "보험",         # 삼성생명
    "066570": "전자",         # LG전자
    "033780": "소비재",       # KT&G
    # KR ETFs
    "069500": "ETF", "229200": "ETF", "364690": "ETF", "371460": "ETF",
    # ── US Stocks ──
    "AAPL": "Tech",      "MSFT": "Tech",
    "NVDA": "Semiconductor", "AMZN": "Consumer",
    "GOOGL": "Tech",     "META": "Tech",
    "TSLA": "Auto",      "BRK-B": "Finance",
    "UNH": "Healthcare", "JNJ": "Healthcare",
    "V": "Finance",      "XOM": "Energy",
    "JPM": "Finance",    "PG": "Consumer",
    "MA": "Finance",     "HD": "Consumer",
    "AVGO": "Semiconductor", "CVX": "Energy",
    "MRK": "Healthcare", "ABBV": "Healthcare",
    # US ETFs
    "SPY": "ETF", "QQQ": "ETF", "DIA": "ETF", "IWM": "ETF", "VTI": "ETF",
    "TLT": "ETF", "SOXL": "ETF",
    # Additional US Stocks
    "PWR": "Infrastructure", "CEG": "Energy",
    # Additional KR Stocks (portfolio)
    "329180": "조선/중공업",   # HD현대중공업
    "009540": "조선/중공업",   # HD한국조선해양
    "042660": "조선/중공업",   # 한화오션
    "012450": "방산/항공",     # 한화에어로스페이스
    "267260": "전기/전력장비", # HD현대일렉트릭
    "034020": "에너지/플랜트", # 두산에너빌리티
}


def get_sector(symbol: str) -> str:
    """Get sector for a symbol. Returns 'Unknown' if not mapped."""
    return SECTOR_MAP.get(symbol, "Unknown")


def compute_sector_exposure(positions: dict[str, float]) -> dict[str, float]:
    """Compute sector exposure from current positions.

    Args:
        positions: {symbol: position_pct} mapping

    Returns:
        {sector: total_pct} mapping
    """
    exposure: dict[str, float] = {}
    for symbol, pct in positions.items():
        sector = get_sector(symbol)
        exposure[sector] = exposure.get(sector, 0) + pct
    return exposure


def check_sector_limit(
    symbol: str,
    proposed_pct: float,
    current_positions: dict[str, float],
    max_sector_pct: float,
) -> tuple[float, bool]:
    """Check if adding a position would exceed sector limit.

    Returns:
        (adjusted_pct, was_constrained)
    """
    sector = get_sector(symbol)
    current_exposure = compute_sector_exposure(current_positions)
    current_sector = current_exposure.get(sector, 0)

    remaining = max_sector_pct - current_sector
    if remaining <= 0:
        return 0.0, True

    if proposed_pct > remaining:
        return remaining, True

    return proposed_pct, False
