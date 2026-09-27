import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.exceptions import DomainError
from app.models.domain import (
    MatchJoinToken,
    PlayerAnalyticsEvent,
    PlayerIntensityBucket,
    PlayerMatchAnalytics,
    PlayerPositionSample,
)
from app.schemas.matches import (
    AssignmentCreate,
    IntensityBucketResponse,
    JerseyChange,
    MatchCreate,
    MatchStateUpdate,
    PositionSampleResponse,
)
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


def test_public_match_detail_preserves_relationships_and_missing_metrics(
    session: Session,
) -> None:
    service = MatchService(session)
    created = service.create_match(match_payload())
    assignment = service.join_match(
        created.join_token,
        AssignmentCreate(
            team_id=created.match.teams[0].id,
            display_name="Detail Player",
            jersey_number=11,
        ),
    )

    detail = service.get_public_match_detail(created.match.id)

    assert detail.match.home_score is None
    assert detail.match.away_score is None
    assert detail.team_stats is None
    assert detail.highlights == []
    assert detail.players[0].id == assignment.player.id
    assert detail.players[0].team.id == created.match.teams[0].id
    assert detail.players[0].rating is None
    assert detail.players[0].jersey_history[0].jersey_number == 11


def test_missing_public_match_detail_returns_404(session: Session) -> None:
    with pytest.raises(DomainError) as raised:
        MatchService(session).get_public_match_detail(uuid.uuid4())

    assert raised.value.status == 404
    assert raised.value.error_code == "MATCH_NOT_FOUND"


def test_organizer_can_update_score_and_match_status(session: Session) -> None:
    service = MatchService(session)
    created = service.create_match(match_payload())
    updated = service.update_match_state(
        created.match.id,
        created.organizer_token,
        MatchStateUpdate(status="live", home_score=2, away_score=1),
    )

    assert updated.status == "live"
    assert updated.home_score == 2
    assert updated.away_score == 1


def test_player_analytics_detail_returns_persisted_data(session: Session) -> None:
    service = MatchService(session)
    created = service.create_match(match_payload())
    assignment = service.join_match(
        created.join_token,
        AssignmentCreate(
            team_id=created.match.teams[0].id,
            display_name="Analytics Player",
            jersey_number=10,
        ),
    )
    analytics = PlayerMatchAnalytics(
        match_id=created.match.id,
        player_id=assignment.player.id,
        team_id=assignment.team.id,
        status="available",
        rating=8.4,
        distance_m=4820,
        avg_speed_kmh=11.9,
        max_speed_kmh=27.6,
        sprint_count=14,
        active_seconds=3136,
        activity_count=92,
        peak_speed_at_ms=2052000,
    )
    analytics.position_samples = [PlayerPositionSample(timestamp_ms=1000, x=0.42, y=0.68)]
    analytics.intensity_buckets = [PlayerIntensityBucket(from_minute=0, to_minute=5, intensity=42)]
    analytics.events = [
        PlayerAnalyticsEvent(
            event_type="sprint",
            timestamp_ms=752000,
            speed_kmh=24.8,
            title="Sprint",
        )
    ]
    session.add(analytics)
    session.commit()

    detail = service.get_player_analytics_detail(
        created.match.id,
        assignment.player.id,
    )

    assert detail.player.analytics_status == "available"
    assert detail.player.rating == 8.4
    assert detail.player.distance_m == 4820
    assert detail.position_samples[0].x == 0.42
    assert detail.intensity_buckets[0].to_minute == 5
    assert detail.events[0].speed_kmh == 24.8


def test_inflated_motion_analytics_are_clamped_for_display(session: Session) -> None:
    service = MatchService(session)
    start = datetime.now(UTC) + timedelta(hours=1)
    created = service.create_match(
        MatchCreate(
            venue_name="Clamp venue",
            starts_at=start,
            expected_ends_at=start + timedelta(hours=1),
            team_a_name="Home",
            team_b_name="Away",
        )
    )
    assignment = service.join_match(
        created.join_token,
        AssignmentCreate(
            team_id=created.match.teams[0].id,
            display_name="Detected away 1",
            jersey_number=1,
        ),
    )
    analytics = PlayerMatchAnalytics(
        match_id=created.match.id,
        player_id=assignment.player.id,
        team_id=assignment.team.id,
        status="available",
        rating=6.6,
        distance_m=284,
        avg_speed_kmh=18.7,
        max_speed_kmh=198.0,
        sprint_count=51,
        active_seconds=53,
        activity_count=223,
        peak_speed_at_ms=48000,
    )
    analytics.position_samples = [
        PlayerPositionSample(timestamp_ms=0, x=0.20, y=0.50),
        PlayerPositionSample(timestamp_ms=250, x=0.21, y=0.50),
        PlayerPositionSample(timestamp_ms=500, x=0.80, y=0.50),
    ]
    analytics.intensity_buckets = [PlayerIntensityBucket(from_minute=0, to_minute=1, intensity=100)]
    analytics.events = [
        PlayerAnalyticsEvent(
            event_type="sprint",
            timestamp_ms=6000,
            speed_kmh=26.1,
            title="Sprint",
        ),
        PlayerAnalyticsEvent(
            event_type="sprint",
            timestamp_ms=10000,
            speed_kmh=106.9,
            title="Sprint",
        ),
        PlayerAnalyticsEvent(
            event_type="peak_speed",
            timestamp_ms=48000,
            speed_kmh=198.0,
            title="Peak recorded speed",
        ),
    ]
    session.add(analytics)
    session.commit()

    detail = service.get_player_analytics_detail(created.match.id, assignment.player.id)
    assert detail.player.max_speed_kmh == 36.0
    assert detail.player.avg_speed_kmh == 12.0
    assert detail.player.sprint_count is not None and detail.player.sprint_count <= 4
    assert detail.player.distance_m is not None and detail.player.distance_m <= 177
    assert all(event.speed_kmh is None or event.speed_kmh <= 36 for event in detail.events)
    assert all(
        event.event_type != "sprint" or (event.speed_kmh or 0) <= 40 for event in detail.events
    )
    xs = [sample.x for sample in detail.position_samples]
    assert len(detail.position_samples) >= 8
    assert max(xs) - min(xs) > 0.3
    assert 10 <= detail.intensity_buckets[0].intensity < 100


