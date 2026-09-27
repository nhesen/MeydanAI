"""Add persisted match highlights.

Revision ID: 20260927_0007
Revises: 20260927_0006
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0007"
down_revision: str | None = "20260927_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "highlights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid()),
        sa.Column("highlight_type", sa.String(length=30), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("video_url", sa.String(length=1000)),
        sa.Column("thumbnail_url", sa.String(length=1000)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "highlight_type IN ('goal', 'top_run', 'sprint', 'key_moment', "
            "'manual', 'ai_detected')",
            name="ck_highlights_type",
        ),
        sa.CheckConstraint(
            "timestamp_ms >= 0",
            name="ck_highlights_timestamp",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms > 0",
            name="ck_highlights_duration",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_highlights_match_id", "highlights", ["match_id"])
    op.create_index("ix_highlights_player_id", "highlights", ["player_id"])
    op.create_index(
        "ix_highlights_highlight_type",
        "highlights",
        ["highlight_type"],
    )
    op.create_index(
        "ix_highlights_match_created",
        "highlights",
        ["match_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_highlights_match_created", table_name="highlights")
    op.drop_index("ix_highlights_highlight_type", table_name="highlights")
    op.drop_index("ix_highlights_player_id", table_name="highlights")
    op.drop_index("ix_highlights_match_id", table_name="highlights")
    op.drop_table("highlights")
