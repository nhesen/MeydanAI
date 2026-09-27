from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.exceptions import DomainError
from app.models.domain import Highlight, Match, PlayerMatchAnalytics
from app.schemas.matches import AssignmentCreate, MatchCreate
from app.services.matches import MatchService
from app.services.platform import PlatformService


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


def create_match(
    session: Session,
    suffix: str,
    *,
    days: int = 1,
    completed: bool = False,
):
    start = datetime.now(UTC) + timedelta(days=days)
    created = MatchService(session).create_match(
        MatchCreate(
            title=f"Platform Match {suffix}",
            venue_name=f"Venue {suffix}",
            starts_at=start,
            expected_ends_at=start + timedelta(hours=1),
            team_a_name=f"Home {suffix}",
            team_b_name=f"Away {suffix}",
        )
    )
    if completed:
        match = session.get(Match, created.match.id)
        assert match is not None
        match.status = "completed"
        match.ended_at = start + timedelta(hours=1)
        match.home_score = 3
        match.away_score = 2
        session.commit()
    return created


def assign_player(session: Session, match, name: str, team_index: int = 0):
    return MatchService(session).join_match(
        match.join_token,
        AssignmentCreate(
            team_id=match.match.teams[team_index].id,
            display_name=name,
            jersey_number=7 + team_index,
        ),
    )


def test_match_list_filters_search_and_pagination(session: Session) -> None:
    first = create_match(session, "Alpha", days=-2)
    second = create_match(session, "Beta", days=2)
    service = PlatformService(session)

    searched = service.list_matches(
        query="Home Alpha",
        status=None,
        team_id=None,
        date_from=None,
        date_to=None,
        page=1,
        page_size=10,
    )
    filtered = service.list_matches(
        query=None,
        status="scheduled",
        team_id=second.match.teams[0].id,
        date_from=datetime.now(UTC).date(),
        date_to=None,
        page=1,
        page_size=1,
    )
    paged = service.list_matches(
        query=None,
        status=None,
        team_id=None,
        date_from=None,
        date_to=None,
        page=2,
        page_size=1,
    )

    assert searched.total == 1
    assert searched.items[0].match.id == first.match.id
    assert filtered.total == 1
    assert filtered.items[0].match.id == second.match.id
    assert paged.total == 2
    assert paged.total_pages == 2


def test_player_search_team_filter_and_team_counts(session: Session) -> None:
    match = create_match(session, "Directory")
    player = assign_player(session, match, "Searchable Player")
    assign_player(session, match, "Other Player", team_index=1)
    service = PlatformService(session)

    players = service.list_players(
        query="searchable",
        team_id=match.match.teams[0].id,
        page=1,
        page_size=20,
    )
    teams = service.list_teams(query="Home Directory", page=1, page_size=20)

    assert players.total == 1
    assert players.items[0].id == player.player.id
    assert teams.total == 1
    assert teams.items[0].player_count == 1
    assert teams.items[0].match_count == 1


def test_analytics_leaderboards_order_and_exclude_null_metrics(
    session: Session,
) -> None:
    match = create_match(session, "Analytics")
    first = assign_player(session, match, "First Ranked")
    second = assign_player(session, match, "Second Ranked", team_index=1)
    session.add_all(
        [
            PlayerMatchAnalytics(
                match_id=match.match.id,
                player_id=first.player.id,
                team_id=first.team.id,
                status="available",
                rating=8.6,
                distance_m=5200,
                max_speed_kmh=28.4,
                sprint_count=14,
            ),
            PlayerMatchAnalytics(
                match_id=match.match.id,
                player_id=second.player.id,
                team_id=second.team.id,
                status="available",
                rating=None,
                distance_m=4800,
                max_speed_kmh=29.2,
                sprint_count=10,
            ),
        ]
    )
    session.commit()

    analytics = PlatformService(session).analytics_leaderboards(
        team_id=None,
        date_from=None,
        date_to=None,
        minimum_matches=1,
    )

    assert [item.display_name for item in analytics.rating_leaders] == ["First Ranked"]
    assert [item.display_name for item in analytics.distance_leaders] == [
        "First Ranked",
        "Second Ranked",
    ]
    assert analytics.speed_leaders[0].display_name == "Second Ranked"


def test_highlight_filters_return_only_real_records(session: Session) -> None:
    match = create_match(session, "Highlights")
    player = assign_player(session, match, "Highlight Player")
    session.add_all(
        [
            Highlight(
                match_id=match.match.id,
                player_id=player.player.id,
                highlight_type="sprint",
                timestamp_ms=12000,
                title="Fast break",
            ),
            Highlight(
                match_id=match.match.id,
                highlight_type="manual",
                timestamp_ms=20000,
                title="Manual moment",
            ),
        ]
    )
    session.commit()

    highlights = PlatformService(session).list_highlights(
        match_id=match.match.id,
        player_id=player.player.id,
        highlight_type="sprint",
        page=1,
        page_size=10,
    )

    assert highlights.total == 1
    assert highlights.items[0].title == "Fast break"
    assert highlights.items[0].video_url is None


def test_invalid_date_filter_is_rejected(session: Session) -> None:
    today = datetime.now(UTC).date()
    with pytest.raises(DomainError) as raised:
        PlatformService(session).list_matches(
            query=None,
            status=None,
            team_id=None,
            date_from=today,
            date_to=today - timedelta(days=1),
            page=1,
            page_size=10,
        )
    assert raised.value.error_code == "INVALID_DATE_RANGE"


def test_match_listing_query_count_is_constant(session: Session) -> None:
    for index in range(5):
        create_match(session, f"Query {index}")
    statements = 0

    def count_statement(*_args) -> None:
        nonlocal statements
        statements += 1

    event.listen(session.bind, "before_cursor_execute", count_statement)
    try:
        PlatformService(session).list_matches(
            query=None,
            status=None,
            team_id=None,
            date_from=None,
            date_to=None,
            page=1,
            page_size=10,
        )
    finally:
        event.remove(session.bind, "before_cursor_execute", count_statement)

    assert statements <= 4
