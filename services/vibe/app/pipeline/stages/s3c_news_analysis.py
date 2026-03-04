"""Stage 3c: News Analysis - Collect and score news for each symbol.

Uses RSS-based news fetching (no API key required).
Provides per-symbol news scores and market-level news summary.
"""

import asyncio
import logging
from typing import Any

from app.collectors.news import fetch_market_news, fetch_news_for_symbol
from app.config import Settings
from app.database import repositories as repo
from app.indicators.news_scoring import compute_news_score
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s3c")


class NewsAnalysisStage(BaseStage):
    """Stage 3c: Collect news and compute sentiment scores per symbol."""

    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s3c_news_analysis"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return self.config.NEWS_ENABLED

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        symbols = context.get("symbols", [])
        symbol_names = context.get("symbol_names", {})
        warnings = []

        per_symbol_news: dict[str, dict] = {}
        market_news_data = {}

        # 1. Fetch market-level news
        try:
            market_articles = await fetch_market_news(market, max_articles=10)
            market_result = compute_news_score(market_articles)
            market_news_data = {
                "articles": market_articles,
                "score": market_result,
            }
            logger.info(
                "[S3c] Market news: %d articles, score=%+.1f (B:%d/N:%d/S:%d)",
                market_result["article_count"],
                market_result["news_score"],
                market_result["bullish_count"],
                market_result["neutral_count"],
                market_result["bearish_count"],
            )
        except Exception as e:
            warnings.append(f"Market news fetch failed: {e}")
            logger.warning("[S3c] Market news fetch failed: %s", e)

        # 2. Fetch per-symbol news (with rate limiting)
        max_articles = self.config.NEWS_MAX_ARTICLES
        fetched = 0
        failed = 0

        for symbol in symbols:
            name = symbol_names.get(symbol, symbol)
            try:
                articles = await fetch_news_for_symbol(
                    symbol=symbol,
                    market=market,
                    symbol_name=name,
                    max_articles=max_articles,
                )
                result = compute_news_score(articles)

                per_symbol_news[symbol] = {
                    "news_score": result["news_score"],
                    "article_count": result["article_count"],
                    "bullish_count": result["bullish_count"],
                    "bearish_count": result["bearish_count"],
                    "neutral_count": result["neutral_count"],
                    "headlines": result["headlines"],
                }
                fetched += 1

                if result["article_count"] > 0:
                    logger.debug(
                        "[S3c] %s (%s): %d articles, score=%+.1f",
                        symbol, name, result["article_count"], result["news_score"],
                    )

                # Rate limiting: 0.5s between requests
                await asyncio.sleep(0.5)

            except Exception as e:
                failed += 1
                per_symbol_news[symbol] = {
                    "news_score": 0.0,
                    "article_count": 0,
                    "bullish_count": 0,
                    "bearish_count": 0,
                    "neutral_count": 0,
                    "headlines": [],
                }
                logger.debug("[S3c] News fetch failed for %s: %s", symbol, e)

        if failed > 0:
            warnings.append(f"News fetch failed for {failed}/{len(symbols)} symbols")

        # Store news data to DB
        try:
            await _store_news_data(
                context["run_id"], context["date"], market,
                per_symbol_news, market_news_data,
            )
        except Exception as e:
            warnings.append(f"News DB store failed: {e}")

        logger.info(
            "[S3c] News analysis complete: %d/%d symbols fetched, %d failed",
            fetched, len(symbols), failed,
        )

        return StageResult(
            stage_name=self.name,
            status="success" if fetched > 0 else "partial",
            data={
                "per_symbol": per_symbol_news,
                "market_news": market_news_data,
            },
            warnings=warnings,
        )


async def _store_news_data(
    run_id: str, trade_date: str, market: str,
    per_symbol: dict, market_news: dict,
) -> None:
    """Store news data to news_data table."""
    import json

    rows = []
    for symbol, data in per_symbol.items():
        rows.append({
            "run_id": run_id,
            "symbol": symbol,
            "market": market,
            "trade_date": trade_date,
            "news_score": data["news_score"],
            "article_count": data["article_count"],
            "bullish_count": data["bullish_count"],
            "bearish_count": data["bearish_count"],
            "headlines_json": json.dumps(data.get("headlines", []), ensure_ascii=False),
        })

    if rows:
        await repo.insert_news_data(rows)
