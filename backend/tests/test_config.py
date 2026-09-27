import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_parse_multiple_cors_origins() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:pass@localhost:5432/meydanai",
        cors_allowed_origins="http://localhost:3000, https://app.example.com",
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://app.example.com",
    ]


def test_settings_reject_non_postgresql_database() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="sqlite:///local.db",
            cors_allowed_origins="http://localhost:3000",
        )


def test_production_rejects_wildcard_cors_and_disabled_rate_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://user:pass@localhost:5432/meydanai",
            cors_allowed_origins="https://app.example.com,*",
        )

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://user:pass@localhost:5432/meydanai",
            cors_allowed_origins="https://app.example.com",
            auth_rate_limit_enabled=False,
        )


def test_production_accepts_explicit_origins_and_rate_limits() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+psycopg://user:pass@localhost:5432/meydanai",
        cors_allowed_origins="https://app.example.com",
    )

    assert settings.cors_origins == ["https://app.example.com"]
    assert settings.auth_rate_limit_enabled is True


def test_processing_settings_disable_empty_worker_token() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:pass@localhost:5432/meydanai",
        cors_allowed_origins="http://localhost:3000",
        internal_worker_token=" ",
    )

    assert settings.internal_worker_token is None
