"""Allow FootballVision match event types on player analytics events.

Revision ID: 20261022_0009
Revises: 20260927_0008
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261022_0009"
down_revision: str | None = "20260927_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_VALUES = (
    "sprint",
    "peak_speed",
    "high_intensity_period",
    "custom",
    "pass",
    "successful_pass",
    "failed_pass",
    "key_pass",
    "shot",
    "shot_on_target",
    "shot_off_target",
    "goal",
    "assist",
    "tackle",
    "interception",
    "turnover",
    "ball_recovery",
    "dribble",
    "save",
    "corner",
    "free_kick",
    "penalty",
)


def upgrade() -> None:
    quoted = ", ".join(f"'{item}'" for item in NEW_VALUES)
    op.drop_constraint("ck_player_analytics_event_type", "player_analytics_events", type_="check")
    op.create_check_constraint(
        "ck_player_analytics_event_type",
        "player_analytics_events",
        f"event_type IN ({quoted})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_player_analytics_event_type", "player_analytics_events", type_="check")
    op.create_check_constraint(
        "ck_player_analytics_event_type",
        "player_analytics_events",
        "event_type IN ('sprint', 'peak_speed', 'high_intensity_period', 'custom')",
    )
