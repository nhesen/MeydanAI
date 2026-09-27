import secrets
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import DomainError
from app.models.domain import User

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]
OrganizerTokenHeader = Annotated[str | None, Header(alias="X-Organizer-Token")]


def authentication_required() -> DomainError:
    return DomainError(
        status=401,
        title="Authentication required",
        detail="Sign in to continue.",
        error_code="AUTHENTICATION_REQUIRED",
    )


def access_denied(
    detail: str = "You do not have permission to perform this action.",
) -> DomainError:
    return DomainError(
        status=403,
        title="Access denied",
        detail=detail,
        error_code="ACCESS_DENIED",
    )


def parse_bearer_token(authorization: str | None) -> str | None:
    if authorization is None or authorization.strip() == "":
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise DomainError(
            status=401,
            title="Authentication required",
            detail="Provide a valid Bearer token.",
            error_code="INVALID_AUTH_HEADER",
        )
    return token.strip()


def get_optional_user(
    session: DatabaseSession,
    authorization: AuthorizationHeader = None,
) -> User | None:
    from app.services.auth import AuthService

    token = parse_bearer_token(authorization)
    if token is None:
        return None
    return AuthService(session).resolve_session(token)


def require_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise authentication_required()
    return user


def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    if user.role != "admin":
        raise access_denied("Administrator access is required.")
    return user


def is_admin(user: User | None) -> bool:
    return user is not None and user.role == "admin"


def owns_match(user: User | None, organizer_user_id: object | None) -> bool:
    return user is not None and organizer_user_id is not None and user.id == organizer_user_id


def compare_secret(stored_hash: str, provided: str, hashed_provided: str) -> bool:
    if not provided:
        return False
    return secrets.compare_digest(stored_hash, hashed_provided)
