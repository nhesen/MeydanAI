import cv2
import numpy as np
import pytest

from app.calibration.camera import CameraCompensator


def test_auto_camera_can_start_panning_after_initial_static_frames():
    rng = np.random.default_rng(3)
    frame = rng.integers(0, 256, (180, 320, 3), dtype=np.uint8)
    camera = CameraCompensator(mode="auto")
    for _ in range(16):
        camera.update(frame.copy(), [])
    moved = cv2.warpAffine(frame, np.float32([[1, 0, 3], [0, 1, 0]]), (320, 180))
    camera.update(moved, [])
    assert camera.enabled
    assert camera.warp_point(103, 80)[0] == pytest.approx(100, abs=0.5)


def test_camera_feature_loss_preserves_reference_offset():
    camera = CameraCompensator(enabled=True, mode="on")
    camera._dx = 21
    camera._recover(
        np.zeros((32, 32), dtype=np.uint8), np.ones((32, 32), dtype=np.uint8), "lost"
    )
    assert camera.warp_point(100, 50) == (79, 50)


def test_fixed_camera_still_detects_a_scene_cut():
    camera = CameraCompensator(mode="off")
    camera.update(np.zeros((100, 200, 3), dtype=np.uint8), [])
    camera.update(np.full((100, 200, 3), 255, dtype=np.uint8), [])
    assert camera.scene_cut
