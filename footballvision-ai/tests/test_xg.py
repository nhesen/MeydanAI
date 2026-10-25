from app.analytics.xg import expected_goals, goal_angle


def test_close_central_shot_beats_long_wide_shot() -> None:
    close = expected_goals(distance_m=7, goal_angle_rad=0.9, gk_distance_m=8, defenders_in_path=0)
    long_shot = expected_goals(distance_m=28, goal_angle_rad=0.15, gk_distance_m=2, defenders_in_path=3)
    assert close > long_shot
    assert long_shot < 0.05
    distant = expected_goals(
        distance_m=40, goal_angle_rad=0.08, gk_distance_m=2, defenders_in_path=2
    )
    assert distant < 0.012


def test_goal_angle_narrows_from_the_byline() -> None:
    central = goal_angle(30, 10, 40, 10, 3)
    wide = goal_angle(38, 1, 40, 10, 3)
    assert central > wide
