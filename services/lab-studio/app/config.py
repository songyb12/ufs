from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Lab-Studio service configuration."""

    SERVICE_NAME: str = "lab-studio"
    SERVICE_PORT: int = 8002
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DB_PATH: str = "/app/data/lab-studio.db"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
