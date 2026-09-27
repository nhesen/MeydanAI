"""Add analytics processing jobs.

Revision ID: 20260927_0005
Revises: 20260927_0004
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0005"
down_revision: str | None = "20260927_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("retry_of_id", sa.Uuid()),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Integer()),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("source_media_type", sa.String(length=100), nullable=False),
        sa.Column("source_size_bytes", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_run_id", sa.String(length=200)),
        sa.Column("calibration_metadata", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column("error_message", sa.Text()),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_processing_jobs_status",
        ),
        sa.CheckConstraint(
            "stage IN ('queued', 'uploading', 'validating', 'preprocessing', "
            "'detecting_players', 'tracking_players', 'calibrating_field', "
            "'calculating_metrics', 'persisting_results', 'completed')",
            name="ck_processing_jobs_stage",
        ),
        sa.CheckConstraint(
            "progress IS NULL OR (progress >= 0 AND progress <= 100)",
            name="ck_processing_jobs_progress",
        ),
        sa.CheckConstraint(
            "source_type IN ('uploaded_video')",
            name="ck_processing_jobs_source_type",
        ),
        sa.CheckConstraint(
            "source_size_bytes > 0",
            name="ck_processing_jobs_source_size",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_id"],
            ["processing_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_processing_jobs_match_id",
        "processing_jobs",
        ["match_id"],
    )
    op.create_index(
        "ix_processing_jobs_retry_of_id",
        "processing_jobs",
        ["retry_of_id"],
    )
    op.create_index(
        "ix_processing_jobs_status",
        "processing_jobs",
        ["status"],
    )
    op.create_index(
        "ix_processing_jobs_match_status_created",
        "processing_jobs",
        ["match_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processing_jobs_match_status_created",
        table_name="processing_jobs",
    )
    op.drop_index("ix_processing_jobs_status", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_retry_of_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_match_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
