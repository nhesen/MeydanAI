from types import SimpleNamespace

import numpy as np
import pytest

from app.core.config import AppConfig
from app.core.types import BBox, Detection, Role
from app.tracking.ball_tracker import BallTracker
from app.tracking.player_tracker import PlayerTracker


def test_iou_tracker_keeps_stable_id(config: AppConfig) -> None:
    tracker = PlayerTracker(config)
    first = tracker.update(
        [Detection(BBox(10, 10, 30, 50), 0.9, Role.PLAYER)],
    )
    second = tracker.update(
        [Detection(BBox(12, 12, 32, 52), 0.9, Role.PLAYER)],
    )
    assert first[0].track_id == second[0].track_id


def test_real_bytetrack_keeps_confirmed_id(config: AppConfig) -> None:
    pytest.importorskip("supervision")
    pytest.importorskip("trackers")
    tracker = PlayerTracker(config)
    observations = []
    for index in range(3):
        observations.append(
            tracker.update(
                [Detection(BBox(10 + index, 10, 30 + index, 50), 0.9, Role.PLAYER)],
                (120, 160),
            )
        )
    assert observations[1][0].track_id is not None
    assert observations[1][0].track_id == observations[2][0].track_id


def test_ball_tracker_interpolates_short_gap(config: AppConfig) -> None:
    tracker = BallTracker(config)
    to_world = lambda x, y: (x / 10, y / 10)
    visible = Detection(BBox(50, 50, 56, 56), 0.8, Role.BALL)
    tracker.update([visible], 0, 0.0, to_world)
    gap = tracker.update([], 1, 0.04, to_world)
    assert gap.interpolated is True
    assert gap.pixel is not None


def test_bytetrack_reordered_output_keeps_correct_detection_ids(
    config: AppConfig,
) -> None:
    pytest.importorskip("supervision")
    tracker = PlayerTracker(config)

    class ReorderedTracker:
        def update_with_detections(self, wrapped):
            return SimpleNamespace(
                tracker_id=np.array([91]), data={"source_index": np.array([1])}
            )

    tracker._supervision = ReorderedTracker()
    detections = [
        Detection(BBox(10, 10, 30, 50), 0.9, Role.PLAYER),
        Detection(BBox(60, 10, 80, 50), 0.9, Role.PLAYER),
    ]
    tracked = tracker.update(detections, (120, 160))
    assert tracked[0].track_id is None
    assert tracked[1].track_id == 1


def test_tracker_reset_never_reuses_an_identity(config: AppConfig) -> None:
    tracker = PlayerTracker(config)
    first = tracker.update([Detection(BBox(10, 10, 30, 50), 0.9, Role.PLAYER)])
    tracker.reset()
    second = tracker.update([Detection(BBox(10, 10, 30, 50), 0.9, Role.PLAYER)])
    assert second[0].track_id != first[0].track_id


def test_ball_velocity_does_not_cross_a_scene_cut(config: AppConfig) -> None:
    tracker = BallTracker(config)
    to_world = lambda x, y: (x, y)
    tracker.update([Detection(BBox(0, 0, 2, 2), 0.9, Role.BALL)], 0, 0, to_world)
    tracker.cut()
    current = tracker.update(
        [Detection(BBox(90, 0, 92, 2), 0.9, Role.BALL)], 1, 0.04, to_world
    )
    assert current.velocity_mps is None
    assert current.scene_cut


def test_ball_gap_limit_uses_source_frames_when_sampling(config: AppConfig) -> None:
    tracker = BallTracker(config)
    tracker.update(
        [Detection(BBox(0, 0, 2, 2), 0.9, Role.BALL)], 0, 0, lambda x, y: (x, y)
    )
    gap = tracker.update([], 15, 0.6, lambda x, y: (x, y))
    assert gap.pixel is None
    assert not gap.interpolated
