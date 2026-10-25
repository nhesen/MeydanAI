"""Validated, per-frame metric calibration from the local 32-landmark pose model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.calibration.homography import PitchMapper
from app.core.config import AppConfig
from app.core.device import resolve_device


def pitch_vertices(length_m: float = 105.0, width_m: float = 68.0) -> np.ndarray:
    """Roboflow football-pitch model landmark order for an 11-a-side field."""
    pb, gb = 40.32, 18.32
    return np.array([
        (0, 0), (0, (width_m-pb)/2), (0, (width_m-gb)/2),
        (0, (width_m+gb)/2), (0, (width_m+pb)/2), (0, width_m),
        (5.5, (width_m-gb)/2), (5.5, (width_m+gb)/2), (11, width_m/2),
        (16.5, (width_m-pb)/2), (16.5, (width_m-gb)/2),
        (16.5, (width_m+gb)/2), (16.5, (width_m+pb)/2),
        (length_m/2, 0), (length_m/2, width_m/2-9.15),
        (length_m/2, width_m/2+9.15), (length_m/2, width_m),
        (length_m-16.5, (width_m-pb)/2), (length_m-16.5, (width_m-gb)/2),
        (length_m-16.5, (width_m+gb)/2), (length_m-16.5, (width_m+pb)/2),
        (length_m-11, width_m/2), (length_m-5.5, (width_m-gb)/2),
        (length_m-5.5, (width_m+gb)/2), (length_m, 0),
        (length_m, (width_m-pb)/2), (length_m, (width_m-gb)/2),
        (length_m, (width_m+gb)/2), (length_m, (width_m+pb)/2),
        (length_m, width_m), (length_m/2-9.15, width_m/2),
        (length_m/2+9.15, width_m/2),
    ], dtype=np.float32)


@dataclass
class CalibrationFit:
    mapper: PitchMapper | None
    quality: dict[str, Any]


def fit_keypoints(points: np.ndarray, scores: np.ndarray | None, config: AppConfig,
                  frame_width: int, frame_height: int) -> CalibrationFit:
    quality: dict[str, Any] = {"valid": False, "source": "pitch-keypoints", "reason": "insufficient_landmarks"}
    if config.pitch.mode != "11v11":
        quality["reason"] = "11v11_template_not_selected"
        return CalibrationFit(None, quality)
    if not 90 <= config.pitch.length_m <= 120 or not 45 <= config.pitch.width_m <= 90:
        quality["reason"] = "invalid_11v11_dimensions"
        return CalibrationFit(None, quality)
    points = np.asarray(points, dtype=np.float64)
    if points.shape != (32, 2) or scores is None:
        quality["reason"] = "invalid_keypoint_shape"
        return CalibrationFit(None, quality)
    scores = np.asarray(scores).reshape(-1)
    if len(scores) != 32:
        quality["reason"] = "invalid_confidence_shape"
        return CalibrationFit(None, quality)
    visible = np.isfinite(points).all(axis=1) & np.isfinite(scores) & (scores >= 0.5)
    visible &= (points[:, 0] > 1) & (points[:, 0] < frame_width-1)
    visible &= (points[:, 1] > 1) & (points[:, 1] < frame_height-1)
    quality["visible_points"] = int(visible.sum())
    if int(visible.sum()) < 6:
        return CalibrationFit(None, quality)
    world = pitch_vertices(config.pitch.length_m, config.pitch.width_m)[visible]
    pixels = points[visible].astype(np.float32)
    threshold = max(3.0, np.hypot(frame_width, frame_height) * 0.003)
    # Fit in pixel space: RANSAC's error threshold is pixels, never metres.
    world_to_image, mask = cv2.findHomography(world, pixels, cv2.RANSAC, threshold)
    if world_to_image is None or mask is None or not np.isfinite(world_to_image).all():
        quality["reason"] = "homography_failed"
        return CalibrationFit(None, quality)
    inliers = mask.ravel().astype(bool)
    count = int(inliers.sum())
    ratio = count / len(world)
    quality.update(inlier_count=count, inlier_ratio=round(ratio, 4))
    if count < 6 or ratio < 0.65:
        quality["reason"] = "insufficient_inliers"
        return CalibrationFit(None, quality)
    world, pixels = world[inliers], pixels[inliers]
    image_coverage = abs(cv2.contourArea(cv2.convexHull(pixels))) / (frame_width*frame_height)
    field_coverage = abs(cv2.contourArea(cv2.convexHull(world))) / (config.pitch.length_m*config.pitch.width_m)
    quality.update(frame_coverage=round(image_coverage, 4), pitch_coverage=round(field_coverage, 4))
    if image_coverage < 0.015 or field_coverage < 0.025:
        quality["reason"] = "landmarks_not_spread_in_two_dimensions"
        return CalibrationFit(None, quality)
    reprojection = cv2.perspectiveTransform(world.reshape(-1, 1, 2), world_to_image).reshape(-1, 2)
    errors = np.linalg.norm(reprojection-pixels, axis=1)
    rmse = float(np.sqrt(np.mean(errors**2)))
    quality["reprojection_rmse_px"] = round(rmse, 3)
    quality["max_reprojection_error_px"] = round(float(errors.max()), 3)
    normalizer_image = np.diag([1/frame_width, 1/frame_height, 1.0])
    denormalizer_world = np.diag([config.pitch.length_m, config.pitch.width_m, 1.0])
    condition = float(np.linalg.cond(normalizer_image @ world_to_image @ denormalizer_world))
    if rmse > threshold or not np.isfinite(condition) or condition > 10000:
        quality["reason"] = "unstable_or_inaccurate_transform"
        return CalibrationFit(None, quality)
    try:
        matrix = np.linalg.inv(world_to_image)
    except np.linalg.LinAlgError:
        quality["reason"] = "singular_transform"
        return CalibrationFit(None, quality)
    mapper = PitchMapper.from_matrix(matrix, config, frame_width, frame_height)
    mapper.support_polygon = cv2.convexHull(pixels)
    mapper.calibration_source = "pitch-keypoints"
    quality.update(valid=True, reason=None, normalized_condition=round(condition, 2))
    mapper.quality = quality
    return CalibrationFit(mapper, quality)


class KeypointCalibrator:
    def __init__(self, config: AppConfig, model: Any | None = None) -> None:
        self.config = config
        self._model = model
        self.device = resolve_device(config.detection.device)

    def calibrate(self, frame: np.ndarray) -> CalibrationFit:
        if self._model is None:
            model_path = Path(self.config.detection.pitch_model)
            if model_path.parent != Path(".") and not model_path.is_file():
                return CalibrationFit(None, {
                    "valid": False, "source": "pitch-keypoints", "reason": "pitch_model_missing",
                })
            from ultralytics import YOLO

            self._model = YOLO(self.config.detection.pitch_model)
        result = next(iter(self._model.predict(frame, verbose=False, device=self.device,
                                               imgsz=self.config.detection.image_size)))
        keypoints = getattr(result, "keypoints", None)
        if keypoints is None or getattr(keypoints, "xy", None) is None or len(keypoints.xy) == 0:
            return CalibrationFit(None, {"valid": False, "source": "pitch-keypoints", "reason": "no_keypoints"})
        raw_points, raw_scores = keypoints.xy[0], keypoints.conf[0] if keypoints.conf is not None else None
        points = raw_points.cpu().numpy() if hasattr(raw_points, "cpu") else np.asarray(raw_points)
        scores = raw_scores.cpu().numpy() if hasattr(raw_scores, "cpu") else raw_scores
        height, width = frame.shape[:2]
        return fit_keypoints(points, scores, self.config, width, height)
