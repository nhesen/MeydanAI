import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.analytics_bounds import (
    MAX_PLAUSIBLE_STEP_KMH,
    SPRINT_KMH,
    intensity_from_positions,
    reconstruct_display_path,
    sanitize_events,
    sanitize_intensity,
    sanitize_player_metrics,
)
from app.core.exceptions import DomainError
from app.core.security import access_denied, authentication_required, is_admin, owns_match
from app.core.tokens import aware, create_token, hash_token
from app.models.domain import (
    JerseyAssignment,
    Match,
    MatchJoinToken,
    MatchTeam,
    Player,
    PlayerMatchAnalytics,
    Team,
    User,
)
from app.repositories.matches import MatchRepository
from app.schemas.matches import (
    AnalyticsStatus,
    AssignmentCorrection,
    AssignmentCreate,
    AssignmentResponse,
    HighlightResponse,
    IntensityBucketResponse,
    JerseyChange,
    JerseyHistoryResponse,
    JoinContextResponse,
    MatchCreate,
    MatchCreatedResponse,
    MatchDetailResponse,
    MatchPlayerResponse,
    MatchResponse,
    MatchStateUpdate,
    PlayerAnalyticsDetailResponse,
    PlayerAnalyticsEventResponse,
    PlayerComparisonResponse,
    PlayerResponse,
    PositionSampleResponse,
    TeamResponse,
    TimelineEventResponse,
)
from app.services.audit import AuditService


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


class MatchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = MatchRepository(session)

    def create_match(
        self,
        payload: MatchCreate,
        *,
        organizer_user_id: uuid.UUID | None = None,
    ) -> MatchCreatedResponse:
        organizer_token = create_token()
        join_token = create_token()
        match = Match(
            title=payload.title.strip() if payload.title else None,
            venue_name=payload.venue_name.strip(),
            starts_at=payload.starts_at,
            expected_ends_at=payload.expected_ends_at,
            organizer_token_hash=hash_token(organizer_token),
            organizer_user_id=organizer_user_id,
        )
        team_a = Team(name=payload.team_a_name.strip())
        team_b = Team(name=payload.team_b_name.strip())
        match.teams = [
            MatchTeam(team=team_a, side="home"),
            MatchTeam(team=team_b, side="away"),
        ]
        join_record = MatchJoinToken(
            match=match,
            token_hash=hash_token(join_token),
            expires_at=payload.join_expires_at,
        )
        self.session.add_all([match, join_record])
        self.session.commit()
        stored = self._require_match(match.id)
        return MatchCreatedResponse(
            match=self.to_match_response(stored),
            join_token=join_token,
            organizer_token=organizer_token,
        )

    def authorize_match(
        self,
        match_id: uuid.UUID,
        *,
        organizer_token: str | None = None,
        user: User | None = None,
    ) -> Match:
        match = self._require_match(match_id)
        if is_admin(user) or owns_match(user, match.organizer_user_id):
            return match
        if organizer_token:
            self._validate_organizer(match, organizer_token)
            return match
        if user is not None:
            raise access_denied("You do not manage this match.")
        raise authentication_required()

    def get_organizer_match(
        self,
        match_id: uuid.UUID,
        organizer_token: str | None = None,
        user: User | None = None,
    ) -> Match:
        return self.authorize_match(
            match_id,
            organizer_token=organizer_token,
            user=user,
        )

    def get_public_match_detail(self, match_id: uuid.UUID) -> MatchDetailResponse:
        match = self._require_match(match_id)
        assignments = self.repository.list_assignments(match_id)
        analytics_by_player = {
            analytics.player_id: analytics
            for analytics in self.repository.list_player_analytics(match_id)
        }
        players: dict[uuid.UUID, MatchPlayerResponse] = {}
        assignment_by_id = {assignment.id: assignment for assignment in assignments}
        events: list[TimelineEventResponse] = []

        for assignment in assignments:
            history_item = JerseyHistoryResponse(
                assignment_id=assignment.id,
                jersey_number=assignment.jersey_number,
                started_at=aware(assignment.started_at),
                ended_at=aware(assignment.ended_at) if assignment.ended_at else None,
            )
            existing = players.get(assignment.player_id)
            if existing is None:
                existing = MatchPlayerResponse(
                    id=assignment.player.id,
                    display_name=assignment.player.display_name,
                    team=TeamResponse(
                        id=assignment.team.id,
                        name=assignment.team.name,
                    ),
                    current_jersey=None,
                    jersey_history=[],
                )
                players[assignment.player_id] = existing
            existing.jersey_history.append(history_item)
            if assignment.ended_at is None:
                existing.current_jersey = assignment.jersey_number

            if assignment.supersedes_id is not None:
                previous = assignment_by_id.get(assignment.supersedes_id)
                previous_number = previous.jersey_number if previous else None
                minute = max(
                    0,
                    int(
                        (aware(assignment.started_at) - aware(match.starts_at)).total_seconds()
                        // 60
                    ),
                )
                events.append(
                    TimelineEventResponse(
                        id=f"jersey-{assignment.id}",
                        event_type="jersey_change",
                        occurred_at=aware(assignment.started_at),
                        minute=minute,
                        title="Jersey changed",
                        description=(
                            f"{assignment.player.display_name}: "
                            f"#{previous_number} to #{assignment.jersey_number}"
                            if previous_number is not None
                            else f"{assignment.player.display_name}: #{assignment.jersey_number}"
                        ),
                        player_id=assignment.player_id,
                        team_id=assignment.team_id,
                    )
                )

        for player in players.values():
            player.jersey_history.sort(key=lambda item: item.started_at)
            if player.current_jersey is None and player.jersey_history:
                player.current_jersey = player.jersey_history[-1].jersey_number
            analytics = analytics_by_player.get(player.id)
            if analytics is not None and analytics.team_id == player.team.id:
                self._apply_analytics(player, analytics)
            elif match.status == "processing":
                player.analytics_status = "processing"

        return MatchDetailResponse(
            match=self.to_match_response(match),
            players=sorted(players.values(), key=lambda item: item.display_name.casefold()),
            team_stats=None,
            events=sorted(events, key=lambda item: item.occurred_at),
            highlights=[
                HighlightResponse(
                    id=highlight.id,
                    highlight_type=highlight.highlight_type,
                    title=highlight.title,
                    video_url=highlight.video_url,
                    thumbnail_url=highlight.thumbnail_url,
                    duration_seconds=(
                        highlight.duration_ms // 1000 if highlight.duration_ms is not None else None
                    ),
                    occurred_at=aware(match.starts_at)
                    + timedelta(milliseconds=highlight.timestamp_ms),
                    player_id=highlight.player_id,
                )
                for highlight in self.repository.list_highlights(match_id)
            ],
        )

    def get_player_analytics_detail(
        self,
        match_id: uuid.UUID,
        player_id: uuid.UUID,
    ) -> PlayerAnalyticsDetailResponse:
        detail = self.get_public_match_detail(match_id)
        player = next((item for item in detail.players if item.id == player_id), None)
        if player is None:
            raise self._not_found(
                "Player is not assigned to this match.",
                "PLAYER_NOT_IN_MATCH",
            )
        analytics = self.repository.get_player_analytics(match_id, player_id)
        if analytics is None:
            return PlayerAnalyticsDetailResponse(
                match=detail.match,
                player=player,
                position_samples=[],
                intensity_buckets=[],
                events=[],
            )
        events = sanitize_events(
            [
                PlayerAnalyticsEventResponse(
                    id=event.id,
                    event_type=cast(
                        Literal[
                            "sprint",
                            "peak_speed",
                            "high_intensity_period",
                            "custom",
                        ],
                        event.event_type,
                    ),
                    timestamp_ms=event.timestamp_ms,
                    speed_kmh=event.speed_kmh,
                    title=event.title,
                )
                for event in analytics.events
            ]
        )
        position_samples = reconstruct_display_path(
            [
                PositionSampleResponse(
                    timestamp_ms=sample.timestamp_ms,
                    x=sample.x,
                    y=sample.y,
                )
                for sample in analytics.position_samples
            ]
        )
        rebuilt_intensity = intensity_from_positions(position_samples)
        if rebuilt_intensity:
            intensity_buckets = [
                IntensityBucketResponse(
                    from_minute=from_minute,
                    to_minute=to_minute,
                    intensity=intensity,
                )
                for from_minute, to_minute, intensity in rebuilt_intensity
            ]
        else:
            intensity_buckets = sanitize_intensity(
                [
                    IntensityBucketResponse(
                        from_minute=bucket.from_minute,
                        to_minute=bucket.to_minute,
                        intensity=bucket.intensity,
                    )
                    for bucket in analytics.intensity_buckets
                ],
                raw_max_speed_kmh=analytics.max_speed_kmh,
            )
        return PlayerAnalyticsDetailResponse(
            match=detail.match,
            player=player,
            position_samples=position_samples,
            intensity_buckets=intensity_buckets,
            events=events,
        )

    def compare_players(
        self,
        match_id: uuid.UUID,
        left_player_id: uuid.UUID,
        right_player_id: uuid.UUID,
    ) -> PlayerComparisonResponse:
        if left_player_id == right_player_id:
            raise self._conflict(
                "Select two different players.",
                "COMPARISON_PLAYERS_MUST_DIFFER",
            )
        detail = self.get_public_match_detail(match_id)
        players = {player.id: player for player in detail.players}
        left = players.get(left_player_id)
        right = players.get(right_player_id)
        if left is None or right is None:
            raise self._not_found(
                "Both comparison players must belong to this match.",
                "COMPARISON_PLAYER_NOT_IN_MATCH",
            )
        return PlayerComparisonResponse(left=left, right=right)

    def update_match_state(
        self,
        match_id: uuid.UUID,
        organizer_token: str | None,
        payload: MatchStateUpdate,
        user: User | None = None,
    ) -> MatchResponse:
        match = self.get_organizer_match(match_id, organizer_token, user)
        match.status = payload.status
        match.home_score = payload.home_score
        match.away_score = payload.away_score
        match.ended_at = (
            payload.ended_at
            if payload.ended_at is not None
            else datetime.now(UTC)
            if payload.status == "completed"
            else None
        )
        if match.ended_at is not None and aware(match.ended_at) <= aware(match.starts_at):
            raise DomainError(
                status=422,
                title="Invalid match time",
                detail="Match end time must be after the start time.",
                error_code="INVALID_MATCH_END_TIME",
            )
        AuditService(self.session).record(
            actor_user_id=user.id if user is not None else None,
            action="match.update",
            entity_type="match",
            entity_id=str(match.id),
            metadata={"status": payload.status, "via_token": organizer_token is not None},
        )
        self.session.commit()
        return self.to_match_response(self._require_match(match.id))

    def rotate_join_token(
        self,
        match_id: uuid.UUID,
        organizer_token: str | None,
        expires_at: datetime | None,
        user: User | None = None,
    ) -> tuple[str, datetime | None]:
        match = self.get_organizer_match(match_id, organizer_token, user)
        now = datetime.now(UTC)
        self.session.execute(
            update(MatchJoinToken)
            .where(
                MatchJoinToken.match_id == match.id,
                MatchJoinToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        token = create_token()
        self.session.add(
            MatchJoinToken(
                match_id=match.id,
                token_hash=hash_token(token),
                expires_at=expires_at,
            )
        )
        self.session.commit()
        return token, expires_at

    def get_join_context(self, token: str) -> JoinContextResponse:
        join_record = self._require_valid_join_token(token)
        return JoinContextResponse(
            match=self.to_match_response(join_record.match),
            players=[
                PlayerResponse.model_validate(player) for player in self.repository.list_players()
            ],
        )

    def join_match(self, token: str, payload: AssignmentCreate) -> AssignmentResponse:
        join_record = self._require_valid_join_token(token)
        match = join_record.match
        self._require_match_team(match.id, payload.team_id, for_update=True)

        if payload.player_id is not None:
            player = self.repository.get_player(payload.player_id)
            if player is None:
                raise self._not_found("Player was not found.", "PLAYER_NOT_FOUND")
        else:
            assert payload.display_name is not None
            cleaned_name = " ".join(payload.display_name.strip().split())
            player = Player(
                display_name=cleaned_name,
                normalized_name=normalize_name(cleaned_name),
                is_temporary=True,
            )
            self.repository.add(player)
            self.repository.flush()

        active = self.repository.find_active_player_assignment(match.id, player.id)
        if active is not None:
            raise self._conflict(
                "This player is already assigned in the match.",
                "PLAYER_ALREADY_ASSIGNED",
            )

        started_at = max(datetime.now(UTC), aware(match.starts_at))
        self._ensure_jersey_available(match.id, payload.team_id, payload.jersey_number, started_at)
        assignment = JerseyAssignment(
            match_id=match.id,
            team_id=payload.team_id,
            player_id=player.id,
            jersey_number=payload.jersey_number,
            started_at=started_at,
        )
        self.repository.add(assignment)
        self._commit_assignment()
        return self.to_assignment_response(self._require_assignment(assignment.id))

    def list_assignments(
        self,
        match_id: uuid.UUID,
        organizer_token: str | None,
        user: User | None = None,
    ) -> list[AssignmentResponse]:
        self.get_organizer_match(match_id, organizer_token, user)
        return [
            self.to_assignment_response(item) for item in self.repository.list_assignments(match_id)
        ]

    def correct_assignment(
        self,
        match_id: uuid.UUID,
        assignment_id: uuid.UUID,
        organizer_token: str | None,
        payload: AssignmentCorrection,
        user: User | None = None,
    ) -> AssignmentResponse:
        self.get_organizer_match(match_id, organizer_token, user)
        assignment = self._require_assignment(assignment_id, match_id)
        if assignment.ended_at is not None:
            raise self._conflict("Assignment is already closed.", "ASSIGNMENT_CLOSED")
        effective_at = payload.effective_at or datetime.now(UTC)
        self._validate_effective_time(assignment, effective_at)
        assignment.ended_at = effective_at
        assignment.closed_reason = "admin_correction"
        if payload.close_only:
            self.session.commit()
            return self.to_assignment_response(self._require_assignment(assignment.id))

        team_id = payload.team_id or assignment.team_id
        jersey_number = (
            payload.jersey_number if payload.jersey_number is not None else assignment.jersey_number
        )
        self._require_match_team(match_id, team_id, for_update=True)
        if not payload.override_conflict:
            self._ensure_jersey_available(match_id, team_id, jersey_number, effective_at)
        replacement = JerseyAssignment(
            match_id=match_id,
            team_id=team_id,
            player_id=assignment.player_id,
            jersey_number=jersey_number,
            started_at=effective_at,
            supersedes_id=assignment.id,
            conflict_override=payload.override_conflict,
            override_actor=payload.override_actor,
            override_reason=payload.override_reason,
            override_at=effective_at if payload.override_conflict else None,
        )
        self.repository.add(replacement)
        AuditService(self.session).record(
            actor_user_id=user.id if user is not None else None,
            action="assignment.correct",
            entity_type="jersey_assignment",
            entity_id=str(assignment.id),
            metadata={
                "override": payload.override_conflict,
                "reason": payload.override_reason,
                "actor_label": payload.override_actor,
            },
        )
        self._commit_assignment()
        return self.to_assignment_response(self._require_assignment(replacement.id))

    def change_jersey(
        self,
        match_id: uuid.UUID,
        assignment_id: uuid.UUID,
        organizer_token: str | None,
        payload: JerseyChange,
        user: User | None = None,
    ) -> AssignmentResponse:
        correction = AssignmentCorrection(
            jersey_number=payload.jersey_number,
            effective_at=payload.effective_at,
            override_conflict=payload.override_conflict,
            override_reason=payload.override_reason,
            override_actor=payload.override_actor,
        )
        return self.correct_assignment(match_id, assignment_id, organizer_token, correction, user)

    def _require_valid_join_token(self, token: str) -> MatchJoinToken:
        if len(token) < 32 or len(token) > 200:
            raise self._not_found("Join link was not found.", "JOIN_TOKEN_NOT_FOUND")
        record = self.repository.get_join_token(hash_token(token))
        if record is None:
            raise self._not_found("Join link was not found.", "JOIN_TOKEN_NOT_FOUND")
        now = datetime.now(UTC)
        if record.revoked_at is not None:
            raise self._gone("This join link has been revoked.", "JOIN_TOKEN_REVOKED")
        if record.expires_at is not None and aware(record.expires_at) <= now:
            raise self._gone("This join link has expired.", "JOIN_TOKEN_EXPIRED")
        if record.match.status in {"processing", "completed", "failed", "cancelled"}:
            raise self._gone("This match is no longer open.", "MATCH_CLOSED")
        return record

    def _require_match(self, match_id: uuid.UUID) -> Match:
        match = self.repository.get_match(match_id)
        if match is None:
            raise self._not_found("Match was not found.", "MATCH_NOT_FOUND")
        return match

    def _require_assignment(
        self, assignment_id: uuid.UUID, match_id: uuid.UUID | None = None
    ) -> JerseyAssignment:
        assignment = self.repository.get_assignment(assignment_id)
        if assignment is None or (match_id is not None and assignment.match_id != match_id):
            raise self._not_found("Assignment was not found.", "ASSIGNMENT_NOT_FOUND")
        return assignment

    def _require_match_team(
        self, match_id: uuid.UUID, team_id: uuid.UUID, *, for_update: bool
    ) -> MatchTeam:
        match_team = self.repository.get_match_team(match_id, team_id, for_update=for_update)
        if match_team is None:
            raise self._conflict(
                "The selected team does not belong to this match.",
                "TEAM_NOT_IN_MATCH",
            )
        return match_team

    def _validate_organizer(self, match: Match, organizer_token: str) -> None:
        if not organizer_token or not secrets.compare_digest(
            match.organizer_token_hash, hash_token(organizer_token)
        ):
            raise DomainError(
                status=403,
                title="Organizer access denied",
                detail="A valid organizer token is required.",
                error_code="ORGANIZER_ACCESS_DENIED",
            )

    def _ensure_jersey_available(
        self,
        match_id: uuid.UUID,
        team_id: uuid.UUID,
        jersey_number: int,
        started_at: datetime,
    ) -> None:
        if (
            self.repository.find_conflict(
                match_id=match_id,
                team_id=team_id,
                jersey_number=jersey_number,
                started_at=started_at,
            )
            is not None
        ):
            raise self._conflict(
                "This jersey number is already in use by another player.",
                "JERSEY_IN_USE",
            )

    def _validate_effective_time(
        self, assignment: JerseyAssignment, effective_at: datetime
    ) -> None:
        if aware(effective_at) <= aware(assignment.started_at):
            raise DomainError(
                status=422,
                title="Invalid assignment time",
                detail="The effective time must be after the assignment start.",
                error_code="INVALID_ASSIGNMENT_TIME",
            )

    def _commit_assignment(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as exception:
            self.session.rollback()
            raise self._conflict(
                "This jersey number is already in use by another player.",
                "JERSEY_IN_USE",
            ) from exception

    @staticmethod
    def to_match_response(match: Match) -> MatchResponse:
        return MatchResponse(
            id=match.id,
            title=match.title,
            venue_name=match.venue_name,
            starts_at=aware(match.starts_at),
            expected_ends_at=(
                aware(match.expected_ends_at) if match.expected_ends_at is not None else None
            ),
            ended_at=aware(match.ended_at) if match.ended_at is not None else None,
            home_score=match.home_score,
            away_score=match.away_score,
            status=match.status,
            teams=[
                TeamResponse(id=item.team.id, name=item.team.name, side=item.side)
                for item in match.teams
            ],
        )

    @staticmethod
    def to_assignment_response(assignment: JerseyAssignment) -> AssignmentResponse:
        return AssignmentResponse(
            id=assignment.id,
            match_id=assignment.match_id,
            team=TeamResponse(
                id=assignment.team.id,
                name=assignment.team.name,
            ),
            player=PlayerResponse.model_validate(assignment.player),
            jersey_number=assignment.jersey_number,
            started_at=aware(assignment.started_at),
            ended_at=aware(assignment.ended_at) if assignment.ended_at else None,
            supersedes_id=assignment.supersedes_id,
            conflict_override=assignment.conflict_override,
            override_actor=assignment.override_actor,
            override_reason=assignment.override_reason,
        )

    @staticmethod
    def _apply_analytics(
        player: MatchPlayerResponse,
        analytics: PlayerMatchAnalytics,
    ) -> None:
        event_sprints = MatchService._plausible_sprint_count(list(analytics.events))
        metrics = sanitize_player_metrics(
            rating=analytics.rating,
            distance_m=analytics.distance_m,
            avg_speed_kmh=analytics.avg_speed_kmh,
            max_speed_kmh=analytics.max_speed_kmh,
            sprint_count=analytics.sprint_count,
            active_seconds=analytics.active_seconds,
            activity_count=analytics.activity_count,
            peak_speed_at_ms=analytics.peak_speed_at_ms,
            event_sprint_count=event_sprints or None,
        )
        player.rating = metrics.rating
        player.distance_m = metrics.distance_m
        player.avg_speed_kmh = metrics.avg_speed_kmh
        player.max_speed_kmh = metrics.max_speed_kmh
        player.sprint_count = metrics.sprint_count
        player.active_seconds = metrics.active_seconds
        player.activity_count = metrics.activity_count
        player.peak_speed_at_ms = metrics.peak_speed_at_ms
        player.analytics_status = cast(AnalyticsStatus, analytics.status)

    @staticmethod
    def _plausible_sprint_count(events: list[object]) -> int | None:
        count = 0
        for event in events:
            speed = getattr(event, "speed_kmh", None)
            if getattr(event, "event_type", None) != "sprint":
                continue
            if speed is None or speed < SPRINT_KMH or speed > MAX_PLAUSIBLE_STEP_KMH:
                continue
            count += 1
        return count or None

    @staticmethod
    def _not_found(detail: str, code: str) -> DomainError:
        return DomainError(
            status=404,
            title="Resource not found",
            detail=detail,
            error_code=code,
        )

    @staticmethod
    def _gone(detail: str, code: str) -> DomainError:
        return DomainError(
            status=410,
            title="Join unavailable",
            detail=detail,
            error_code=code,
        )

    @staticmethod
    def _conflict(detail: str, code: str) -> DomainError:
        return DomainError(
            status=409,
            title="Conflict",
            detail=detail,
            error_code=code,
        )
