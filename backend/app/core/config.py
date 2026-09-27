from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MeydanAI API"
    app_env: Literal["development", "test", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    cors_allowed_origins: str
    analytics_provider: Literal["external"] = "external"
    max_video_upload_size: int = Field(default=524_288_000, gt=0)
    video_storage_path: Path = Path("./var/videos")
    raw_video_retention_days: int = Field(default=30, ge=1)
    max_position_samples_per_ingestion: int = Field(default=10_000, ge=1)
    internal_worker_token: str | None = None
    auth_session_ttl_hours: int = Field(default=168, ge=1, le=720)
    auth_bootstrap_admin_email: str | None = None
    auth_rate_limit_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql+psycopg://", "postgresql://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must contain at least one origin")

        for origin in origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid CORS origin: {origin}")
        return ",".join(origins)

    @property
    def cors_origins(self) -> list[str]:
        return self.cors_allowed_origins.split(",")

    @field_validator("internal_worker_token")
    @classmethod
    def normalize_worker_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("auth_bootstrap_admin_email")
    @classmethod
    def normalize_bootstrap_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        return normalized or None

    @model_validator(mode="after")
    def reject_unsafe_production_settings(self) -> Self:
        if self.app_env != "production":
            return self
        if "*" in self.cors_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS cannot include a wildcard in production")
        if not self.auth_rate_limit_enabled:
            raise ValueError("AUTH_RATE_LIMIT_ENABLED must stay enabled in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
