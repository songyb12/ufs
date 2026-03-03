from enum import StrEnum


class Market(StrEnum):
    KR = "KR"
    US = "US"


class SignalType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class AssetType(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"


class PipelineStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
