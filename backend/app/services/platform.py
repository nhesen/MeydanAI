import math
import uuid
from datetime import UTC, date, datetime
from typing import cast

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.domain import (
    Highlight,
    Match,
    Player,
    PlayerMatchAnalytics,
    Team,
)
from app.repositories.platform import PlatformRepository
from app.schemas.matches import TeamResponse
from app.schemas.platform import (
    AnalyticsLeaderboardsResponse,
    DashboardResponse,
    GlobalPlayerProfile,
    HighlightType,
    LeaderboardEntry,
    MatchListItem,
    PageResponse,
    PlatformHighlightResponse,
    PlayerDirectoryItem,
    PlayerPerformanceSummary,
    QuickStatsResponse,
    TeamAnalyticsSummary,
    TeamDetailResponse,
    TeamDirectoryItem,
)
from app.services.matches import MatchService


class PlatformService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = PlatformRepository(session)

    def list_matches(
        self,
        *,
        query: str | None,
        status: str | None,
        team_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        page: int,
        page_size: int,
    ) -> PageResponse[MatchListItem]:
        self._validate_dates(date_from, date_to)
        matches, total = self.repository.list_matches(
            query=query,
            status=status,
            team_id=team_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return self._page(
            self._match_items(matches),
            page=page,
            page_size=page_size,
            total=total,
        )

    def list_players(
        self,
        *,
        query: str | None,
        team_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> PageResponse[PlayerDirectoryItem]:
        players, total = self.repository.list_players(
            query=query,
            team_id=team_id,
            page=page,
            page_size=page_size,
        )
        contexts = self._performance_contexts([player.id for player in players])
        items = [
            PlayerDirectoryItem(
                id=player.id,
                display_name=player.display_name,
                is_temporary=player.is_temporary,
                recent_performance=contexts.get(player.id, [None])[0],
            )
            for player in players
        ]
        return self._page(items, page=page, page_size=page_size, total=total)

    def get_player(self, player_id: uuid.UUID) -> GlobalPlayerProfile:
        player = self.repository.get_player(player_id)
        if player is None:
            raise self._not_found("Player was not found.", "PLAYER_NOT_FOUND")
        contexts = self._performance_contexts([player.id]).get(player.id, [])
        return GlobalPlayerProfile(
            id=player.id,
            display_name=player.display_name,
            is_temporary=player.is_temporary,
            recent_performances=contexts[:10],
        )

    def list_teams(
        self,
        *,
        query: str | None,
        page: int,
        page_size: int,
    ) -> PageResponse[TeamDirectoryItem]:
        rows, total = self.repository.list_teams(
            query=query,
            page=page,
            page_size=page_size,
        )
        items = [
            TeamDirectoryItem(
                id=team.id,
                name=team.name,
                player_count=player_count,
                match_count=match_count,
            )
            for team, player_count, match_count in rows
        ]
        return self._page(items, page=page, page_size=page_size, total=total)

    def get_team(self, team_id: uuid.UUID) -> TeamDetailResponse:
        team_row = self.repository.get_team_counts(team_id)
        if team_row is None:
            raise self._not_found("Team was not found.", "TEAM_NOT_FOUND")
        team, player_count, match_count = team_row
        players = self.repository.list_team_players(team_id)
        contexts = self._performance_contexts([player.id for player in players])
        matches, _ = self.repository.list_matches(
            query=None,
            status=None,
            team_id=team_id,
            date_from=None,
            date_to=None,
            page=1,
            page_size=10,
        )
        return TeamDetailResponse(
            team=TeamDirectoryItem(
                id=team.id,
                name=team.name,
                player_count=player_count,
                match_count=match_count,
            ),
            players=[
                PlayerDirectoryItem(
                    id=player.id,
                    display_name=player.display_name,
                    is_temporary=player.is_temporary,
                    recent_performance=contexts.get(player.id, [None])[0],
                )
                for player in players
            ],
            recent_matches=self._match_items(matches),
        )

    def list_highlights(
        self,
        *,
        match_id: uuid.UUID | None,
        player_id: uuid.UUID | None,
        highlight_type: str | None,
        page: int,
        page_size: int,
    ) -> PageResponse[PlatformHighlightResponse]:
        rows, total = self.repository.list_highlights(
            match_id=match_id,
            player_id=player_id,
            highlight_type=highlight_type,
            page=page,
            page_size=page_size,
        )
        items = [
            self._highlight_response(highlight, match, player) for highlight, match, player in rows
        ]
        return self._page(items, page=page, page_size=page_size, total=total)

    def analytics_leaderboards(
        self,
        *,
        team_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        minimum_matches: int,
    ) -> AnalyticsLeaderboardsResponse:
        self._validate_dates(date_from, date_to)
        rows = self.repository.leaderboard_rows(
            team_id=team_id,
            date_from=date_from,
            date_to=date_to,
            minimum_matches=minimum_matches,
        )

        def leaders(index: int) -> list[LeaderboardEntry]:
            available = [row for row in rows if row[index] is not None]
            available.sort(key=lambda row: cast(float, row[index]), reverse=True)
            return [
                LeaderboardEntry(
                    player_id=row[0],
                    display_name=row[1],
                    match_count=row[2],
                    value=float(cast(float, row[index])),
                )
                for row in available[:10]
            ]

        team_rows = self.repository.team_analytics_rows(
            date_from=date_from,
            date_to=date_to,
        )
        return AnalyticsLeaderboardsResponse(
            rating_leaders=leaders(3),
            distance_leaders=leaders(4),
            speed_leaders=leaders(5),
            sprint_leaders=leaders(6),
            team_analytics=[
                TeamAnalyticsSummary(
                    team_id=row[0],
                    team_name=row[1],
                    match_count=row[2],
                    total_distance_m=row[3],
                    average_speed_kmh=row[4],
                    maximum_speed_kmh=row[5],
                    sprint_count=row[6],
                )
                for row in team_rows
            ],
            date_from=date_from,
            date_to=date_to,
        )

    def dashboard(self) -> DashboardResponse:
        total, completed, players, teams, processed = self.repository.quick_stats()
        today = datetime.now(UTC).date()
        recent, _ = self.repository.list_matches(
            query=None,
            status="completed",
            team_id=None,
            date_from=None,
            date_to=today,
            page=1,
            page_size=5,
        )
        upcoming, _ = self.repository.list_matches(
            query=None,
            status="scheduled",
            team_id=None,
            date_from=today,
            date_to=None,
            page=1,
            page_size=5,
            ascending=True,
        )
        processing, _ = self.repository.list_matches(
            query=None,
            status="processing",
            team_id=None,
            date_from=None,
            date_to=None,
            page=1,
            page_size=5,
        )
        highlights, _ = self.repository.list_highlights(
            match_id=None,
            player_id=None,
            highlight_type=None,
            page=1,
            page_size=4,
        )
        leaderboard = self.analytics_leaderboards(
            team_id=None,
            date_from=None,
            date_to=None,
            minimum_matches=1,
        )
        return DashboardResponse(
            quick_stats=QuickStatsResponse(
                total_matches=total,
                completed_matches=completed,
                total_players=players,
                total_teams=teams,
                processed_matches=processed,
            ),
            recent_matches=self._match_items(recent),
            upcoming_matches=self._match_items(upcoming),
            processing_matches=self._match_items(processing),
            top_players=leaderboard.rating_leaders[:5],
            latest_highlights=[
                self._highlight_response(highlight, match, player)
                for highlight, match, player in highlights
            ],
        )

    def _match_items(self, matches: list[Match]) -> list[MatchListItem]:
        analytics_ids = self.repository.analytics_match_ids([match.id for match in matches])
        return [
            MatchListItem(
                match=MatchService.to_match_response(match),
                has_analytics=match.id in analytics_ids,
            )
            for match in matches
        ]

    def _performance_contexts(
        self,
        player_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, list[PlayerPerformanceSummary]]:
        rows = self.repository.player_performance_rows(player_ids)
        contexts: dict[uuid.UUID, list[PlayerPerformanceSummary]] = {
            player_id: [] for player_id in player_ids
        }
        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for assignment, match, team, analytics in rows:
            key = (assignment.player_id, match.id)
            if key in seen:
                continue
            seen.add(key)
            contexts[assignment.player_id].append(self._performance_summary(match, team, analytics))
        return contexts

    @staticmethod
    def _performance_summary(
        match: Match,
        team: Team,
        analytics: PlayerMatchAnalytics | None,
    ) -> PlayerPerformanceSummary:
        return PlayerPerformanceSummary(
            match_id=match.id,
            match_title=match.title,
            venue_name=match.venue_name,
            starts_at=match.starts_at,
            team=TeamResponse(id=team.id, name=team.name),
            rating=analytics.rating if analytics else None,
            distance_m=analytics.distance_m if analytics else None,
            avg_speed_kmh=analytics.avg_speed_kmh if analytics else None,
            max_speed_kmh=analytics.max_speed_kmh if analytics else None,
            sprint_count=analytics.sprint_count if analytics else None,
            active_seconds=analytics.active_seconds if analytics else None,
        )

    @staticmethod
    def _highlight_response(
        highlight: Highlight,
        match: Match,
        player: Player | None,
    ) -> PlatformHighlightResponse:
        return PlatformHighlightResponse(
            id=highlight.id,
            match_id=match.id,
            match_title=match.title,
            player_id=player.id if player else None,
            player_name=player.display_name if player else None,
            highlight_type=cast(HighlightType, highlight.highlight_type),
            timestamp_ms=highlight.timestamp_ms,
            title=highlight.title,
            video_url=highlight.video_url,
            thumbnail_url=highlight.thumbnail_url,
            duration_ms=highlight.duration_ms,
            created_at=highlight.created_at,
        )

    @staticmethod
    def _page[T](
        items: list[T],
        *,
        page: int,
        page_size: int,
        total: int,
    ) -> PageResponse[T]:
        return PageResponse[T](
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    @staticmethod
    def _validate_dates(date_from: date | None, date_to: date | None) -> None:
        if date_from and date_to and date_from > date_to:
            raise DomainError(
                status=422,
                title="Invalid date range",
                detail="date_from must be before or equal to date_to.",
                error_code="INVALID_DATE_RANGE",
            )

    @staticmethod
    def _not_found(detail: str, code: str) -> DomainError:
        return DomainError(
            status=404,
            title="Resource not found",
            detail=detail,
            error_code=code,
        )
