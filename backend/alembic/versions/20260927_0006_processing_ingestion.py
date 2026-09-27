"""Add idempotent processing ingestion support.

Revision ID: 20260927_0006
Revises: 20260927_0005
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0006"
down_revision: str | None = "20260927_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processing_ingestion_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False),
        sa.Column("intensity_bucket_count", sa.Integer(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["processing_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "idempotency_key",
            name="uq_ingestion_batches_job_key",
        ),
    )
    op.create_index(
        "ix_processing_ingestion_batches_job_id",
        "processing_ingestion_batches",
        ["job_id"],
    )
    op.create_index(
        "ix_processing_ingestion_batches_player_id",
        "processing_ingestion_batches",
        ["player_id"],
    )

    op.create_table(
        "processing_track_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("provider_track_id", sa.String(length=120), nullable=False),
        sa.Column("mapping_status", sa.String(length=20), nullable=False),
        sa.Column("player_id", sa.Uuid()),
        sa.Column("team_id", sa.Uuid()),
        sa.Column("observed_jersey", sa.Integer()),
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
            "mapping_status IN ('mapped', 'unresolved')",
            name="ck_track_mappings_status",
        ),
        sa.CheckConstraint(
            "(mapping_status = 'unresolved' AND player_id IS NULL AND team_id IS NULL) "
            "OR (mapping_status = 'mapped' AND player_id IS NOT NULL "
            "AND team_id IS NOT NULL)",
            name="ck_track_mappings_identity",
        ),
        sa.CheckConstraint(
            "observed_jersey IS NULL OR (observed_jersey >= 0 AND observed_jersey <= 99)",
            name="ck_track_mappings_jersey",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["processing_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "provider_track_id",
            name="uq_track_mappings_job_track",
        ),
    )
    op.create_index(
        "ix_processing_track_mappings_job_id",
        "processing_track_mappings",
        ["job_id"],
    )
    op.create_index(
        "ix_processing_track_mappings_player_id",
        "processing_track_mappings",
        ["player_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processing_track_mappings_player_id",
        table_name="processing_track_mappings",
    )
    op.drop_index(
        "ix_processing_track_mappings_job_id",
        table_name="processing_track_mappings",
    )
    op.drop_table("processing_track_mappings")
    op.drop_index(
        "ix_processing_ingestion_batches_player_id",
        table_name="processing_ingestion_batches",
    )
    op.drop_index(
        "ix_processing_ingestion_batches_job_id",
        table_name="processing_ingestion_batches",
    )
    op.drop_table("processing_ingestion_batches")
