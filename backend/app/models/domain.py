import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(100))
    normalized_name: Mapped[str] = mapped_column(String(100), index=True)
    is_temporary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(
            "expected_ends_at IS NULL OR expected_ends_at > starts_at",
            name="ck_matches_expected_end_after_start",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'live', 'completed', 'cancelled')",
            name="ck_matches_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(String(140))
    venue_name: Mapped[str] = mapped_column(String(140))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expected_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    organizer_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    teams: Mapped[list["MatchTeam"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchTeam.side",
    )


class MatchTeam(Base):
    __tablename__ = "match_teams"
    __table_args__ = (
        UniqueConstraint("match_id", "side", name="uq_match_teams_match_side"),
        UniqueConstraint("match_id", "team_id", name="uq_match_teams_match_team"),
        CheckConstraint("side IN ('home', 'away')", name="ck_match_teams_side"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    side: Mapped[str] = mapped_column(String(10))

    match: Mapped[Match] = relationship(back_populates="teams")
    team: Mapped[Team] = relationship()


class MatchJoinToken(Base):
    __tablename__ = "match_join_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    match: Mapped[Match] = relationship()


class JerseyAssignment(Base):
    __tablename__ = "jersey_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["match_id", "team_id"],
            ["match_teams.match_id", "match_teams.team_id"],
            ondelete="CASCADE",
            name="fk_assignments_match_team",
        ),
        CheckConstraint(
            "jersey_number >= 0 AND jersey_number <= 99",
            name="ck_assignments_jersey_number",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at > started_at",
            name="ck_assignments_valid_interval",
        ),
        CheckConstraint(
            "(conflict_override = false AND override_reason IS NULL) OR "
            "(conflict_override = true AND override_reason IS NOT NULL "
            "AND override_actor IS NOT NULL AND override_at IS NOT NULL)",
            name="ck_assignments_override_audit",
        ),
        Index(
            "uq_assignments_active_jersey",
            "match_id",
            "team_id",
            "jersey_number",
            unique=True,
            postgresql_where=text("ended_at IS NULL AND conflict_override = false"),
            sqlite_where=text("ended_at IS NULL AND conflict_override = 0"),
        ),
        Index("ix_assignments_player_match", "player_id", "match_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    jersey_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    closed_reason: Mapped[str | None] = mapped_column(String(80))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jersey_assignments.id", ondelete="SET NULL")
    )
    conflict_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_actor: Mapped[str | None] = mapped_column(String(100))
    override_reason: Mapped[str | None] = mapped_column(Text)
    override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    player: Mapped[Player] = relationship()
    team: Mapped[Team] = relationship()
