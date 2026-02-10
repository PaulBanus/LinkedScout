"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # type: ignore[misc]
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="LINKEDSCOUT_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Directories and files
    alerts_file: Path = Path("alerts.yaml")
    output_dir: Path = Path("output")
    db_path: Path = Path("linkedscout.db")

    # Rate limiting
    request_delay: float = 1.5  # Seconds between requests
    max_retries: int = 3
    # Adaptive backoff
    backoff_multiplier: float = 2.0  # Multiply delay by this on 429
    max_backoff_delay: float = 30.0  # Cap maximum delay
    backoff_reset_after: int = 5  # Reset backoff after N successful requests

    # HTTP client settings
    timeout: float = 30.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()
