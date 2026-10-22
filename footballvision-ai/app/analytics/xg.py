from __future__ import annotations

import math


def expected_goals(
    *,
    distance_m: float,
    goal_angle_rad: float,
    gk_distance_m: float | None,
    defenders_in_path: int,
) -> float:
    """Simple logistic xG using shot distance, angle, keeper and traffic."""
    angle_term = max(0.05, min(1.2, goal_angle_rad))
    gk_term = 0.0
    if gk_distance_m is not None:
        gk_term = max(-1.1, min(0.4, (gk_distance_m - 4.0) / 6.0))
    logit = (
        0.15
        - 0.13 * distance_m
        + 1.7 * (angle_term / (math.pi / 2))
        + 0.45 * gk_term
        - 0.22 * defenders_in_path
    )
    value = 1.0 / (1.0 + math.exp(-logit))
    return round(min(0.92, max(0.015, value)), 3)


def goal_angle(shot_x: float, shot_y: float, goal_x: float, goal_y: float, goal_width_m: float) -> float:
    left = (goal_x, goal_y - goal_width_m / 2)
    right = (goal_x, goal_y + goal_width_m / 2)
    a = math.atan2(left[1] - shot_y, left[0] - shot_x)
    b = math.atan2(right[1] - shot_y, right[0] - shot_x)
    return abs(a - b)
