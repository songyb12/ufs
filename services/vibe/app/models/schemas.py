from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AssetType, Market, PipelineStatus, SignalType


# ── Watchlist ──


class WatchlistItemCreate(BaseModel):
    symbol: str
    name: str
    market: Market
    asset_type: AssetType = AssetType.STOCK


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    name: str
    market: Market
    asset_type: AssetType
    is_active: bool
    created_at: str


class WatchlistBulkCreate(BaseModel):
    items: list[WatchlistItemCreate]


# ── Pipeline ──


class PipelineRunRequest(BaseModel):
    market: Market | str = Field(
        default="ALL",
        description="KR, US, or ALL",
    )


class PipelineRunResponse(BaseModel):
    run_id: str
    market: str
    status: PipelineStatus
    started_at: str
    message: str


class PipelineRunDetail(BaseModel):
    run_id: str
    run_type: str
    market: str
    status: PipelineStatus
    started_at: str
    completed_at: str | None = None
    stages_completed: list[str] = []
    error_message: str | None = None


# ── Signals ──


class SignalResponse(BaseModel):
    symbol: str
    name: str | None = None
    market: Market
    signal_date: str
    raw_signal: SignalType
    raw_score: float
    hard_limit_triggered: bool
    hard_limit_reason: str | None = None
    final_signal: SignalType
    confidence: float | None = None
    red_team_warning: str | None = None
    rsi_value: float | None = None
    disparity_value: float | None = None
    rationale: str | None = None


class SignalsListResponse(BaseModel):
    market: str
    signal_date: str
    count: int
    signals: list[SignalResponse]


# ── Dashboard ──


class DashboardResponse(BaseModel):
    snapshot_date: str
    market: str
    run_id: str
    content: dict
    discord_sent: bool
    discord_sent_at: str | None = None


class DashboardHistoryItem(BaseModel):
    id: int
    snapshot_date: str
    market: str
    run_id: str
    discord_sent: bool


# ── Health ──


class HealthResponse(BaseModel):
    service: str
    status: str
    version: str
    timestamp: str
    db_connected: bool = False
    scheduler_running: bool = False
    last_pipeline_run: str | None = None
