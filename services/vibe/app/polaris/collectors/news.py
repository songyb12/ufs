"""News Collector for POLARIS — Fetch political news via Google News RSS.

Focused on political figure-specific news rather than stock-specific news.
Uses the same httpx client pattern as the existing news.py collector.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx

logger = logging.getLogger("vibe.polaris.collectors.news")

_client: httpx.AsyncClient | None = None
_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"

# Language/region configs
LANG_CONFIGS = {
    "US": {"hl": "en", "gl": "US", "ceid": "US:en"},
    "KR": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
    "global": {"hl": "en", "gl": "US", "ceid": "US:en"},
}


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; VIBE-POLARIS/1.0)"},
            follow_redirects=True,
        )
    return _client


def _clean_html(text: str) -> str:
    """Strip HTML tags from RSS description."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rss_items(xml_text: str, max_items: int = 10) -> list[dict]:
    """Parse Google News RSS XML into structured items."""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse RSS XML")
        return items

    for item in root.iter("item"):
        if len(items) >= max_items:
            break

        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")
        desc_el = item.find("description")
        source_el = item.find("source")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        if not title:
            continue

        items.append({
            "title": title,
            "url": link_el.text.strip() if link_el is not None and link_el.text else "",
            "published": pub_date_el.text.strip() if pub_date_el is not None and pub_date_el.text else "",
            "description": _clean_html(desc_el.text) if desc_el is not None and desc_el.text else "",
            "source": source_el.text.strip() if source_el is not None and source_el.text else "",
        })

    return items


async def fetch_figure_news(
    figure_name: str,
    country: str = "US",
    extra_keywords: list[str] | None = None,
    max_articles: int = 10,
) -> list[dict]:
    """Fetch recent news articles about a political figure.

    Args:
        figure_name: Name of the figure (e.g., "Donald Trump").
        country: Country code for language/region config.
        extra_keywords: Additional search terms to narrow results.
        max_articles: Maximum articles to return.

    Returns:
        List of news article dicts with title, url, published, description, source.
    """
    client = await _get_client()
    lang_cfg = LANG_CONFIGS.get(country, LANG_CONFIGS["global"])

    # Build search query
    query_parts = [f'"{figure_name}"']
    if extra_keywords:
        query_parts.extend(extra_keywords)
    query = " ".join(query_parts)

    url = _GOOGLE_NEWS_RSS.format(
        query=quote(query),
        hl=lang_cfg["hl"],
        gl=lang_cfg["gl"],
        ceid=lang_cfg["ceid"],
    )

    try:
        resp = await client.get(url)
        resp.raise_for_status()
        articles = _parse_rss_items(resp.text, max_items=max_articles)
        logger.info("Fetched %d news articles for %s", len(articles), figure_name)
        return articles
    except httpx.HTTPError as e:
        logger.warning("News fetch failed for %s: %s", figure_name, e)
        return []


async def fetch_multi_figure_news(
    figures: list[dict],
    max_per_figure: int = 5,
) -> dict[str, list[dict]]:
    """Fetch news for multiple figures.

    Args:
        figures: List of figure dicts with 'name' and 'country' keys.
        max_per_figure: Max articles per figure.

    Returns:
        Dict mapping figure_id to list of articles.
    """
    import asyncio

    results = {}

    async def _fetch_one(fig: dict) -> tuple[str, list[dict]]:
        articles = await fetch_figure_news(
            figure_name=fig["name"],
            country=fig.get("country", "US"),
            max_articles=max_per_figure,
        )
        return fig.get("id", fig["name"]), articles

    tasks = [_fetch_one(fig) for fig in figures]
    for coro in asyncio.as_completed(tasks):
        fig_id, articles = await coro
        results[fig_id] = articles

    return results
