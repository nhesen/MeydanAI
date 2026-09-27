"""Add player match analytics and visualization data.

Revision ID: 20260927_0004
Revises: 20260927_0003
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0004"
down_revision: str | None = "20260927_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_match_analytics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rating", sa.Float()),
        sa.Column("distance_m", sa.Float()),
        sa.Column("avg_speed_kmh", sa.Float()),
        sa.Column("max_speed_kmh", sa.Float()),
        sa.Column("sprint_count", sa.Integer()),
        sa.Column("active_seconds", sa.Integer()),
        sa.Column("activity_count", sa.Integer()),
        sa.Column("peak_speed_at_ms", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'available', 'unavailable', 'failed')",
            name="ck_player_analytics_status",
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 10)",
            name="ck_player_analytics_rating",
        ),
        sa.CheckConstraint(
            "distance_m IS NULL OR distance_m >= 0",
            name="ck_player_analytics_distance",
        ),
        sa.CheckConstraint(
            "avg_speed_kmh IS NULL OR avg_speed_kmh >= 0",
            name="ck_player_analytics_avg_speed",
        ),
        sa.CheckConstraint(
            "max_speed_kmh IS NULL OR max_speed_kmh >= 0",
            name="ck_player_analytics_max_speed",
        ),
        sa.CheckConstraint(
            "sprint_count IS NULL OR sprint_count >= 0",
            name="ck_player_analytics_sprints",
        ),
        sa.CheckConstraint(
            "active_seconds IS NULL OR active_seconds >= 0",
            name="ck_player_analytics_active_seconds",
        ),
        sa.CheckConstraint(
            "activity_count IS NULL OR activity_count >= 0",
            name="ck_player_analytics_activity_count",
        ),
        sa.CheckConstraint(
            "peak_speed_at_ms IS NULL OR peak_speed_at_ms >= 0",
            name="ck_player_analytics_peak_speed_time",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["match_id", "team_id"],
            ["match_teams.match_id", "match_teams.team_id"],
            name="fk_player_analytics_match_team",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "match_id",
            "player_id",
            name="uq_player_analytics_match_player",
        ),
    )
    op.create_index(
        "ix_player_match_analytics_match_id",
        "player_match_analytics",
        ["match_id"],
    )
    op.create_index(
        "ix_player_match_analytics_player_id",
        "player_match_analytics",
        ["player_id"],
    )
    op.create_index(
        "ix_player_match_analytics_team_id",
        "player_match_analytics",
        ["team_id"],
    )

    op.create_table(
        "player_position_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analytics_id", sa.Uuid(), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("timestamp_ms >= 0", name="ck_position_samples_time"),
        sa.CheckConstraint("x >= 0 AND x <= 1", name="ck_position_samples_x"),
        sa.CheckConstraint("y >= 0 AND y <= 1", name="ck_position_samples_y"),
        sa.ForeignKeyConstraint(
            ["analytics_id"],
            ["player_match_analytics.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_position_samples_analytics_time",
        "player_position_samples",
        ["analytics_id", "timestamp_ms"],
    )

    op.create_table(
        "player_intensity_buckets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analytics_id", sa.Uuid(), nullable=False),
        sa.Column("from_minute", sa.Integer(), nullable=False),
        sa.Column("to_minute", sa.Integer(), nullable=False),
        sa.Column("intensity", sa.Float(), nullable=False),
        sa.CheckConstraint("from_minute >= 0", name="ck_intensity_from_minute"),
        sa.CheckConstraint(
            "to_minute > from_minute",
            name="ck_intensity_valid_interval",
        ),
        sa.CheckConstraint(
            "intensity >= 0 AND intensity <= 100",
            name="ck_intensity_range",
        ),
        sa.ForeignKeyConstraint(
            ["analytics_id"],
            ["player_match_analytics.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analytics_id",
            "from_minute",
            "to_minute",
            name="uq_intensity_analytics_interval",
        ),
    )
    op.create_index(
        "ix_player_intensity_buckets_analytics_id",
        "player_intensity_buckets",
        ["analytics_id"],
    )

    op.create_table(
        "player_analytics_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analytics_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=False),
        sa.Column("speed_kmh", sa.Float()),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('sprint', 'peak_speed', 'high_intensity_period', 'custom')",
            name="ck_player_analytics_event_type",
        ),
        sa.CheckConstraint(
            "timestamp_ms >= 0",
            name="ck_player_analytics_event_time",
        ),
        sa.CheckConstraint(
            "speed_kmh IS NULL OR speed_kmh >= 0",
            name="ck_player_analytics_event_speed",
        ),
        sa.ForeignKeyConstraint(
            ["analytics_id"],
            ["player_match_analytics.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_player_analytics_events_analytics_id",
        "player_analytics_events",
        ["analytics_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_player_analytics_events_analytics_id",
        table_name="player_analytics_events",
    )
    op.drop_table("player_analytics_events")
    op.drop_index(
        "ix_player_intensity_buckets_analytics_id",
        table_name="player_intensity_buckets",
    )
    op.drop_table("player_intensity_buckets")
    op.drop_index(
        "ix_position_samples_analytics_time",
        table_name="player_position_samples",
    )
    op.drop_table("player_position_samples")
    op.drop_index(
        "ix_player_match_analytics_team_id",
        table_name="player_match_analytics",
    )
    op.drop_index(
        "ix_player_match_analytics_player_id",
        table_name="player_match_analytics",
    )
    op.drop_index(
        "ix_player_match_analytics_match_id",
        table_name="player_match_analytics",
    )
    op.drop_table("player_match_analytics")
