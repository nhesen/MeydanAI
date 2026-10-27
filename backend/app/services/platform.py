import math
import uuid
from datetime import UTC, date, datetime
from typing import cast

from sqlalchemy.orm import Session

from app.core.analysis_metadata import analysis_quality, highlight_review_states
from app.core.analytics_bounds import MAX_PLAYER_KMH, clamp_speed, sanitize_player_metrics
from app.core.exceptions import DomainError
from app.models.domain import (
    Highlight,
    Match,
    Player,
    PlayerMatchAnalytics,
    Team,
)
from app.repositories.platform import PlatformRepository
from app.services.caption_stats import caption_involvement
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


def _event_counts(events: list[object]) -> tuple[int, int, int, int]:
    passes = accurate = tackles = interceptions = 0
    for event in events:
        kind = getattr(event, "event_type", None)
        if kind in {"successful_pass", "failed_pass"}:
            passes += 1
        if kind == "successful_pass":
            accurate += 1
        elif kind == "tackle":
            tackles += 1
        elif kind == "interception":
            interceptions += 1
    return passes, accurate, tackles, interceptions


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
                recent_performance=(contexts.get(player.id) or [None])[0],
            )
            for player in players
        ]
        return self._page(items, page=page, page_size=page_size, total=total)

    def get_player(self, player_id: uuid.UUID) -> GlobalPlayerProfile:
        player = self.repository.get_player(player_id)
        if player is None:
            raise self._not_found("Player was not found.", "PLAYER_NOT_FOUND")
        contexts = self._performance_contexts([player.id]).get(player.id, [])
        clips = self._caption_clips(player.id, [item.match_id for item in contexts])
        return GlobalPlayerProfile(
            id=player.id,
            display_name=player.display_name,
            is_temporary=player.is_temporary,
            recent_performances=contexts[:10],
            highlights=clips,
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
                    recent_performance=(contexts.get(player.id) or [None])[0],
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
                    value=PlatformService._leaderboard_value(index, float(cast(float, row[index]))),
                )
                for row in available[:10]
            ]

        def event_leaders(event_types: set[str]) -> list[LeaderboardEntry]:
            return [
                LeaderboardEntry(
                    player_id=row[0],
                    display_name=row[1],
                    match_count=row[2],
                    value=float(row[3]),
                )
                for row in self.repository.event_leader_rows(
                    event_types,
                    team_id=team_id,
                    date_from=date_from,
                    date_to=date_to,
                    minimum_matches=minimum_matches,
                )
            ]

        team_rows = self.repository.team_analytics_rows(
            date_from=date_from,
            date_to=date_to,
        )
        event_totals = self.repository.team_event_rows(
            date_from=date_from,
            date_to=date_to,
        )
        return AnalyticsLeaderboardsResponse(
            rating_leaders=leaders(3),
            distance_leaders=leaders(4),
            speed_leaders=leaders(5),
            sprint_leaders=leaders(6),
            pass_leaders=event_leaders({"successful_pass", "failed_pass"}),
            tackle_leaders=event_leaders({"tackle"}),
            interception_leaders=event_leaders({"interception"}),
            team_analytics=[
                TeamAnalyticsSummary(
                    team_id=row[0],
                    team_name=row[1],
                    match_count=row[2],
                    total_distance_m=row[3],
                    average_speed_kmh=clamp_speed(row[4], MAX_PLAYER_KMH)
                    if row[4] is not None
                    else None,
                    maximum_speed_kmh=clamp_speed(row[5]) if row[5] is not None else None,
                    sprint_count=row[6],
                    passes=event_totals.get(row[0], (None, None, None, None))[0],
                    accurate_passes=event_totals.get(row[0], (None, None, None, None))[1],
                    tackles=event_totals.get(row[0], (None, None, None, None))[2],
                    interceptions=event_totals.get(row[0], (None, None, None, None))[3],
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
        ranked_by_passes = not leaderboard.rating_leaders
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
            top_players=(leaderboard.pass_leaders if ranked_by_passes else leaderboard.rating_leaders)[:5],
            top_players_metric="passes" if ranked_by_passes else "rating",
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
            contexts[assignment.player_id].append(
                self._performance_summary(match, team, analytics, assignment.jersey_number)
            )
        self._apply_caption_scores(contexts)
        return contexts

    def _apply_caption_scores(
        self,
        contexts: dict[uuid.UUID, list[PlayerPerformanceSummary]],
    ) -> None:
        match_ids = {item.match_id for items in contexts.values() for item in items}
        board = caption_involvement(
            self.session,
            match_ids=match_ids,
            player_ids=list(contexts),
        )
        for player_id, items in contexts.items():
            for item in items:
                if item.match_id not in board.matches_with_captions:
                    continue
                item.goals = board.goals.get((player_id, item.match_id), 0)
                item.assists = board.assists.get((player_id, item.match_id), 0)

    def _caption_clips(
        self,
        player_id: uuid.UUID,
        match_ids: list[uuid.UUID],
    ) -> list[PlatformHighlightResponse]:
        board = caption_involvement(
            self.session,
            match_ids=set(match_ids),
            player_ids=[player_id],
        )
        clips = []
        for highlight in board.clips.get(player_id, []):
            match = self.session.get(Match, highlight.match_id)
            player = self.session.get(Player, highlight.player_id) if highlight.player_id else None
            if match is not None:
                clips.append(self._highlight_response(highlight, match, player))
        return clips

    def _performance_summary(
        self,
        match: Match,
        team: Team,
        analytics: PlayerMatchAnalytics | None,
        jersey_number: int | None = None,
    ) -> PlayerPerformanceSummary:
        if analytics is None:
            return PlayerPerformanceSummary(
                match_id=match.id,
                match_title=match.title,
                venue_name=match.venue_name,
                starts_at=match.starts_at,
                team=TeamResponse(id=team.id, name=team.name),
                jersey_number=jersey_number,
                rating=None,
                distance_m=None,
                avg_speed_kmh=None,
                max_speed_kmh=None,
                sprint_count=None,
                active_seconds=None,
            )
        counted = _event_counts(analytics.events)
        metrics = sanitize_player_metrics(
            rating=analytics.rating,
            distance_m=analytics.distance_m,
            avg_speed_kmh=analytics.avg_speed_kmh,
            max_speed_kmh=analytics.max_speed_kmh,
            sprint_count=analytics.sprint_count,
            active_seconds=analytics.active_seconds,
            activity_count=analytics.activity_count,
            peak_speed_at_ms=analytics.peak_speed_at_ms,
            calibrated=analysis_quality(self.session, match.id, analytics.player_id).calibrated,
        )
        return PlayerPerformanceSummary(
            match_id=match.id,
            match_title=match.title,
            venue_name=match.venue_name,
            starts_at=match.starts_at,
            team=TeamResponse(id=team.id, name=team.name),
            jersey_number=jersey_number,
            rating=metrics.rating,
            distance_m=metrics.distance_m,
            avg_speed_kmh=metrics.avg_speed_kmh,
            max_speed_kmh=metrics.max_speed_kmh,
            sprint_count=metrics.sprint_count,
            active_seconds=metrics.active_seconds,
            passes=counted[0],
            accurate_passes=counted[1],
            tackles=counted[2],
            interceptions=counted[3],
        )

    def _highlight_response(
        self,
        highlight: Highlight,
        match: Match,
        player: Player | None,
    ) -> PlatformHighlightResponse:
        states = highlight_review_states(self.session, match.id)
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
            review_status=states.get(
                highlight.id, "pending" if highlight.title.startswith("AI: ") else "confirmed"
            ),
        )

    @staticmethod
    def _leaderboard_value(index: int, raw: float) -> float:
        if index == 5:
            capped = clamp_speed(raw)
            return capped if capped is not None else raw
        return raw

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
