"""Initial watchlist seed data for VIBE."""

from app.database import repositories as repo

SEED_DATA = [
    # ── KR 대형주 (KOSPI Top 20) ──
    {"symbol": "005930", "name": "삼성전자", "market": "KR", "asset_type": "stock"},
    {"symbol": "000660", "name": "SK하이닉스", "market": "KR", "asset_type": "stock"},
    {"symbol": "373220", "name": "LG에너지솔루션", "market": "KR", "asset_type": "stock"},
    {"symbol": "207940", "name": "삼성바이오로직스", "market": "KR", "asset_type": "stock"},
    {"symbol": "005380", "name": "현대차", "market": "KR", "asset_type": "stock"},
    {"symbol": "006400", "name": "삼성SDI", "market": "KR", "asset_type": "stock"},
    {"symbol": "035420", "name": "NAVER", "market": "KR", "asset_type": "stock"},
    {"symbol": "000270", "name": "기아", "market": "KR", "asset_type": "stock"},
    {"symbol": "051910", "name": "LG화학", "market": "KR", "asset_type": "stock"},
    {"symbol": "035720", "name": "카카오", "market": "KR", "asset_type": "stock"},
    {"symbol": "068270", "name": "셀트리온", "market": "KR", "asset_type": "stock"},
    {"symbol": "003670", "name": "포스코홀딩스", "market": "KR", "asset_type": "stock"},
    {"symbol": "105560", "name": "KB금융", "market": "KR", "asset_type": "stock"},
    {"symbol": "055550", "name": "신한지주", "market": "KR", "asset_type": "stock"},
    {"symbol": "017670", "name": "SK텔레콤", "market": "KR", "asset_type": "stock"},
    {"symbol": "034730", "name": "SK", "market": "KR", "asset_type": "stock"},
    {"symbol": "015760", "name": "한국전력", "market": "KR", "asset_type": "stock"},
    {"symbol": "032830", "name": "삼성생명", "market": "KR", "asset_type": "stock"},
    {"symbol": "066570", "name": "LG전자", "market": "KR", "asset_type": "stock"},
    {"symbol": "033780", "name": "KT&G", "market": "KR", "asset_type": "stock"},
    # ── KR ETF ──
    {"symbol": "069500", "name": "KODEX 200", "market": "KR", "asset_type": "etf"},
    {"symbol": "229200", "name": "KODEX 코스닥150", "market": "KR", "asset_type": "etf"},
    {"symbol": "364690", "name": "KODEX 200선물인버스2X", "market": "KR", "asset_type": "etf"},
    {"symbol": "371460", "name": "TIGER 차이나전기차SOLACTIVE", "market": "KR", "asset_type": "etf"},
    # ── US 대형주 (S&P Top 20) ──
    {"symbol": "AAPL", "name": "Apple Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "market": "US", "asset_type": "stock"},
    {"symbol": "NVDA", "name": "NVIDIA Corp.", "market": "US", "asset_type": "stock"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway B", "market": "US", "asset_type": "stock"},
    {"symbol": "UNH", "name": "UnitedHealth Group", "market": "US", "asset_type": "stock"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "market": "US", "asset_type": "stock"},
    {"symbol": "V", "name": "Visa Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "XOM", "name": "Exxon Mobil Corp.", "market": "US", "asset_type": "stock"},
    {"symbol": "JPM", "name": "JPMorgan Chase", "market": "US", "asset_type": "stock"},
    {"symbol": "PG", "name": "Procter & Gamble", "market": "US", "asset_type": "stock"},
    {"symbol": "MA", "name": "Mastercard Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "HD", "name": "Home Depot Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "AVGO", "name": "Broadcom Inc.", "market": "US", "asset_type": "stock"},
    {"symbol": "CVX", "name": "Chevron Corp.", "market": "US", "asset_type": "stock"},
    {"symbol": "MRK", "name": "Merck & Co.", "market": "US", "asset_type": "stock"},
    {"symbol": "ABBV", "name": "AbbVie Inc.", "market": "US", "asset_type": "stock"},
    # ── US ETF/Index ──
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "market": "US", "asset_type": "etf"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "market": "US", "asset_type": "etf"},
    {"symbol": "DIA", "name": "SPDR Dow Jones ETF", "market": "US", "asset_type": "etf"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "market": "US", "asset_type": "etf"},
    {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "market": "US", "asset_type": "etf"},
    {"symbol": "SOXL", "name": "Direxion Daily Semiconductor Bull 3X", "market": "US", "asset_type": "etf"},
    {"symbol": "SOXS", "name": "Direxion Daily Semiconductor Bear 3X", "market": "US", "asset_type": "etf"},
]


async def seed_watchlist() -> int:
    """Seed watchlist with initial data. Returns number of new items added."""
    return await repo.add_watchlist_bulk(SEED_DATA)
