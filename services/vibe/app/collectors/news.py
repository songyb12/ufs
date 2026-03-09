"""News data collectors - RSS-based news fetching for KR and US markets.

Sources:
- KR: Naver Finance news RSS
- US: Finviz news, Google News RSS
- Global: Google News RSS for market keywords

No API keys required. All sources are free RSS/HTML scraping.
"""

import asyncio
import logging
import re
import defusedxml.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger("vibe.collectors.news")

# Korean stock name mapping for search
KR_SYMBOL_NAMES = {}  # Populated from DB at runtime

# Symbol format validation
_SYMBOL_RE = re.compile(r'^[A-Z0-9.\-]{1,10}$', re.IGNORECASE)

# Shared httpx client — reused across all news fetches within a session
_http_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    """Get or create a shared httpx.AsyncClient instance (race-condition safe)."""
    global _http_client
    async with _client_lock:
        if _http_client is None or _http_client.is_closed:
            _http_client = httpx.AsyncClient(
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=10.0,
                follow_redirects=True,
            )
    return _http_client


async def close_client() -> None:
    """Close the shared httpx client. Call at application shutdown."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
    _http_client = None


async def fetch_news_for_symbol(
    symbol: str,
    market: str,
    symbol_name: str = "",
    max_articles: int = 5,
) -> list[dict[str, Any]]:
    """Fetch recent news for a single symbol."""
    if market == "KR":
        return await _fetch_kr_news(symbol, symbol_name, max_articles)
    else:
        return await _fetch_us_news(symbol, symbol_name, max_articles)


async def fetch_market_news(market: str, max_articles: int = 10) -> list[dict[str, Any]]:
    """Fetch general market/macro news."""
    if market == "KR":
        keywords = ["한국 증시", "코스피", "한국은행 금리"]
    else:
        keywords = ["stock market", "Federal Reserve", "S&P 500"]

    all_articles = []
    for kw in keywords:
        try:
            articles = await _fetch_google_news_rss(kw, max_articles=3)
            all_articles.extend(articles)
        except Exception as e:
            logger.warning("Market news fetch failed for '%s': %s", kw, e)

    # Deduplicate by title similarity
    seen_titles = set()
    unique = []
    for a in all_articles:
        title = a.get("title", "")
        if not title:
            continue
        title_key = title[:30].lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique.append(a)

    return unique[:max_articles]


async def _fetch_kr_news(
    symbol: str, name: str, max_articles: int,
) -> list[dict[str, Any]]:
    """Fetch Korean stock news from Naver Finance RSS."""
    articles = []

    # Method 1: Naver Finance stock news page (HTML scraping)
    try:
        naver_articles = await _fetch_naver_stock_news(symbol, max_articles)
        articles.extend(naver_articles)
    except Exception as e:
        logger.info("[News] Naver stock news failed for %s: %s", symbol, e)

    # Method 2: Google News RSS with Korean company name
    if len(articles) < max_articles and name:
        try:
            google_articles = await _fetch_google_news_rss(
                f"{name} 주식", max_articles=max_articles - len(articles),
            )
            articles.extend(google_articles)
        except Exception as e:
            logger.info("[News] Google News KR failed for %s: %s", name, e)

    return articles[:max_articles]


async def _fetch_us_news(
    symbol: str, name: str, max_articles: int,
) -> list[dict[str, Any]]:
    """Fetch US stock news from Finviz and Google News RSS."""
    articles = []

    # Method 1: Finviz news page
    try:
        finviz_articles = await _fetch_finviz_news(symbol, max_articles)
        articles.extend(finviz_articles)
    except Exception as e:
        logger.debug("Finviz news failed for %s: %s", symbol, e)

    # Method 2: Google News RSS
    if len(articles) < max_articles:
        try:
            query = f"{symbol} stock" if not name else f"{name} stock"
            google_articles = await _fetch_google_news_rss(
                query, max_articles=max_articles - len(articles),
            )
            articles.extend(google_articles)
        except Exception as e:
            logger.debug("Google News US failed for %s: %s", symbol, e)

    return articles[:max_articles]


async def _fetch_naver_stock_news(symbol: str, max_articles: int) -> list[dict]:
    """Scrape Naver Finance news headlines for a KR stock."""
    if not _SYMBOL_RE.match(symbol):
        logger.warning("Invalid symbol format rejected: %s", symbol[:20])
        return []
    url = f"https://finance.naver.com/item/news_news.naver?code={symbol}&page=1"

    client = await _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    html = resp.text

    articles = []
    # Try multiple patterns for robustness (Naver changes HTML periodically)
    patterns = [
        r'class="tit"[^>]*>([^<]+)</a>',           # Legacy pattern
        r'<td\s+class="title">\s*<a[^>]*>([^<]+)</a>',  # Table-based layout
        r'class="articleSubject"[^>]*>\s*<a[^>]*>([^<]+)</a>',  # Article layout
    ]
    matches = []
    for pattern in patterns:
        matches = re.findall(pattern, html)
        if matches:
            break

    for title in matches[:max_articles]:
        title = title.strip()
        if title and len(title) > 5:
            articles.append({
                "title": title,
                "source": "naver",
                "symbol": symbol,
                "market": "KR",
                "published": datetime.now(timezone.utc).isoformat(),
            })

    if not articles:
        logger.info("[News] Naver scraper returned 0 articles for %s (page length: %d)", symbol, len(html))

    return articles


async def _fetch_finviz_news(symbol: str, max_articles: int) -> list[dict]:
    """Scrape Finviz news headlines for a US stock."""
    if not _SYMBOL_RE.match(symbol):
        logger.warning("Invalid symbol format rejected: %s", symbol[:20])
        return []
    url = f"https://finviz.com/quote.ashx?t={symbol}"

    client = await _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    html = resp.text

    articles = []
    # Find news table rows: <a href="..." class="tab-link-news">Title</a>
    pattern = r'class="tab-link-news"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, html)

    for title in matches[:max_articles]:
        title = title.strip()
        if title and len(title) > 5:
            articles.append({
                "title": title,
                "source": "finviz",
                "symbol": symbol,
                "market": "US",
                "published": datetime.now(timezone.utc).isoformat(),
            })

    return articles


async def _fetch_google_news_rss(
    query: str, max_articles: int = 5,
) -> list[dict]:
    """Fetch news from Google News RSS feed."""
    encoded = quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"

    client = await _get_client()
    resp = await client.get(url)
    resp.raise_for_status()
    xml_text = resp.text

    articles = []
    try:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return articles

        for item in channel.findall("item")[:max_articles]:
            title = item.findtext("title", "").strip()
            pub_date = item.findtext("pubDate", "")
            source = item.findtext("source", "google")

            if title:
                articles.append({
                    "title": title,
                    "source": source if source else "google",
                    "published": pub_date,
                    "market": "global",
                })
    except ET.ParseError as e:
        logger.warning("Google News RSS parse error: %s", e)

    return articles
