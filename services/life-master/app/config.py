from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Life-Master service configuration."""

    SERVICE_NAME: str = "life-master"
    SERVICE_PORT: int = 8004
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DB_PATH: str = "/app/data/life-master.db"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
