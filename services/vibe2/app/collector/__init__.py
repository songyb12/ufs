"""VIBE 2.0 data collection layer."""

import logging

from app.collector.macro import collect_all_macro
from app.collector.price import collect_all_prices
from app.collector.sentiment import collect_sentiment

logger = logging.getLogger("vibe2.collector")

__all__ = [
    "collect_all_prices",
    "collect_all_macro",
    "collect_sentiment",
    "collect_all",
]


def collect_all() -> dict:
    """Run all collectors and return summary.

    Returns dict with keys: prices, macro_rows, sentiment_ok.
    """
    logger.info("Starting full data collection...")

    prices = collect_all_prices()
    macro_rows = collect_all_macro()
    sentiment_ok = collect_sentiment()

    summary = {
        "prices": prices,
        "macro_rows": macro_rows,
        "sentiment_ok": sentiment_ok,
    }
    logger.info("Collection complete: %s", summary)
    return summary
