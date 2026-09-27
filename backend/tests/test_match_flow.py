from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.exceptions import DomainError
from app.models.domain import MatchJoinToken
from app.schemas.matches import AssignmentCreate, JerseyChange, MatchCreate
from app.services.matches import MatchService, hash_token


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


def match_payload(suffix: str = "") -> MatchCreate:
    start = datetime.now(UTC) + timedelta(hours=1)
    return MatchCreate(
        venue_name=f"Test venue {suffix}".strip(),
        starts_at=start,
        expected_ends_at=start + timedelta(hours=1),
        team_a_name=f"Home {suffix}".strip(),
        team_b_name=f"Away {suffix}".strip(),
    )


def test_match_creation_generates_secure_hashed_tokens(session: Session) -> None:
    created = MatchService(session).create_match(match_payload())

    assert created.match.teams[0].name == "Home"
    assert created.match.teams[1].name == "Away"
    assert len(created.join_token) >= 40
    assert len(created.organizer_token) >= 40
    stored = session.scalar(
        select(MatchJoinToken).where(MatchJoinToken.token_hash == hash_token(created.join_token))
    )
    assert stored is not None
    assert stored.token_hash != created.join_token


def test_invalid_join_token_is_rejected(session: Session) -> None:
    with pytest.raises(DomainError, match="Join link was not found") as raised:
        MatchService(session).get_join_context("x" * 40)

    assert raised.value.error_code == "JOIN_TOKEN_NOT_FOUND"


def test_revoked_and_expired_tokens_are_rejected(session: Session) -> None:
    service = MatchService(session)
    revoked_match = service.create_match(match_payload("revoked"))
    revoked = session.scalar(
        select(MatchJoinToken).where(
            MatchJoinToken.token_hash == hash_token(revoked_match.join_token)
        )
    )
    assert revoked is not None
    revoked.revoked_at = datetime.now(UTC)
    session.commit()

    with pytest.raises(DomainError) as revoked_error:
        service.get_join_context(revoked_match.join_token)
    assert revoked_error.value.error_code == "JOIN_TOKEN_REVOKED"

    expired_match = service.create_match(match_payload("expired"))
    expired = session.scalar(
        select(MatchJoinToken).where(
            MatchJoinToken.token_hash == hash_token(expired_match.join_token)
        )
    )
    assert expired is not None
    expired.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    session.commit()

    with pytest.raises(DomainError) as expired_error:
        service.get_join_context(expired_match.join_token)
    assert expired_error.value.error_code == "JOIN_TOKEN_EXPIRED"


def test_assignment_succeeds_and_rejects_team_outside_match(session: Session) -> None:
    service = MatchService(session)
    first = service.create_match(match_payload("one"))
    second = service.create_match(match_payload("two"))
    assignment = service.join_match(
        first.join_token,
        AssignmentCreate(
            team_id=first.match.teams[0].id,
            display_name="Test Player",
            jersey_number=7,
        ),
    )
    assert assignment.jersey_number == 7

    with pytest.raises(DomainError) as raised:
        service.join_match(
            first.join_token,
            AssignmentCreate(
                team_id=second.match.teams[0].id,
                display_name="Other Player",
                jersey_number=8,
            ),
        )
    assert raised.value.error_code == "TEAM_NOT_IN_MATCH"


def test_duplicate_active_jersey_is_rejected(session: Session) -> None:
    service = MatchService(session)
    created = service.create_match(match_payload())
    team_id = created.match.teams[0].id
    service.join_match(
        created.join_token,
        AssignmentCreate(team_id=team_id, display_name="First Player", jersey_number=3),
    )

    with pytest.raises(DomainError) as raised:
        service.join_match(
            created.join_token,
            AssignmentCreate(
                team_id=team_id,
                display_name="Second Player",
                jersey_number=3,
            ),
        )
    assert raised.value.error_code == "JERSEY_IN_USE"


def test_same_jersey_is_allowed_across_matches_and_teams(session: Session) -> None:
    service = MatchService(session)
    first = service.create_match(match_payload("one"))
    second = service.create_match(match_payload("two"))

    service.join_match(
        first.join_token,
        AssignmentCreate(
            team_id=first.match.teams[0].id,
            display_name="Home Player",
            jersey_number=9,
        ),
    )
    other_team = service.join_match(
        first.join_token,
        AssignmentCreate(
            team_id=first.match.teams[1].id,
            display_name="Away Player",
            jersey_number=9,
        ),
    )
    other_match = service.join_match(
        second.join_token,
        AssignmentCreate(
            team_id=second.match.teams[0].id,
            display_name="Other Match Player",
            jersey_number=9,
        ),
    )

    assert other_team.jersey_number == 9
    assert other_match.jersey_number == 9


def test_jersey_change_closes_old_assignment_and_preserves_history(
    session: Session,
) -> None:
    service = MatchService(session)
    created = service.create_match(match_payload())
    original = service.join_match(
        created.join_token,
        AssignmentCreate(
            team_id=created.match.teams[0].id,
            display_name="History Player",
            jersey_number=3,
        ),
    )
    effective_at = original.started_at + timedelta(minutes=20)
    replacement = service.change_jersey(
        created.match.id,
        original.id,
        created.organizer_token,
        JerseyChange(jersey_number=8, effective_at=effective_at),
    )
    history = service.list_assignments(created.match.id, created.organizer_token)

    assert replacement.jersey_number == 8
    assert replacement.started_at == effective_at
    assert replacement.supersedes_id == original.id
    assert len(history) == 2
    assert history[0].ended_at == effective_at
    assert history[0].jersey_number == 3
