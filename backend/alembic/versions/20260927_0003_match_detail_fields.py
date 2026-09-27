"""Add match detail score and lifecycle fields.

Revision ID: 20260927_0003
Revises: 20260927_0002
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0003"
down_revision: str | None = "20260927_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("ended_at", sa.DateTime(timezone=True)))
    op.add_column("matches", sa.Column("home_score", sa.Integer()))
    op.add_column("matches", sa.Column("away_score", sa.Integer()))
    op.drop_constraint("ck_matches_status", "matches", type_="check")
    op.create_check_constraint(
        "ck_matches_status",
        "matches",
        "status IN ('scheduled', 'live', 'processing', 'completed', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_matches_home_score",
        "matches",
        "home_score IS NULL OR home_score >= 0",
    )
    op.create_check_constraint(
        "ck_matches_away_score",
        "matches",
        "away_score IS NULL OR away_score >= 0",
    )
    op.create_check_constraint(
        "ck_matches_end_after_start",
        "matches",
        "ended_at IS NULL OR ended_at > starts_at",
    )


def downgrade() -> None:
    op.drop_constraint("ck_matches_end_after_start", "matches", type_="check")
    op.drop_constraint("ck_matches_away_score", "matches", type_="check")
    op.drop_constraint("ck_matches_home_score", "matches", type_="check")
    op.drop_constraint("ck_matches_status", "matches", type_="check")
    op.create_check_constraint(
        "ck_matches_status",
        "matches",
        "status IN ('scheduled', 'live', 'completed', 'cancelled')",
    )
    op.drop_column("matches", "away_score")
    op.drop_column("matches", "home_score")
    op.drop_column("matches", "ended_at")
