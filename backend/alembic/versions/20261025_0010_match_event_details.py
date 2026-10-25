"""Record goal kicks, woodwork and big chances as player events.

Revision ID: 20261025_0010
Revises: 20261022_0009
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261025_0010"
down_revision: str | None = "20261022_0009"
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
    "goal_kick",
    "woodwork",
    "big_chance",
    "free_kick",
    "penalty",
)

PREVIOUS_VALUES = tuple(
    item for item in NEW_VALUES if item not in {"goal_kick", "woodwork", "big_chance"}
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
    quoted = ", ".join(f"'{item}'" for item in PREVIOUS_VALUES)
    op.drop_constraint("ck_player_analytics_event_type", "player_analytics_events", type_="check")
    op.create_check_constraint(
        "ck_player_analytics_event_type",
        "player_analytics_events",
        f"event_type IN ({quoted})",
    )
