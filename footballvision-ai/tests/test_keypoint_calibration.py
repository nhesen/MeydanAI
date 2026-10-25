import cv2
import numpy as np
import pytest

from app.calibration.keypoints import fit_keypoints, pitch_vertices
from app.core.config import AppConfig, PitchConfig, with_video_calibration


@pytest.fixture
def full_pitch_config():
    return AppConfig(pitch=PitchConfig(mode="11v11", length_m=105, width_m=68))


def projected_landmarks():
    transform = np.array([[10.0, 1.0, 200], [0.0, -8.0, 800], [0.001, 0.0005, 1.0]])
    points = cv2.perspectiveTransform(pitch_vertices().reshape(-1, 1, 2), transform).reshape(-1, 2)
    return points, transform


def test_keypoint_fit_recovers_metric_coordinates_and_rejects_outliers(full_pitch_config):
    points, transform = projected_landmarks()
    points[:5] += 120
    fitted = fit_keypoints(points, np.ones(32), full_pitch_config, 1920, 1080)
    assert fitted.mapper is not None
    assert fitted.quality["valid"]
    assert fitted.quality["inlier_count"] >= 26
    assert fitted.quality["reprojection_rmse_px"] < 0.01
    image = cv2.perspectiveTransform(np.array([[[52.5, 34]]], dtype=np.float32), transform)[0, 0]
    assert fitted.mapper.to_world(*image) == pytest.approx((52.5, 34), abs=0.02)


def test_keypoint_fit_rejects_collinear_landmarks(full_pitch_config):
    points = np.stack([np.linspace(100, 1700, 32), np.full(32, 500)], axis=1)
    fitted = fit_keypoints(points, np.ones(32), full_pitch_config, 1920, 1080)
    assert fitted.mapper is None
    assert not fitted.quality["valid"]


def test_keypoint_template_never_used_for_small_pitch(config):
    points, _ = projected_landmarks()
    fitted = fit_keypoints(points, np.ones(32), config, 1920, 1080)
    assert fitted.mapper is None
    assert fitted.quality["reason"] == "11v11_template_not_selected"


def test_keypoint_fit_rejects_wrong_landmark_correspondences(full_pitch_config):
    points, _ = projected_landmarks()
    shuffled = points[np.random.default_rng(19).permutation(32)]
    fitted = fit_keypoints(shuffled, np.ones(32), full_pitch_config, 1920, 1080)
    assert fitted.mapper is None


def test_relative_mode_clears_global_manual_points(config):
    config.raw = {"calibration": {"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}}
    configured = with_video_calibration(config, {"mode": "relative"})
    assert configured.raw["calibration"]["points"] == []
    assert config.raw["calibration"]["points"]


def test_automatic_mode_requires_explicit_11v11_and_sets_matching_dimensions(config):
    with pytest.raises(ValueError, match="11v11"):
        with_video_calibration(config, {"mode": "automatic"})
    configured = with_video_calibration(config, {"mode": "automatic", "pitch_mode": "11v11"})
    assert (configured.pitch.length_m, configured.pitch.width_m) == (105, 68)


@pytest.mark.parametrize("payload", [
    {"mode": "manual", "points": [[0, 0]]},
    {"mode": "relative", "length_m": float("nan")},
    {"mode": "manual", "points": [[0, 0], [1, 0], [1, 1], [0, 2]]},
])
def test_invalid_per_video_calibration_rejected(config, payload):
    with pytest.raises(ValueError):
        with_video_calibration(config, payload)
