import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.domain import JerseyAssignment, Match, MatchJoinToken, MatchTeam, Player, Team
from app.repositories.matches import MatchRepository
from app.schemas.matches import (
    AssignmentCorrection,
    AssignmentCreate,
    AssignmentResponse,
    JerseyChange,
    JoinContextResponse,
    MatchCreate,
    MatchCreatedResponse,
    MatchResponse,
    PlayerResponse,
    TeamResponse,
)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token() -> str:
    return secrets.token_urlsafe(32)


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class MatchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = MatchRepository(session)

    def create_match(self, payload: MatchCreate) -> MatchCreatedResponse:
        organizer_token = create_token()
        join_token = create_token()
        match = Match(
            title=payload.title.strip() if payload.title else None,
            venue_name=payload.venue_name.strip(),
            starts_at=payload.starts_at,
            expected_ends_at=payload.expected_ends_at,
            organizer_token_hash=hash_token(organizer_token),
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

    def get_organizer_match(self, match_id: uuid.UUID, organizer_token: str) -> Match:
        match = self._require_match(match_id)
        self._validate_organizer(match, organizer_token)
        return match

    def rotate_join_token(
        self,
        match_id: uuid.UUID,
        organizer_token: str,
        expires_at: datetime | None,
    ) -> tuple[str, datetime | None]:
        match = self.get_organizer_match(match_id, organizer_token)
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
        self, match_id: uuid.UUID, organizer_token: str
    ) -> list[AssignmentResponse]:
        self.get_organizer_match(match_id, organizer_token)
        return [
            self.to_assignment_response(item) for item in self.repository.list_assignments(match_id)
        ]

    def correct_assignment(
        self,
        match_id: uuid.UUID,
        assignment_id: uuid.UUID,
        organizer_token: str,
        payload: AssignmentCorrection,
    ) -> AssignmentResponse:
        self.get_organizer_match(match_id, organizer_token)
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
        self._commit_assignment()
        return self.to_assignment_response(self._require_assignment(replacement.id))

    def change_jersey(
        self,
        match_id: uuid.UUID,
        assignment_id: uuid.UUID,
        organizer_token: str,
        payload: JerseyChange,
    ) -> AssignmentResponse:
        correction = AssignmentCorrection(
            jersey_number=payload.jersey_number,
            effective_at=payload.effective_at,
            override_conflict=payload.override_conflict,
            override_reason=payload.override_reason,
            override_actor=payload.override_actor,
        )
        return self.correct_assignment(match_id, assignment_id, organizer_token, correction)

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
        if record.match.status in {"completed", "cancelled"}:
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
