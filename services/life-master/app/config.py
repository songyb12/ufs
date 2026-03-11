from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Life-Master service configuration."""

    SERVICE_NAME: str = "life-master"
    SERVICE_PORT: int = 8004
    VERSION: str = "0.2.0"
    DEBUG: bool = False

    # Database
    DB_PATH: str = "/app/data/life-master.db"

    # Scheduler defaults
    DAY_START_HOUR: int = Field(default=6, ge=0, le=23)
    DAY_END_HOUR: int = Field(default=23, ge=1, le=23)
    SLOT_INTERVAL_MIN: int = Field(default=30, ge=5, le=120)

    # Data retention
    RETENTION_LOG_DAYS: int = Field(default=365, ge=30)

    # CORS
    CORS_EXTRA_ORIGINS: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"

    # Notifications (Pushover for Apple Watch support)
    PUSHOVER_USER_KEY: str = ""
    PUSHOVER_APP_TOKEN: str = ""
    NTFY_TOPIC: str = ""
    NTFY_SERVER: str = "https://ntfy.sh"
    NOTIFICATION_PROVIDER: str = "pushover"  # "pushover" or "ntfy"
    NOTIFICATION_ENABLED: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
