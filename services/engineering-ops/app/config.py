from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Engineering-Ops service configuration."""

    SERVICE_NAME: str = "engineering-ops"
    SERVICE_PORT: int = 8003
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DB_PATH: str = "/app/data/engineering-ops.db"

    # Log parsing config (externalized for flexibility)
    LOG_PATTERNS_PATH: str = "/app/config/log_patterns.yaml"

    # CORS
    CORS_EXTRA_ORIGINS: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
