import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    APP_TITLE: str = "Bulk Certificate Generator API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "High-performance backend API for bulk certificate generation with "
        "asynchronous background execution, real-time progress tracking, "
        "individual failure isolation, and bulk ZIP retrieval."
    )
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Server binding
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database configuration (SQLite default, PostgreSQL supported)
    DATABASE_URL: str = "sqlite:///./certificates.db"

    # Storage paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    STORAGE_DIR: str = str(Path(__file__).resolve().parent.parent / "storage" / "certificates")
    ZIP_STORAGE_DIR: str = str(Path(__file__).resolve().parent.parent / "storage" / "zips")

    # Limits and constraints
    MAX_BATCH_SIZE: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure directories exist
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
os.makedirs(settings.ZIP_STORAGE_DIR, exist_ok=True)
