from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_FAST_HASHER = PasswordHasher(time_cost=1, memory_cost=8_192, parallelism=1)
_PRODUCTION_HASHER = PasswordHasher()
DUMMY_PASSWORD_HASH = _FAST_HASHER.hash("meydanai-timing-dummy")


def _hasher() -> PasswordHasher:
    from app.core.config import get_settings

    return _FAST_HASHER if get_settings().app_env == "test" else _PRODUCTION_HASHER


def hash_password(password: str) -> str:
    return _hasher().hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher().verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
