"""Data management API endpoints — price refresh, data status."""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

from app.database import repositories as repo

logger = logging.getLogger("vibe.routers.data")

router = APIRouter(prefix="/data", tags=["data"])


@router.post("/prices/refresh")
async def refresh_prices(
    request: Request,
    market: str = Query("ALL", pattern="^(KR|US|ALL)$"),
    days: int = Query(10, ge=1, le=200),
):
    """Fetch latest prices for portfolio + watchlist symbols WITHOUT running the full pipeline.

    This is a lightweight operation that only updates price_history.
    Use this when portfolio returns show '-' due to missing price data.
    """
    registry = getattr(request.app.state, "collector_registry", None)
    if registry is None:
        raise HTTPException(500, "Collector registry not initialized")

    markets = ["KR", "US"] if market == "ALL" else [market]
    end_date = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    results = {}
    for mkt in markets:
        # Gather symbols: watchlist + portfolio (union)
        watchlist_syms = await repo.get_active_symbols(mkt)
        portfolio_syms = await _get_portfolio_symbols(mkt)
        all_symbols = list(set(watchlist_syms + portfolio_syms))

        if not all_symbols:
            results[mkt] = {"symbols": 0, "rows": 0, "status": "no_symbols"}
            continue

        logger.info(
            "[PriceRefresh] %s: %d symbols (watchlist=%d, portfolio=%d)",
            mkt, len(all_symbols), len(watchlist_syms), len(portfolio_syms),
        )

        try:
            collector = registry.get(mkt)
            ohlcv_data = await collector.fetch_ohlcv_batch(
                all_symbols, start_date, end_date,
            )

            total_rows = 0
            collected = []
            failed = []
            for symbol, df in ohlcv_data.items():
                rows = [
                    {
                        "symbol": symbol,
                        "market": mkt,
                        "trade_date": date_str,
                        "open": float(row.get("open", 0)) if row.get("open") is not None else None,
                        "high": float(row.get("high", 0)) if row.get("high") is not None else None,
                        "low": float(row.get("low", 0)) if row.get("low") is not None else None,
                        "close": float(row.get("close", 0)) if row.get("close") is not None else None,
                        "volume": int(row.get("volume", 0)) if row.get("volume") is not None else None,
                        "adjusted_close": float(row.get("adj_close", 0)) if row.get("adj_close") is not None else None,
                    }
                    for date_str, row in df.iterrows()
                ]
                count = await repo.upsert_price_history(rows)
                total_rows += count
                collected.append(symbol)

            failed = [s for s in all_symbols if s not in collected]

            results[mkt] = {
                "symbols": len(collected),
                "rows": total_rows,
                "failed": failed,
                "status": "success" if not failed else "partial",
            }
            logger.info(
                "[PriceRefresh] %s: %d symbols, %d rows stored",
                mkt, len(collected), total_rows,
            )

        except Exception as e:
            logger.error("[PriceRefresh] %s failed: %s", mkt, e, exc_info=True)
            results[mkt] = {"symbols": 0, "rows": 0, "status": "error", "error": "Price refresh failed. Check server logs."}

    return {
        "status": "ok",
        "markets": results,
        "total_rows": sum(r.get("rows", 0) for r in results.values()),
    }


async def _get_portfolio_symbols(market: str) -> list[str]:
    """Get all distinct symbols from portfolio_state for the given market."""
    from app.database.connection import get_db

    db = await get_db()
    cursor = await db.execute(
        "SELECT DISTINCT symbol FROM portfolio_state WHERE market = ? AND position_size > 0",
        (market,),
    )
    rows = await cursor.fetchall()
    return [r["symbol"] for r in rows]
