import uuid
from datetime import datetime

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.domain import (
    JerseyAssignment,
    Match,
    MatchJoinToken,
    MatchTeam,
    Player,
    PlayerMatchAnalytics,
)


class MatchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_match(self, match_id: uuid.UUID) -> Match | None:
        return self.session.scalar(
            select(Match)
            .where(Match.id == match_id)
            .options(selectinload(Match.teams).joinedload(MatchTeam.team))
        )

    def get_join_token(self, token_hash: str) -> MatchJoinToken | None:
        return self.session.scalar(
            select(MatchJoinToken)
            .where(MatchJoinToken.token_hash == token_hash)
            .options(
                joinedload(MatchJoinToken.match)
                .selectinload(Match.teams)
                .joinedload(MatchTeam.team)
            )
        )

    def get_match_team(
        self, match_id: uuid.UUID, team_id: uuid.UUID, *, for_update: bool = False
    ) -> MatchTeam | None:
        query: Select[MatchTeam] = select(MatchTeam).where(
            MatchTeam.match_id == match_id,
            MatchTeam.team_id == team_id,
        )
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_players(self, limit: int = 30) -> list[Player]:
        return list(self.session.scalars(select(Player).order_by(Player.display_name).limit(limit)))

    def get_player(self, player_id: uuid.UUID) -> Player | None:
        return self.session.get(Player, player_id)

    def get_assignment(self, assignment_id: uuid.UUID) -> JerseyAssignment | None:
        return self.session.scalar(
            select(JerseyAssignment)
            .where(JerseyAssignment.id == assignment_id)
            .options(
                joinedload(JerseyAssignment.player),
                joinedload(JerseyAssignment.team),
            )
        )

    def list_assignments(self, match_id: uuid.UUID) -> list[JerseyAssignment]:
        return list(
            self.session.scalars(
                select(JerseyAssignment)
                .where(JerseyAssignment.match_id == match_id)
                .options(
                    joinedload(JerseyAssignment.player),
                    joinedload(JerseyAssignment.team),
                )
                .order_by(JerseyAssignment.started_at, JerseyAssignment.created_at)
            )
        )

    def list_player_analytics(self, match_id: uuid.UUID) -> list[PlayerMatchAnalytics]:
        return list(
            self.session.scalars(
                select(PlayerMatchAnalytics).where(PlayerMatchAnalytics.match_id == match_id)
            )
        )

    def get_player_analytics(
        self,
        match_id: uuid.UUID,
        player_id: uuid.UUID,
    ) -> PlayerMatchAnalytics | None:
        return self.session.scalar(
            select(PlayerMatchAnalytics)
            .where(
                PlayerMatchAnalytics.match_id == match_id,
                PlayerMatchAnalytics.player_id == player_id,
            )
            .options(
                joinedload(PlayerMatchAnalytics.player),
                joinedload(PlayerMatchAnalytics.team),
                selectinload(PlayerMatchAnalytics.position_samples),
                selectinload(PlayerMatchAnalytics.intensity_buckets),
                selectinload(PlayerMatchAnalytics.events),
            )
        )

    def find_conflict(
        self,
        *,
        match_id: uuid.UUID,
        team_id: uuid.UUID,
        jersey_number: int,
        started_at: datetime,
        ended_at: datetime | None = None,
        exclude_id: uuid.UUID | None = None,
    ) -> JerseyAssignment | None:
        conditions = [
            JerseyAssignment.match_id == match_id,
            JerseyAssignment.team_id == team_id,
            JerseyAssignment.jersey_number == jersey_number,
            JerseyAssignment.conflict_override.is_(False),
            or_(
                JerseyAssignment.ended_at.is_(None),
                JerseyAssignment.ended_at > started_at,
            ),
        ]
        if ended_at is not None:
            conditions.append(JerseyAssignment.started_at < ended_at)
        if exclude_id is not None:
            conditions.append(JerseyAssignment.id != exclude_id)
        return self.session.scalar(select(JerseyAssignment).where(and_(*conditions)).limit(1))

    def find_active_player_assignment(
        self, match_id: uuid.UUID, player_id: uuid.UUID
    ) -> JerseyAssignment | None:
        return self.session.scalar(
            select(JerseyAssignment).where(
                JerseyAssignment.match_id == match_id,
                JerseyAssignment.player_id == player_id,
                JerseyAssignment.ended_at.is_(None),
            )
        )

    def add(self, entity: object) -> None:
        self.session.add(entity)

    def flush(self) -> None:
        self.session.flush()
