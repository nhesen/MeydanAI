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
