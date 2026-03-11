import logging

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Master Core configuration."""

    SERVICE_NAME: str = "master-core"
    VERSION: str = "0.2.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Level 1 service URLs
    VIBE_URL: str = "http://vibe:8001"
    LAB_STUDIO_URL: str = "http://lab-studio:8002"
    ENGINEERING_OPS_URL: str = "http://engineering-ops:8003"
    LIFE_MASTER_URL: str = "http://life-master:8004"

    # Discord (shared)
    DISCORD_WEBHOOK_URL: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# Service registry: name -> URL mapping
SERVICE_REGISTRY: dict[str, str] = {
    "vibe": settings.VIBE_URL,
    "lab-studio": settings.LAB_STUDIO_URL,
    "engineering-ops": settings.ENGINEERING_OPS_URL,
    "life-master": settings.LIFE_MASTER_URL,
}
