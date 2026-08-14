"""InsightFlow backend application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "InsightFlow"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = (
        "postgresql+asyncpg://insightflow:insightflow_dev@localhost:5432/insightflow"
    )
    database_pool_size: int = 20
    database_pool_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 300

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_reports: str = "insightflow-reports"
    minio_bucket_models: str = "insightflow-models"
    minio_secure: bool = False

    # LLM Provider
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_fast_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # CORS
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()


settings = get_settings()
