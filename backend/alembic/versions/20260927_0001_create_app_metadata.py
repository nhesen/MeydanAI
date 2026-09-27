"""Create application metadata table.

Revision ID: 20260927_0001
Revises:
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_metadata",
        sa.Column("metadata_key", sa.String(length=100), primary_key=True),
        sa.Column("metadata_value", sa.String(length=500), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO app_metadata (metadata_key, metadata_value) "
            "VALUES ('schema_owner', 'alembic')"
        )
    )


def downgrade() -> None:
    op.drop_table("app_metadata")
