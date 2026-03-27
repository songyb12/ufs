"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./vibe2.db"
    ANTHROPIC_API_KEY: str = ""

    JWT_SECRET: str = "vibe2-dev-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24h

    SOXL_SYMBOLS: list[str] = [
        "SOXL", "SOXX", "^SOX", "^VIX", "^TNX", "DX-Y.NYB",
    ]
    UPDATE_INTERVAL_MINUTES: int = 30

    LOG_LEVEL: str = "INFO"


settings = Settings()
