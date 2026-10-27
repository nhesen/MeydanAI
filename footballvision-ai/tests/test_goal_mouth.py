import numpy as np

from app.analytics.goal_mouth import GoalMouth, ball_in_mouth, cluster_goal_times, goal_mouth


def test_blank_frame_has_no_goal_mouth() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    assert goal_mouth(frame) is None


def test_ball_must_be_inside_the_visible_mouth() -> None:
    mouth = GoalMouth("near", np.array([[10, 10], [40, 10], [40, 50], [10, 50]], np.float32))
    assert ball_in_mouth((20, 30), mouth)
    assert not ball_in_mouth((5, 30), mouth)
    assert not ball_in_mouth(None, mouth)
    assert not ball_in_mouth((20, 30), None)


def test_one_noisy_frame_is_not_a_goal() -> None:
    assert cluster_goal_times([12.0]) == []
    assert cluster_goal_times([12.0, 12.1, 14.5, 14.7]) == [(12.0, 12.1), (14.5, 14.7)]
