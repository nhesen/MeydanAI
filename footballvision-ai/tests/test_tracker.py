from app.core.config import AppConfig
from app.core.types import BBox, Detection, Role
from app.tracking.ball_tracker import BallTracker
from app.tracking.player_tracker import PlayerTracker


def test_iou_tracker_keeps_stable_id(config: AppConfig) -> None:
    tracker = PlayerTracker(config)
    first = tracker.update(
        [Detection(BBox(10, 10, 30, 50), 0.9, Role.PLAYER)],
        (120, 160),
    )
    second = tracker.update(
        [Detection(BBox(12, 12, 32, 52), 0.9, Role.PLAYER)],
        (120, 160),
    )
    assert first[0].track_id == second[0].track_id


def test_ball_tracker_interpolates_short_gap(config: AppConfig) -> None:
    tracker = BallTracker(config)
    to_world = lambda x, y: (x / 10, y / 10)
    visible = Detection(BBox(50, 50, 56, 56), 0.8, Role.BALL)
    tracker.update([visible], 0, 0.0, to_world)
    gap = tracker.update([], 1, 0.04, to_world)
    assert gap.interpolated is True
    assert gap.pixel is not None