def test_player_analytics_rejects_player_not_in_match(session: Session) -> None:
    service = MatchService(session)
    first = service.create_match(match_payload("first"))
    second = service.create_match(match_payload("second"))
    outsider = service.join_match(
        second.join_token,
        AssignmentCreate(
            team_id=second.match.teams[0].id,
            display_name="Other Match Player",
            jersey_number=4,
        ),
    )

    with pytest.raises(DomainError) as raised:
        service.get_player_analytics_detail(first.match.id, outsider.player.id)

    assert raised.value.error_code == "PLAYER_NOT_IN_MATCH"


def test_player_analytics_preserves_null_metrics_and_empty_samples(
    session: Session,
) -> None:
    service = MatchService(session)
    created = service.create_match(match_payload())
    assignment = service.join_match(
        created.join_token,
        AssignmentCreate(
            team_id=created.match.teams[0].id,
            display_name="Nullable Player",
            jersey_number=2,
        ),
    )
    session.add(
        PlayerMatchAnalytics(
            match_id=created.match.id,
            player_id=assignment.player.id,
            team_id=assignment.team.id,
            status="unavailable",
        )
    )
    session.commit()

    detail = service.get_player_analytics_detail(
        created.match.id,
        assignment.player.id,
    )

    assert detail.player.distance_m is None
    assert detail.player.sprint_count is None
    assert detail.position_samples == []
    assert detail.intensity_buckets == []


def test_position_and_intensity_contract_validation() -> None:
    with pytest.raises(ValidationError):
        PositionSampleResponse(timestamp_ms=10, x=1.1, y=0.5)
    with pytest.raises(ValidationError):
        PositionSampleResponse(timestamp_ms=10, x=0.5, y=-0.1)
    with pytest.raises(ValidationError):
        IntensityBucketResponse(from_minute=5, to_minute=5, intensity=42)
    with pytest.raises(ValidationError):
        IntensityBucketResponse(from_minute=0, to_minute=5, intensity=101)


def test_player_analytics_keeps_jersey_history(session: Session) -> None:
    service = MatchService(session)
    created = service.create_match(match_payload())
    original = service.join_match(
        created.join_token,
        AssignmentCreate(
            team_id=created.match.teams[0].id,
            display_name="Changing Player",
            jersey_number=3,
        ),
    )
    service.change_jersey(
        created.match.id,
        original.id,
        created.organizer_token,
        JerseyChange(
            jersey_number=8,
            effective_at=original.started_at + timedelta(minutes=10),
        ),
    )

    detail = service.get_player_analytics_detail(
        created.match.id,
        original.player.id,
    )

    assert detail.player.current_jersey == 8
    assert [item.jersey_number for item in detail.player.jersey_history] == [3, 8]


def test_player_comparison_requires_two_players_from_same_match(
    session: Session,
) -> None:
    service = MatchService(session)
    first = service.create_match(match_payload("first"))
    second = service.create_match(match_payload("second"))
    left = service.join_match(
        first.join_token,
        AssignmentCreate(
            team_id=first.match.teams[0].id,
            display_name="Left Player",
            jersey_number=5,
        ),
    )
    right = service.join_match(
        first.join_token,
        AssignmentCreate(
            team_id=first.match.teams[1].id,
            display_name="Right Player",
            jersey_number=6,
        ),
    )
    outsider = service.join_match(
        second.join_token,
        AssignmentCreate(
            team_id=second.match.teams[0].id,
            display_name="Outsider",
            jersey_number=7,
        ),
    )

    comparison = service.compare_players(
        first.match.id,
        left.player.id,
        right.player.id,
    )
    assert comparison.left.id == left.player.id
    assert comparison.right.id == right.player.id

    with pytest.raises(DomainError) as raised:
        service.compare_players(
            first.match.id,
            left.player.id,
            outsider.player.id,
        )
    assert raised.value.error_code == "COMPARISON_PLAYER_NOT_IN_MATCH"
