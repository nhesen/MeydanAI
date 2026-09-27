import uuid
from datetime import date
from typing import cast

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.domain import (
    Highlight,
    JerseyAssignment,
    Match,
    MatchTeam,
    Player,
    PlayerMatchAnalytics,
    Team,
)


class PlatformRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

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
        ascending: bool = False,
    ) -> tuple[list[Match], int]:
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    Match.title.ilike(pattern),
                    Match.venue_name.ilike(pattern),
                    Match.teams.any(MatchTeam.team.has(Team.name.ilike(pattern))),
                )
            )
        if status:
            filters.append(Match.status == status)
        if team_id:
            filters.append(Match.teams.any(MatchTeam.team_id == team_id))
        if date_from:
            filters.append(func.date(Match.starts_at) >= date_from)
        if date_to:
            filters.append(func.date(Match.starts_at) <= date_to)

        total = self.session.scalar(select(func.count()).select_from(Match).where(*filters)) or 0
        order = Match.starts_at.asc() if ascending else Match.starts_at.desc()
        matches = list(
            self.session.scalars(
                select(Match)
                .where(*filters)
                .options(selectinload(Match.teams).joinedload(MatchTeam.team))
                .order_by(order, Match.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return matches, total

    def analytics_match_ids(self, match_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not match_ids:
            return set()
        return set(
            self.session.scalars(
                select(PlayerMatchAnalytics.match_id)
                .where(PlayerMatchAnalytics.match_id.in_(match_ids))
                .distinct()
            )
        )

    def list_players(
        self,
        *,
        query: str | None,
        team_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Player], int]:
        filters = []
        if query:
            filters.append(Player.display_name.ilike(f"%{query.strip()}%"))
        if team_id:
            filters.append(
                Player.id.in_(
                    select(JerseyAssignment.player_id).where(JerseyAssignment.team_id == team_id)
                )
            )
        total = self.session.scalar(select(func.count()).select_from(Player).where(*filters)) or 0
        players = list(
            self.session.scalars(
                select(Player)
                .where(*filters)
                .order_by(Player.display_name, Player.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return players, total

    def get_player(self, player_id: uuid.UUID) -> Player | None:
        return self.session.get(Player, player_id)

    def player_performance_rows(
        self,
        player_ids: list[uuid.UUID],
    ) -> list[tuple[JerseyAssignment, Match, Team, PlayerMatchAnalytics | None]]:
        if not player_ids:
            return []
        statement = (
            select(JerseyAssignment, Match, Team, PlayerMatchAnalytics)
            .join(Match, Match.id == JerseyAssignment.match_id)
            .join(Team, Team.id == JerseyAssignment.team_id)
            .outerjoin(
                PlayerMatchAnalytics,
                (PlayerMatchAnalytics.match_id == JerseyAssignment.match_id)
                & (PlayerMatchAnalytics.player_id == JerseyAssignment.player_id),
            )
            .where(JerseyAssignment.player_id.in_(player_ids))
            .order_by(
                JerseyAssignment.player_id,
                Match.starts_at.desc(),
                JerseyAssignment.started_at.desc(),
            )
        )
        return cast(
            list[tuple[JerseyAssignment, Match, Team, PlayerMatchAnalytics | None]],
            list(self.session.execute(statement)),
        )

    def list_teams(
        self,
        *,
        query: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[Team, int, int]], int]:
        filters = [Team.name.ilike(f"%{query.strip()}%")] if query else []
        total = self.session.scalar(select(func.count()).select_from(Team).where(*filters)) or 0
        player_count = (
            select(func.count(distinct(JerseyAssignment.player_id)))
            .where(JerseyAssignment.team_id == Team.id)
            .correlate(Team)
            .scalar_subquery()
        )
        match_count = (
            select(func.count(distinct(MatchTeam.match_id)))
            .where(MatchTeam.team_id == Team.id)
            .correlate(Team)
            .scalar_subquery()
        )
        statement = (
            select(Team, player_count, match_count)
            .where(*filters)
            .order_by(Team.name, Team.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = cast(
            list[tuple[Team, int, int]],
            list(self.session.execute(statement)),
        )
        return rows, total

    def get_team_counts(self, team_id: uuid.UUID) -> tuple[Team, int, int] | None:
        player_count = (
            select(func.count(distinct(JerseyAssignment.player_id)))
            .where(JerseyAssignment.team_id == Team.id)
            .correlate(Team)
            .scalar_subquery()
        )
        match_count = (
            select(func.count(distinct(MatchTeam.match_id)))
            .where(MatchTeam.team_id == Team.id)
            .correlate(Team)
            .scalar_subquery()
        )
        row = self.session.execute(
            select(Team, player_count, match_count).where(Team.id == team_id)
        ).one_or_none()
        return cast(tuple[Team, int, int] | None, row)

    def list_team_players(self, team_id: uuid.UUID) -> list[Player]:
        return list(
            self.session.scalars(
                select(Player)
                .join(JerseyAssignment, JerseyAssignment.player_id == Player.id)
                .where(JerseyAssignment.team_id == team_id)
                .distinct()
                .order_by(Player.display_name)
            )
        )

    def list_highlights(
        self,
        *,
        match_id: uuid.UUID | None,
        player_id: uuid.UUID | None,
        highlight_type: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[Highlight, Match, Player | None]], int]:
        filters = []
        if match_id:
            filters.append(Highlight.match_id == match_id)
        if player_id:
            filters.append(Highlight.player_id == player_id)
        if highlight_type:
            filters.append(Highlight.highlight_type == highlight_type)
        total = (
            self.session.scalar(select(func.count()).select_from(Highlight).where(*filters)) or 0
        )
        statement = (
            select(Highlight, Match, Player)
            .join(Match, Match.id == Highlight.match_id)
            .outerjoin(Player, Player.id == Highlight.player_id)
            .where(*filters)
            .order_by(Highlight.created_at.desc(), Highlight.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = cast(
            list[tuple[Highlight, Match, Player | None]],
            list(self.session.execute(statement)),
        )
        return rows, total

    def quick_stats(self) -> tuple[int, int, int, int, int]:
        statement = select(
            select(func.count()).select_from(Match).scalar_subquery(),
            select(func.count())
            .select_from(Match)
            .where(Match.status == "completed")
            .scalar_subquery(),
            select(func.count()).select_from(Player).scalar_subquery(),
            select(func.count()).select_from(Team).scalar_subquery(),
            select(func.count(distinct(PlayerMatchAnalytics.match_id)))
            .select_from(PlayerMatchAnalytics)
            .scalar_subquery(),
        )
        return self.session.execute(statement).one()

    def leaderboard_rows(
        self,
        *,
        team_id: uuid.UUID | None,
        date_from: date | None,
        date_to: date | None,
        minimum_matches: int,
    ) -> list[
        tuple[
            uuid.UUID,
            str,
            int,
            float | None,
            float | None,
            float | None,
            int | None,
        ]
    ]:
        filters = []
        if team_id:
            filters.append(PlayerMatchAnalytics.team_id == team_id)
        if date_from:
            filters.append(func.date(Match.starts_at) >= date_from)
        if date_to:
            filters.append(func.date(Match.starts_at) <= date_to)
        statement = (
            select(
                Player.id,
                Player.display_name,
                func.count(distinct(PlayerMatchAnalytics.match_id)),
                func.avg(PlayerMatchAnalytics.rating),
                func.sum(PlayerMatchAnalytics.distance_m),
                func.max(PlayerMatchAnalytics.max_speed_kmh),
                func.sum(PlayerMatchAnalytics.sprint_count),
            )
            .join(
                PlayerMatchAnalytics,
                PlayerMatchAnalytics.player_id == Player.id,
            )
            .join(Match, Match.id == PlayerMatchAnalytics.match_id)
            .where(*filters)
            .group_by(Player.id, Player.display_name)
            .having(func.count(distinct(PlayerMatchAnalytics.match_id)) >= minimum_matches)
        )
        return cast(
            list[
                tuple[
                    uuid.UUID,
                    str,
                    int,
                    float | None,
                    float | None,
                    float | None,
                    int | None,
                ]
            ],
            list(self.session.execute(statement)),
        )

    def team_analytics_rows(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> list[
        tuple[
            uuid.UUID,
            str,
            int,
            float | None,
            float | None,
            float | None,
            int | None,
        ]
    ]:
        filters = []
        if date_from:
            filters.append(func.date(Match.starts_at) >= date_from)
        if date_to:
            filters.append(func.date(Match.starts_at) <= date_to)
        statement = (
            select(
                Team.id,
                Team.name,
                func.count(distinct(PlayerMatchAnalytics.match_id)),
                func.sum(PlayerMatchAnalytics.distance_m),
                func.avg(PlayerMatchAnalytics.avg_speed_kmh),
                func.max(PlayerMatchAnalytics.max_speed_kmh),
                func.sum(PlayerMatchAnalytics.sprint_count),
            )
            .join(
                PlayerMatchAnalytics,
                PlayerMatchAnalytics.team_id == Team.id,
            )
            .join(Match, Match.id == PlayerMatchAnalytics.match_id)
            .where(*filters)
            .group_by(Team.id, Team.name)
            .order_by(Team.name)
        )
        return cast(
            list[
                tuple[
                    uuid.UUID,
                    str,
                    int,
                    float | None,
                    float | None,
                    float | None,
                    int | None,
                ]
            ],
            list(self.session.execute(statement)),
        )
