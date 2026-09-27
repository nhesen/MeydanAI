from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base, get_db
from app.core.exceptions import DomainError
from app.core.passwords import verify_password
from app.main import create_app
from app.models.domain import AuthSession, User
from app.schemas.auth import AuthCredentials
from app.services.auth import AuthService
from app.services.matches import hash_token


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database_session:
        yield database_session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    application = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql+psycopg://test:test@localhost:5432/test",
            cors_allowed_origins="http://localhost:3000",
            auth_rate_limit_enabled=False,
        )
    )

    def override_db() -> Generator[Session, None, None]:
        yield session

    application.dependency_overrides[get_db] = override_db
    with TestClient(application) as test_client:
        yield test_client


def credentials(email: str = "player@example.com", password: str = "password12") -> AuthCredentials:
    return AuthCredentials(email=email, password=password)


def test_register_success_hashes_password_and_issues_session(session: Session) -> None:
    created = AuthService(session).register(credentials())

    user = session.scalar(select(User).where(User.email == "player@example.com"))
    assert user is not None
    assert user.role == "user"
    assert user.password_hash != "password12"
    assert verify_password(user.password_hash, "password12")
    stored = session.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_token(created.access_token))
    )
    assert stored is not None
    assert created.user.email == "player@example.com"
    assert "password" not in created.model_dump()


def test_duplicate_account_is_rejected(session: Session) -> None:
    service = AuthService(session)
    service.register(credentials())

    with pytest.raises(DomainError) as raised:
        service.register(credentials())
    assert raised.value.status == 409
    assert raised.value.error_code == "ACCOUNT_NOT_CREATED"


def test_login_success_and_invalid_password_rejected(session: Session) -> None:
    service = AuthService(session)
    service.register(credentials())

    logged_in = service.login(credentials())
    assert logged_in.user.email == "player@example.com"

    with pytest.raises(DomainError) as raised:
        service.login(credentials(password="wrong-password"))
    assert raised.value.status == 401
    assert raised.value.detail == "Invalid email or password."


def test_unknown_email_uses_same_login_message(session: Session) -> None:
    with pytest.raises(DomainError) as raised:
        AuthService(session).login(credentials(email="missing@example.com"))
    assert raised.value.detail == "Invalid email or password."


def test_unauthenticated_me_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["errorCode"] == "AUTHENTICATION_REQUIRED"


def test_login_and_me_roundtrip(client: TestClient) -> None:
    register = client.post(
        "/api/v1/auth/register",
        json={"email": "Owner@example.com", "password": "password12"},
    )
    assert register.status_code == 201
    token = register.json()["data"]["access_token"]
    assert register.json()["data"]["user"]["email"] == "owner@example.com"

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["data"]["role"] == "user"
    assert "password" not in me.json()["data"]
    assert "password_hash" not in me.json()["data"]


def test_invalid_and_expired_session_rejected(session: Session, client: TestClient) -> None:
    created = AuthService(session).register(credentials())
    invalid = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + ("x" * 40)})
    assert invalid.status_code == 401

    AuthService(session).logout(created.access_token)
    revoked = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {created.access_token}"},
    )
    assert revoked.status_code == 401
    assert revoked.json()["errorCode"] == "INVALID_SESSION"


def test_bootstrap_admin_email_applies_once(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.get_settings",
        lambda: Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql+psycopg://test:test@localhost:5432/test",
            cors_allowed_origins="http://localhost:3000",
            auth_bootstrap_admin_email="admin@example.com",
        ),
    )
    first = AuthService(session).register(credentials("admin@example.com"))
    second = AuthService(session).register(credentials("other@example.com"))
    assert first.user.role == "admin"
    assert second.user.role == "user"


def test_role_cannot_be_set_during_register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "hacker@example.com", "password": "password12", "role": "admin"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["user"]["role"] == "user"
