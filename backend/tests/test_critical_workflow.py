import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base, get_db
from app.main import create_app
from app.models.domain import PlayerMatchAnalytics, User


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


def test_authenticated_match_join_and_public_analytics_flow(
    client: TestClient,
    session: Session,
) -> None:
    register = client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert register.status_code == 201
    token = register.json()["data"]["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    start = datetime.now(UTC) + timedelta(hours=1)
    created = client.post(
        "/api/v1/matches",
        headers=auth,
        json={
            "venue_name": "Final Pitch",
            "starts_at": start.isoformat(),
            "expected_ends_at": (start + timedelta(hours=1)).isoformat(),
            "title": "QA Cup",
            "team_a_name": "Red",
            "team_b_name": "Blue",
        },
    )
    assert created.status_code == 201
    match = created.json()["data"]["match"]
    join_token = created.json()["data"]["join_token"]
    match_id = match["id"]
    home_id = match["teams"][0]["id"]

    public_dashboard = client.get("/api/v1/public/dashboard")
    assert public_dashboard.status_code == 200
    assert "Authorization" not in public_dashboard.request.headers

    join = client.get(f"/api/v1/join/{join_token}")
    assert join.status_code == 200
    assignment = client.post(
        f"/api/v1/join/{join_token}/assignments",
        json={"team_id": home_id, "display_name": "QA Player", "jersey_number": 3},
    )
    assert assignment.status_code == 201
    player_id = assignment.json()["data"]["player"]["id"]

    other_match = client.post(
        "/api/v1/matches",
        json={
            "venue_name": "Second Pitch",
            "starts_at": (start + timedelta(days=1)).isoformat(),
            "expected_ends_at": (start + timedelta(days=1, hours=1)).isoformat(),
            "team_a_name": "Red",
            "team_b_name": "Green",
        },
    )
    other_join = other_match.json()["data"]["join_token"]
    other_home = other_match.json()["data"]["match"]["teams"][0]["id"]
    other_assignment = client.post(
        f"/api/v1/join/{other_join}/assignments",
        json={"team_id": other_home, "display_name": "Other Player", "jersey_number": 3},
    )
    assert other_assignment.status_code == 201
    assert other_assignment.json()["data"]["player"]["id"] != player_id

    detail = client.get(f"/api/v1/public/matches/{match_id}")
    assert detail.status_code == 200
    players = detail.json()["data"]["players"]
    assert players[0]["current_jersey"] == 3
    assert players[0]["rating"] is None

    updated = client.patch(
        f"/api/v1/matches/{match_id}",
        headers=auth,
        json={"status": "live", "home_score": 2, "away_score": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["home_score"] == 2

    session.add(
        PlayerMatchAnalytics(
            match_id=uuid.UUID(match_id),
            player_id=uuid.UUID(player_id),
            team_id=uuid.UUID(home_id),
            status="available",
            rating=7.5,
            distance_m=4100,
        )
    )
    session.commit()

    analytics = client.get(f"/api/v1/public/matches/{match_id}/players/{player_id}/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["data"]["player"]["rating"] == 7.5
    assert "position_samples" in analytics.json()["data"]

    listing = client.get("/api/v1/public/matches")
    assert listing.status_code == 200
    assert "position_samples" not in listing.text

    forbidden = client.get("/api/v1/admin/dashboard", headers=auth)
    assert forbidden.status_code == 403

    user = session.get(User, uuid.UUID(register.json()["data"]["user"]["id"]))
    assert user is not None
    user.role = "admin"
    session.commit()
    allowed = client.get("/api/v1/admin/dashboard", headers=auth)
    assert allowed.status_code == 200
    assert allowed.json()["data"]["total_matches"] >= 2


def test_public_directories_remain_unauthenticated(client: TestClient) -> None:
    for path in (
        "/api/v1/public/dashboard",
        "/api/v1/public/matches",
        "/api/v1/public/players",
        "/api/v1/public/teams",
        "/api/v1/public/analytics/leaderboards",
        "/api/v1/public/highlights",
        "/api/v1/health",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
