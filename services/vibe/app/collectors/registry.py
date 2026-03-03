from app.collectors.base import BaseCollector
from app.collectors.kr_market import KRMarketCollector
from app.collectors.macro import MacroCollector
from app.collectors.us_market import USMarketCollector
from app.config import Settings


class CollectorRegistry:
    """Registry mapping market identifiers to their collectors."""

    def __init__(self, config: Settings):
        self._collectors: dict[str, BaseCollector] = {
            "KR": KRMarketCollector(config),
            "US": USMarketCollector(config),
        }
        self.macro = MacroCollector(config)

    def get(self, market: str) -> BaseCollector:
        collector = self._collectors.get(market.upper())
        if not collector:
            raise ValueError(f"No collector registered for market: {market}")
        return collector

    @property
    def markets(self) -> list[str]:
        return list(self._collectors.keys())
