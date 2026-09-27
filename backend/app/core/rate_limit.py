import time
from collections import defaultdict

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import DomainError

_hits: dict[str, list[float]] = defaultdict(list)


def reset_rate_limits() -> None:
    _hits.clear()


def enforce_rate_limit(request: Request, *, scope: str, limit: int, window_seconds: int) -> None:
    if not get_settings().auth_rate_limit_enabled:
        return
    client = request.client.host if request.client is not None else "unknown"
    key = f"{scope}:{client}"
    now = time.monotonic()
    recent = [stamp for stamp in _hits[key] if now - stamp < window_seconds]
    if len(recent) >= limit:
        raise DomainError(
            status=429,
            title="Too many requests",
            detail="Please wait before trying again.",
            error_code="RATE_LIMITED",
        )
    recent.append(now)
    _hits[key] = recent


def rate_limit_auth(request: Request) -> None:
    enforce_rate_limit(request, scope="auth", limit=10, window_seconds=60)


def rate_limit_join(request: Request) -> None:
    enforce_rate_limit(request, scope="join", limit=30, window_seconds=60)


def rate_limit_search(request: Request) -> None:
    enforce_rate_limit(request, scope="search", limit=60, window_seconds=60)
