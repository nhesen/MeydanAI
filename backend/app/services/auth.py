import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.core.passwords import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.domain import AuthSession, User
from app.repositories.auth import AuthRepository
from app.schemas.auth import AuthCredentials, AuthSessionResponse, UserResponse
from app.services.matches import aware, create_token, hash_token

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AuthRepository(session)

    def register(self, payload: AuthCredentials) -> AuthSessionResponse:
        existing = self.repository.get_user_by_email(payload.email)
        if existing is not None:
            raise self._account_rejected()
        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=self._initial_role(payload.email),
        )
        self.repository.add(user)
        try:
            self.session.flush()
        except IntegrityError as exception:
            self.session.rollback()
            raise self._account_rejected() from exception
        logger.info("user_registered", extra={"user_id": str(user.id), "role": user.role})
        return self._issue_session(user)

    def login(self, payload: AuthCredentials) -> AuthSessionResponse:
        user = self.repository.get_user_by_email(payload.email)
        password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        if user is None or not verify_password(password_hash, payload.password):
            raise DomainError(
                status=401,
                title="Authentication required",
                detail="Invalid email or password.",
                error_code="INVALID_CREDENTIALS",
            )
        logger.info("user_logged_in", extra={"user_id": str(user.id), "role": user.role})
        return self._issue_session(user)

    def logout(self, token: str) -> None:
        record = self.repository.get_session_by_hash(hash_token(token))
        if record is not None and record.revoked_at is None:
            self.repository.revoke_session(record)
            self.session.commit()
            logger.info("user_logged_out", extra={"user_id": str(record.user_id)})

    def resolve_session(self, token: str) -> User:
        if len(token) < 32 or len(token) > 200:
            raise self._invalid_session()
        record = self.repository.get_session_by_hash(hash_token(token))
        now = datetime.now(UTC)
        if record is None or record.revoked_at is not None or aware(record.expires_at) <= now:
            raise self._invalid_session()
        user = self.repository.get_user(record.user_id)
        if user is None:
            raise self._invalid_session()
        return user

    def to_user_response(self, user: User) -> UserResponse:
        return UserResponse.model_validate(user)

    def _issue_session(self, user: User) -> AuthSessionResponse:
        token = create_token()
        expires_at = datetime.now(UTC) + timedelta(hours=get_settings().auth_session_ttl_hours)
        self.repository.add(
            AuthSession(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=expires_at,
            )
        )
        self.session.commit()
        return AuthSessionResponse(
            user=self.to_user_response(user),
            access_token=token,
            expires_at=expires_at,
        )

    def _initial_role(self, email: str) -> str:
        bootstrap = get_settings().auth_bootstrap_admin_email
        if bootstrap and email == bootstrap and self.repository.admin_count() == 0:
            return "admin"
        return "user"

    @staticmethod
    def _account_rejected() -> DomainError:
        return DomainError(
            status=409,
            title="Unable to create account",
            detail="Unable to create this account.",
            error_code="ACCOUNT_NOT_CREATED",
        )

    @staticmethod
    def _invalid_session() -> DomainError:
        return DomainError(
            status=401,
            title="Authentication required",
            detail="Your session is invalid or has expired.",
            error_code="INVALID_SESSION",
        )
