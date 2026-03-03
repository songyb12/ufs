from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """VIBE service configuration."""

    SERVICE_NAME: str = "vibe"
    SERVICE_PORT: int = 8001
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DB_PATH: str = "/app/data/vibe.db"

    # Discord
    DISCORD_WEBHOOK_URL: str = ""

    # Hard Limit thresholds
    RSI_HARD_LIMIT: float = 65.0
    RSI_BUY_THRESHOLD_KR: float = 50.0  # 국장
    RSI_BUY_THRESHOLD_US: float = 55.0  # 미장
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
    BACKTEST_STOP_LOSS_PCT: float = -5.0  # -5% stop loss

    # Signal Performance Tracking
    PERFORMANCE_TRACKING_ENABLED: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
