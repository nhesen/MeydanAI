import hashlib
import secrets
from datetime import UTC, datetime


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token() -> str:
    return secrets.token_urlsafe(32)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
