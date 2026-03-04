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


# ── Backtesting ──


class BacktestRequest(BaseModel):
    market: Market
    start_date: str | None = None
    end_date: str | None = None
    config_overrides: dict | None = None


class BacktestRunResponse(BaseModel):
    backtest_id: str
    status: str
    message: str


class BacktestResultResponse(BaseModel):
    backtest_id: str
    market: str
    start_date: str
    end_date: str
    status: str
    total_trades: int = 0
    hit_rate: float | None = None
    avg_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    profit_factor: float | None = None
    win_loss_ratio: float | None = None
    total_return: float | None = None


class BacktestTradeResponse(BaseModel):
    symbol: str
    market: str
    entry_date: str
    entry_price: float
    entry_signal: str
    entry_score: float
    exit_date: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    return_pct: float | None = None
    holding_days: int | None = None


class SignalPerformanceResponse(BaseModel):
    total_signals: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    hit_rate_t5: float | None = None
    hit_rate_t20: float | None = None
    avg_return_t5: float | None = None
    avg_return_t20: float | None = None


# ── Portfolio (Phase E) ──


class PortfolioPositionCreate(BaseModel):
    symbol: str
    market: Market
    position_size: float
    entry_date: str | None = None
    entry_price: float | None = None
    sector: str | None = None


class PortfolioScenarioResponse(BaseModel):
    held_scenarios: list[dict] = []
    entry_scenarios: list[dict] = []
    total: int = 0
