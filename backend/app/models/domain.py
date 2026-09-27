import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    player: Mapped[Player | None] = relationship()


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user_expires", "user_id", "expires_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(80))
    event_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(
            "expected_ends_at IS NULL OR expected_ends_at > starts_at",
            name="ck_matches_expected_end_after_start",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'live', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_matches_status",
        ),
        CheckConstraint(
            "home_score IS NULL OR home_score >= 0",
            name="ck_matches_home_score",
        ),
        CheckConstraint(
            "away_score IS NULL OR away_score >= 0",
            name="ck_matches_away_score",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at > starts_at",
            name="ck_matches_end_after_start",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(String(140))
    venue_name: Mapped[str] = mapped_column(String(140))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expected_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    organizer_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    organizer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
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


class Highlight(Base):
    __tablename__ = "highlights"
    __table_args__ = (
        CheckConstraint(
            "highlight_type IN ('goal', 'top_run', 'sprint', 'key_moment', "
            "'manual', 'ai_detected')",
            name="ck_highlights_type",
        ),
        CheckConstraint("timestamp_ms >= 0", name="ck_highlights_timestamp"),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms > 0",
            name="ck_highlights_duration",
        ),
        Index("ix_highlights_match_created", "match_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), index=True
    )
    highlight_type: Mapped[str] = mapped_column(String(30), index=True)
    timestamp_ms: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(140))
    video_url: Mapped[str | None] = mapped_column(String(1000))
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    match: Mapped[Match] = relationship()
    player: Mapped[Player | None] = relationship()


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_processing_jobs_status",
        ),
        CheckConstraint(
            "stage IN ('queued', 'uploading', 'validating', 'preprocessing', "
            "'detecting_players', 'tracking_players', 'calibrating_field', "
            "'calculating_metrics', 'persisting_results', 'completed')",
            name="ck_processing_jobs_stage",
        ),
        CheckConstraint(
            "progress IS NULL OR (progress >= 0 AND progress <= 100)",
            name="ck_processing_jobs_progress",
        ),
        CheckConstraint(
            "source_type IN ('uploaded_video')",
            name="ck_processing_jobs_source_type",
        ),
        CheckConstraint(
            "source_size_bytes > 0",
            name="ck_processing_jobs_source_size",
        ),
        Index(
            "ix_processing_jobs_match_status_created",
            "match_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    retry_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[int | None] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    source_type: Mapped[str] = mapped_column(String(30))
    source_reference: Mapped[str] = mapped_column(String(500))
    source_media_type: Mapped[str] = mapped_column(String(100))
    source_size_bytes: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(50))
    provider_run_id: Mapped[str | None] = mapped_column(String(200))
    calibration_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)

    match: Mapped[Match] = relationship()
    retry_of: Mapped["ProcessingJob | None"] = relationship(remote_side=[id])


class ProcessingIngestionBatch(Base):
    __tablename__ = "processing_ingestion_batches"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "idempotency_key",
            name="uq_ingestion_batches_job_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(120))
    payload_hash: Mapped[str] = mapped_column(String(64))
    position_count: Mapped[int] = mapped_column(Integer)
    intensity_bucket_count: Mapped[int] = mapped_column(Integer)
    event_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProcessingTrackMapping(Base):
    __tablename__ = "processing_track_mappings"
    __table_args__ = (
        CheckConstraint(
            "mapping_status IN ('mapped', 'unresolved')",
            name="ck_track_mappings_status",
        ),
        CheckConstraint(
            "(mapping_status = 'unresolved' AND player_id IS NULL AND team_id IS NULL) "
            "OR (mapping_status = 'mapped' AND player_id IS NOT NULL "
            "AND team_id IS NOT NULL)",
            name="ck_track_mappings_identity",
        ),
        CheckConstraint(
            "observed_jersey IS NULL OR (observed_jersey >= 0 AND observed_jersey <= 99)",
            name="ck_track_mappings_jersey",
        ),
        UniqueConstraint(
            "job_id",
            "provider_track_id",
            name="uq_track_mappings_job_track",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="CASCADE"), index=True
    )
    provider_track_id: Mapped[str] = mapped_column(String(120))
    mapping_status: Mapped[str] = mapped_column(String(20))
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), index=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    observed_jersey: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


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


