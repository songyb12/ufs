from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """VIBE service configuration."""

    SERVICE_NAME: str = "vibe"
    SERVICE_PORT: int = 8001
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DB_PATH: str = "/app/data/vibe.db"
    DB_BACKUP_DIR: str = "/app/data/backups"
    DB_BACKUP_KEEP_DAYS: int = 7  # Keep backups for 7 days

    # Discord
    DISCORD_WEBHOOK_URL: str = ""

    # Hard Limit thresholds (grid search optimized: aggressive)
    RSI_HARD_LIMIT: float = 65.0
    RSI_BUY_THRESHOLD_KR: float = 45.0  # 국장 (Sharpe 1.49, Hit 55.6%)
    RSI_BUY_THRESHOLD_US: float = 50.0  # 미장 (비례 조정)
    DISPARITY_HARD_LIMIT: float = 105.0  # 20일선 이격도 %

    # Scheduler
    SCHEDULER_ENABLED: bool = True
    KR_PIPELINE_HOUR_UTC: int = 7  # 16:00 KST
    KR_PIPELINE_MINUTE: int = 0
    US_PIPELINE_HOUR_UTC: int = 22  # 17:00 EST (winter)
    US_PIPELINE_MINUTE: int = 0
    MACRO_COLLECT_HOUR_UTC: int = 5
    MACRO_COLLECT_MINUTE: int = 0

    # Data collection
    PRICE_HISTORY_DAYS: int = 200
    COLLECTION_DELAY_SECONDS: float = 1.0  # pykrx rate limiting
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_BASE_DELAY: float = 2.0

    # Signal scoring weights
    WEIGHT_TECHNICAL: float = 0.35
    WEIGHT_MACRO: float = 0.20
    WEIGHT_FUND_FLOW: float = 0.25  # KR only; US redistributes to tech/macro
    WEIGHT_FUNDAMENTAL: float = 0.20

    # Red-Team (Stage 7)
    RED_TEAM_ENABLED: bool = True

    # Backtesting
    BACKTEST_DEFAULT_DAYS: int = 365
    BACKTEST_TRADE_EXIT_DAYS: int = 20  # Max hold period before forced close
    BACKTEST_STOP_LOSS_PCT: float = -7.0  # -7% stop loss (grid optimized)

    # Signal Performance Tracking
    PERFORMANCE_TRACKING_ENABLED: bool = True

    # Position Sizing (Phase B)
    PORTFOLIO_TOTAL: float = 100_000_000  # 1억 KRW
    MAX_SINGLE_POSITION_PCT: float = 0.10  # 10% max per symbol
    MAX_SECTOR_EXPOSURE_PCT: float = 0.30  # 30% max per sector
    POSITION_SIZING_METHOD: str = "fixed_fraction"  # 'kelly' or 'fixed_fraction'

    # Event Calendar (Phase B)
    EVENT_SUPPRESS_DAYS: int = 3  # D-3 event warning window
    EVENT_SUPPRESS_ENABLED: bool = True

    # Sentiment (Phase D)
    SENTIMENT_FETCH_ENABLED: bool = True
    WEIGHT_SENTIMENT: float = 0.10  # Sentiment impact on signal scoring

    # LLM Red-Team (Phase D)
    LLM_RED_TEAM_ENABLED: bool = False  # Enable after API key setup
    LLM_PROVIDER: str = "anthropic"  # 'anthropic' or 'openai'
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "claude-3-haiku-20240307"

    # US Fund Flow (Phase D)
    US_FUND_FLOW_ENABLED: bool = True

    # Korean Explanation (Phase E)
    EXPLANATION_ALWAYS_ENABLED: bool = True  # Rule-based always on
    LLM_EXPLANATION_ENABLED: bool = False  # LLM-enhanced explanation
    LLM_EXPLANATION_MODEL: str = ""  # Empty = use LLM_MODEL

    # Portfolio Scenarios (Phase E)
    PORTFOLIO_SCENARIOS_ENABLED: bool = True  # Rule-based scenarios
    LLM_SCENARIO_ENABLED: bool = False  # LLM-enhanced scenarios

    # News Analysis (Phase F)
    NEWS_ENABLED: bool = True
    WEIGHT_NEWS: float = 0.0  # News weight in signal scoring (0=disabled in scoring)
    NEWS_MAX_ARTICLES: int = 5  # Max articles per symbol

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
