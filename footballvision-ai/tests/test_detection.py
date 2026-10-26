from types import SimpleNamespace
from typing import ClassVar

import numpy as np
import pytest

from app.core.types import Role
from app.detection.yolo import FootballDetector


def result(boxes=None):
    return SimpleNamespace(names=["player", "ball", "referee"], boxes=boxes)


def test_detector_filters_invalid_boxes_and_separate_ball_threshold(config):
    boxes = SimpleNamespace(
        xyxy=np.array(
            [
                [0, 0, 10, 20],
                [1, 1, 3, 3],
                [0, 0, 8, 20],
                [np.nan, 0, 2, 2],
                [4, 4, 2, 2],
            ]
        ),
        conf=np.array([0.9, 0.15, 0.2, 0.99, 0.99]),
        cls=np.array([0, 1, 0, 0, 0]),
        id=None,
    )
    parsed = FootballDetector(config, model=SimpleNamespace(names={})).parse_result(
        result(boxes)
    )
    assert [item.role for item in parsed] == [Role.PLAYER, Role.BALL]


def test_detector_retries_smaller_batches_after_out_of_memory(config):
    calls = []

    class Model:
        names: ClassVar[dict[int, str]] = {0: "player"}

        def predict(self, frames, **kwargs):
            calls.append(len(frames))
            if len(frames) > 1:
                raise RuntimeError("CUDA out of memory")
            return [result()]

    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(4)]
    found = FootballDetector(config, model=Model()).detect_many(frames)
    assert len(found) == 4
    assert calls == [4, 2, 1, 1, 2, 1, 1]


def test_detector_rejects_incomplete_batch(config):
    model = SimpleNamespace(names={}, predict=lambda *args, **kwargs: [])
    with pytest.raises(RuntimeError, match="results for 1"):
        FootballDetector(config, model=model).detect_many([np.zeros((8, 8, 3))])


def test_detector_does_not_hide_model_errors(config):
    class Model:
        names: ClassVar[dict[int, str]] = {}

        def predict(self, *args, **kwargs):
            raise RuntimeError("model weights invalid")

    with pytest.raises(RuntimeError, match="weights invalid"):
        FootballDetector(config, model=Model()).detect_many([np.zeros((8, 8, 3))] * 2)


def test_missing_ball_specialist_does_not_block_players(config, tmp_path):
    config.detection.ball_model = str(tmp_path / "missing-ball.pt")
    config.detection.ball_tiles = False

    class Model:
        names = {0: "person"}

        def predict(self, frames, **kwargs):
            boxes = SimpleNamespace(
                xyxy=np.array([[4, 4, 20, 40]]),
                conf=np.array([0.9]),
                cls=np.array([0]),
                id=None,
            )
            return [result(boxes)]

    detector = FootballDetector(config, Model())
    found = detector.detect(np.zeros((48, 48, 3), dtype=np.uint8))
    assert [item.role for item in found] == [Role.PLAYER]
    assert detector.ball_model_skipped.endswith("missing-ball.pt")


def test_ball_rescue_tile_restores_source_coordinates(config):
    config.detection.ball_tiles = True
    config.detection.image_size = 640
    calls = 0

    class Model:
        names = {1: 'ball'}

        def predict(self, frames, **kwargs):
            nonlocal calls
            calls += 1
            boxes = SimpleNamespace(xyxy=np.array([[10, 20, 16, 26]]),
                                    conf=np.array([.8]), cls=np.array([1]), id=None)
            # Call 1 is the full frame; call 2 is the four rescue tiles in one batch.
            return [result(boxes if calls == 2 and index == 3 else None)
                    for index in range(len(frames))]

    detections = FootballDetector(config, Model()).detect(np.zeros((1000, 2000, 3)))
    assert len(detections) == 1
    assert detections[0].bbox.as_xyxy() == (810, 420, 816, 426)
