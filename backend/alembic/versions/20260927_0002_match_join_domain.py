"""Add match join and jersey assignment domain.

Revision ID: 20260927_0002
Revises: 20260927_0001
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0002"
down_revision: str | None = "20260927_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("is_temporary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_players_normalized_name", "players", ["normalized_name"])
    op.create_table(
        "matches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(140)),
        sa.Column("venue_name", sa.String(140), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_ends_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("organizer_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "expected_ends_at IS NULL OR expected_ends_at > starts_at",
            name="ck_matches_expected_end_after_start",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'live', 'completed', 'cancelled')",
            name="ck_matches_status",
        ),
    )
    op.create_index("ix_matches_starts_at", "matches", ["starts_at"])
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_table(
        "match_teams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.Uuid(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("side", sa.String(10), nullable=False),
        sa.CheckConstraint("side IN ('home', 'away')", name="ck_match_teams_side"),
        sa.UniqueConstraint("match_id", "side", name="uq_match_teams_match_side"),
        sa.UniqueConstraint("match_id", "team_id", name="uq_match_teams_match_team"),
    )
    op.create_index("ix_match_teams_match_id", "match_teams", ["match_id"])
    op.create_index("ix_match_teams_team_id", "match_teams", ["team_id"])
    op.create_table(
        "match_join_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_match_join_tokens_match_id", "match_join_tokens", ["match_id"])
    op.create_index("ix_match_join_tokens_token_hash", "match_join_tokens", ["token_hash"])
    op.create_index("ix_match_join_tokens_expires_at", "match_join_tokens", ["expires_at"])
    op.create_index("ix_match_join_tokens_revoked_at", "match_join_tokens", ["revoked_at"])
    op.create_table(
        "jersey_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.Uuid(),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "player_id",
            sa.Uuid(),
            sa.ForeignKey("players.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("jersey_number", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("closed_reason", sa.String(80)),
        sa.Column(
            "supersedes_id",
            sa.Uuid(),
            sa.ForeignKey("jersey_assignments.id", ondelete="SET NULL"),
        ),
        sa.Column("conflict_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_actor", sa.String(100)),
        sa.Column("override_reason", sa.Text()),
        sa.Column("override_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["match_id", "team_id"],
            ["match_teams.match_id", "match_teams.team_id"],
            ondelete="CASCADE",
            name="fk_assignments_match_team",
        ),
        sa.CheckConstraint(
            "jersey_number >= 0 AND jersey_number <= 99",
            name="ck_assignments_jersey_number",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at > started_at",
            name="ck_assignments_valid_interval",
        ),
        sa.CheckConstraint(
            "(conflict_override = false AND override_reason IS NULL) OR "
            "(conflict_override = true AND override_reason IS NOT NULL "
            "AND override_actor IS NOT NULL AND override_at IS NOT NULL)",
            name="ck_assignments_override_audit",
        ),
    )
    op.create_index("ix_jersey_assignments_match_id", "jersey_assignments", ["match_id"])
    op.create_index("ix_jersey_assignments_team_id", "jersey_assignments", ["team_id"])
    op.create_index("ix_jersey_assignments_player_id", "jersey_assignments", ["player_id"])
    op.create_index(
        "ix_assignments_player_match",
        "jersey_assignments",
        ["player_id", "match_id"],
    )
    op.create_index(
        "uq_assignments_active_jersey",
        "jersey_assignments",
        ["match_id", "team_id", "jersey_number"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL AND conflict_override = false"),
    )
    op.execute(
        """
        ALTER TABLE jersey_assignments
        ADD CONSTRAINT ex_assignments_jersey_interval
        EXCLUDE USING gist (
            match_id WITH =,
            team_id WITH =,
            jersey_number WITH =,
            tstzrange(started_at, ended_at, '[)') WITH &&
        )
        WHERE (conflict_override = false)
        """
    )


def downgrade() -> None:
    op.drop_table("jersey_assignments")
    op.drop_table("match_join_tokens")
    op.drop_table("match_teams")
    op.drop_table("matches")
    op.drop_index("ix_players_normalized_name", table_name="players")
    op.drop_table("players")
    op.drop_table("teams")
