from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base, get_db
from app.core.exceptions import DomainError
from app.main import create_app
from app.models.domain import ProcessingJob, User
from app.schemas.admin import HighlightWrite, UserRoleUpdate
from app.schemas.auth import AuthCredentials
from app.schemas.matches import MatchCreate, MatchStateUpdate
from app.services.admin import AdminService
from app.services.auth import AuthService
from app.services.matches import MatchService


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


def match_payload(suffix: str = "owned") -> MatchCreate:
    start = datetime.now(UTC) + timedelta(hours=1)
    return MatchCreate(
        venue_name=f"Venue {suffix}",
        starts_at=start,
        expected_ends_at=start + timedelta(hours=1),
        team_a_name=f"Home {suffix}",
        team_b_name=f"Away {suffix}",
    )


def register_user(session: Session, email: str, *, admin: bool = False) -> tuple[User, str]:
    created = AuthService(session).register(AuthCredentials(email=email, password="password12"))
    user = session.get(User, created.user.id)
    assert user is not None
    if admin:
        user.role = "admin"
        session.commit()
    return user, created.access_token


def test_owner_can_edit_match_and_other_user_cannot(session: Session) -> None:
    owner, _ = register_user(session, "owner@example.com")
    stranger, _ = register_user(session, "stranger@example.com")
    created = MatchService(session).create_match(
        match_payload(),
        organizer_user_id=owner.id,
    )
    service = MatchService(session)
    updated = service.update_match_state(
        created.match.id,
        None,
        MatchStateUpdate(status="live", home_score=1, away_score=0),
        owner,
    )
    assert updated.status == "live"

    with pytest.raises(DomainError) as raised:
        service.update_match_state(
            created.match.id,
            None,
            MatchStateUpdate(status="completed", home_score=1, away_score=0),
            stranger,
        )
    assert raised.value.status == 403


def test_legacy_organizer_token_still_authorizes(session: Session) -> None:
    created = MatchService(session).create_match(match_payload("legacy"))
    updated = MatchService(session).update_match_state(
        created.match.id,
        created.organizer_token,
        MatchStateUpdate(status="live", home_score=0, away_score=0),
    )
    assert updated.status == "live"


def test_admin_can_override_unowned_match(session: Session) -> None:
    admin, _ = register_user(session, "admin@example.com", admin=True)
    created = MatchService(session).create_match(match_payload("admin"))
    updated = MatchService(session).update_match_state(
        created.match.id,
        None,
        MatchStateUpdate(status="live", home_score=2, away_score=1),
        admin,
    )
    assert updated.home_score == 2


def test_unauthenticated_match_edit_is_rejected(session: Session) -> None:
    created = MatchService(session).create_match(match_payload("anon"))
    with pytest.raises(DomainError) as raised:
        MatchService(session).update_match_state(
            created.match.id,
            None,
            MatchStateUpdate(status="live", home_score=0, away_score=0),
        )
    assert raised.value.status == 401


def test_user_cannot_access_admin_and_admin_can(client: TestClient, session: Session) -> None:
    _, user_token = register_user(session, "member@example.com")
    _, admin_token = register_user(session, "root@example.com", admin=True)

    forbidden = client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden.status_code == 403

    allowed = client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    assert "total_users" in allowed.json()["data"]


def test_role_escalation_via_register_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "escalate@example.com", "password": "password12", "role": "admin"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["user"]["role"] == "user"


def test_user_cannot_change_own_role(client: TestClient, session: Session) -> None:
    user, token = register_user(session, "norole@example.com")
    response = client.patch(
        f"/api/v1/admin/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 403


def test_admin_role_change_and_last_admin_lockout(session: Session) -> None:
    admin, _ = register_user(session, "keeper@example.com", admin=True)
    member, _ = register_user(session, "promoted@example.com")
    service = AdminService(session)
    promoted = service.update_user_role(member.id, UserRoleUpdate(role="admin"))
    assert promoted.role == "admin"

    service.update_user_role(member.id, UserRoleUpdate(role="user"))
    with pytest.raises(DomainError) as raised:
        service.update_user_role(admin.id, UserRoleUpdate(role="user"))
    assert raised.value.error_code == "LAST_ADMIN_REQUIRED"


def test_admin_highlight_management_and_retry_permission(
    session: Session,
    client: TestClient,
) -> None:
    admin, admin_token = register_user(session, "ops@example.com", admin=True)
    created = MatchService(session).create_match(match_payload("clip"))
    highlight = AdminService(session).create_highlight(
        HighlightWrite(
            match_id=created.match.id,
            highlight_type="manual",
            timestamp_ms=12000,
            title="Opening run",
        )
    )
    listed = client.get(
        "/api/v1/admin/highlights",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1

    job = ProcessingJob(
        match_id=created.match.id,
        status="failed",
        stage="validating",
        progress=10,
        source_type="uploaded_video",
        source_reference="abc.mp4",
        source_media_type="video/mp4",
        source_size_bytes=1024,
        provider="external",
        error_code="PROCESSING_FAILED",
    )
    session.add(job)
    session.commit()
    retried = AdminService(session).retry_job(job.id, admin)
    assert retried.status.value == "queued"
    assert highlight.title == "Opening run"