class PlayerMatchAnalytics(Base):
    __tablename__ = "player_match_analytics"
    __table_args__ = (
        ForeignKeyConstraint(
            ["match_id", "team_id"],
            ["match_teams.match_id", "match_teams.team_id"],
            ondelete="CASCADE",
            name="fk_player_analytics_match_team",
        ),
        UniqueConstraint(
            "match_id",
            "player_id",
            name="uq_player_analytics_match_player",
        ),
        CheckConstraint(
            "status IN ('processing', 'available', 'unavailable', 'failed')",
            name="ck_player_analytics_status",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 10)",
            name="ck_player_analytics_rating",
        ),
        CheckConstraint(
            "distance_m IS NULL OR distance_m >= 0",
            name="ck_player_analytics_distance",
        ),
        CheckConstraint(
            "avg_speed_kmh IS NULL OR avg_speed_kmh >= 0",
            name="ck_player_analytics_avg_speed",
        ),
        CheckConstraint(
            "max_speed_kmh IS NULL OR max_speed_kmh >= 0",
            name="ck_player_analytics_max_speed",
        ),
        CheckConstraint(
            "sprint_count IS NULL OR sprint_count >= 0",
            name="ck_player_analytics_sprints",
        ),
        CheckConstraint(
            "active_seconds IS NULL OR active_seconds >= 0",
            name="ck_player_analytics_active_seconds",
        ),
        CheckConstraint(
            "activity_count IS NULL OR activity_count >= 0",
            name="ck_player_analytics_activity_count",
        ),
        CheckConstraint(
            "peak_speed_at_ms IS NULL OR peak_speed_at_ms >= 0",
            name="ck_player_analytics_peak_speed_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="unavailable")
    rating: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float)
    avg_speed_kmh: Mapped[float | None] = mapped_column(Float)
    max_speed_kmh: Mapped[float | None] = mapped_column(Float)
    sprint_count: Mapped[int | None] = mapped_column(Integer)
    active_seconds: Mapped[int | None] = mapped_column(Integer)
    activity_count: Mapped[int | None] = mapped_column(Integer)
    peak_speed_at_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    player: Mapped[Player] = relationship()
    team: Mapped[Team] = relationship()
    position_samples: Mapped[list["PlayerPositionSample"]] = relationship(
        back_populates="analytics",
        cascade="all, delete-orphan",
        order_by="PlayerPositionSample.timestamp_ms",
    )
    intensity_buckets: Mapped[list["PlayerIntensityBucket"]] = relationship(
        back_populates="analytics",
        cascade="all, delete-orphan",
        order_by="PlayerIntensityBucket.from_minute",
    )
    events: Mapped[list["PlayerAnalyticsEvent"]] = relationship(
        back_populates="analytics",
        cascade="all, delete-orphan",
        order_by="PlayerAnalyticsEvent.timestamp_ms",
    )


class PlayerPositionSample(Base):
    __tablename__ = "player_position_samples"
    __table_args__ = (
        CheckConstraint("timestamp_ms >= 0", name="ck_position_samples_time"),
        CheckConstraint("x >= 0 AND x <= 1", name="ck_position_samples_x"),
        CheckConstraint("y >= 0 AND y <= 1", name="ck_position_samples_y"),
        Index(
            "ix_position_samples_analytics_time",
            "analytics_id",
            "timestamp_ms",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analytics_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("player_match_analytics.id", ondelete="CASCADE")
    )
    timestamp_ms: Mapped[int] = mapped_column(Integer)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    analytics: Mapped[PlayerMatchAnalytics] = relationship(back_populates="position_samples")


class PlayerIntensityBucket(Base):
    __tablename__ = "player_intensity_buckets"
    __table_args__ = (
        CheckConstraint("from_minute >= 0", name="ck_intensity_from_minute"),
        CheckConstraint("to_minute > from_minute", name="ck_intensity_valid_interval"),
        CheckConstraint(
            "intensity >= 0 AND intensity <= 100",
            name="ck_intensity_range",
        ),
        UniqueConstraint(
            "analytics_id",
            "from_minute",
            "to_minute",
            name="uq_intensity_analytics_interval",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analytics_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("player_match_analytics.id", ondelete="CASCADE"), index=True
    )
    from_minute: Mapped[int] = mapped_column(Integer)
    to_minute: Mapped[int] = mapped_column(Integer)
    intensity: Mapped[float] = mapped_column(Float)

    analytics: Mapped[PlayerMatchAnalytics] = relationship(back_populates="intensity_buckets")


class PlayerAnalyticsEvent(Base):
    __tablename__ = "player_analytics_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('sprint', 'peak_speed', 'high_intensity_period', 'custom')",
            name="ck_player_analytics_event_type",
        ),
        CheckConstraint("timestamp_ms >= 0", name="ck_player_analytics_event_time"),
        CheckConstraint(
            "speed_kmh IS NULL OR speed_kmh >= 0",
            name="ck_player_analytics_event_speed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analytics_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("player_match_analytics.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32))
    timestamp_ms: Mapped[int] = mapped_column(Integer)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(140))

    analytics: Mapped[PlayerMatchAnalytics] = relationship(back_populates="events")
