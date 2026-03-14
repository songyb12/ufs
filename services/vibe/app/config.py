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
    KR_PIPELINE_HOUR_UTC: int = 0  # 09:00 KST (한국장 개장 시간)
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

    # Signal scoring weights (must sum to 1.0 with WEIGHT_SENTIMENT + WEIGHT_NEWS)
    WEIGHT_TECHNICAL: float = 0.30
    WEIGHT_MACRO: float = 0.18
    WEIGHT_FUND_FLOW: float = 0.22  # KR only; US redistributes to tech/macro
    WEIGHT_FUNDAMENTAL: float = 0.18

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
    LLM_MODEL: str = "claude-haiku-4-5-20251001"

    # US Fund Flow (Phase D)
    US_FUND_FLOW_ENABLED: bool = True

    # Korean Explanation (Phase E)
    EXPLANATION_ALWAYS_ENABLED: bool = True  # Rule-based always on
    LLM_EXPLANATION_ENABLED: bool = False  # LLM-enhanced explanation
    LLM_EXPLANATION_MODEL: str = ""  # Empty = use LLM_MODEL

    # Portfolio Scenarios (Phase E)
    PORTFOLIO_SCENARIOS_ENABLED: bool = True  # Rule-based scenarios
    LLM_SCENARIO_ENABLED: bool = False  # LLM-enhanced scenarios

    # API Authentication
    API_KEY: str = ""  # Set via .env; empty = no auth required
    API_AUTH_ENABLED: bool = False  # Enable API key authentication

    # JWT Authentication (ID/Password login)
    JWT_SECRET: str = ""  # Empty = auto-generate at startup (uuid4)
    JWT_EXPIRE_HOURS: int = 168  # 7 days (personal server)

    # Finnhub Live Data (SOXL real-time)
    FINNHUB_API_KEY: str = ""           # Set via .env
    FINNHUB_POLL_INTERVAL: int = 15     # SOXL quote poll interval (seconds)
    FINNHUB_SECTOR_INTERVAL: int = 60   # Sector ETF poll interval (seconds)
    FINNHUB_RATE_LIMIT: int = 55        # Effective limit (5 buffer from 60/min)

    # CORS (comma-separated extra origins for external access)
    CORS_EXTRA_ORIGINS: str = ""  # e.g. "https://vibe.example.com"

    # Signal Thresholds (was hardcoded, now configurable)
    SIGNAL_BUY_THRESHOLD: float = 15.0  # raw_score > this → BUY
    SIGNAL_SELL_THRESHOLD: float = -15.0  # raw_score < this → SELL

    # Data Retention
    RETENTION_PRICE_DAYS: int = 400  # Keep price_history for ~2 years
    RETENTION_SIGNAL_DAYS: int = 365  # Keep signals for 1 year
    RETENTION_NEWS_DAYS: int = 90  # Keep news data for 3 months
    RETENTION_PIPELINE_RUNS_DAYS: int = 90

    # News Analysis (Phase F)
    NEWS_ENABLED: bool = True
    WEIGHT_NEWS: float = 0.02  # News weight in signal scoring (sum with other weights = 1.0)
    NEWS_MAX_ARTICLES: int = 5  # Max articles per symbol

    # Logging
    LOG_FORMAT: str = "text"  # 'text' (human-readable) or 'json' (structured)
    LOG_LEVEL: str = "INFO"   # DEBUG, INFO, WARNING, ERROR

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
