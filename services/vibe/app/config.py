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

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
