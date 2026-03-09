from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Life-Master service configuration."""

    SERVICE_NAME: str = "life-master"
    SERVICE_PORT: int = 8004
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DB_PATH: str = "/app/data/life-master.db"

    # Scheduler defaults
    DAY_START_HOUR: int = 6
    DAY_END_HOUR: int = 23
    SLOT_INTERVAL_MIN: int = 30

    # Data retention
    RETENTION_LOG_DAYS: int = 365

    # CORS
    CORS_EXTRA_ORIGINS: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
