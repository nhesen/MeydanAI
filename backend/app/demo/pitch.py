"""FIFA pitch template and keypoint homography. Coordinates are metres."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.demo.metrics import Calibration

LENGTH_M = 105.0
WIDTH_M = 68.0
PENALTY_BOX_WIDTH = 40.32
PENALTY_BOX_LENGTH = 16.5
GOAL_BOX_WIDTH = 18.32
GOAL_BOX_LENGTH = 5.5
CENTRE_CIRCLE_RADIUS = 9.15
PENALTY_SPOT = 11.0

Array = np.ndarray[Any, Any]


def pitch_vertices(length_m: float = LENGTH_M, width_m: float = WIDTH_M) -> Array:
    """32 pitch landmarks matching the Roboflow soccer keypoint model order."""
    pb_w, pb_l = PENALTY_BOX_WIDTH, PENALTY_BOX_LENGTH
    gb_w, gb_l = GOAL_BOX_WIDTH, GOAL_BOX_LENGTH
    return np.array(
        [
            (0, 0),
            (0, (width_m - pb_w) / 2),
            (0, (width_m - gb_w) / 2),
            (0, (width_m + gb_w) / 2),
            (0, (width_m + pb_w) / 2),
            (0, width_m),
            (gb_l, (width_m - gb_w) / 2),
            (gb_l, (width_m + gb_w) / 2),
            (PENALTY_SPOT, width_m / 2),
            (pb_l, (width_m - pb_w) / 2),
            (pb_l, (width_m - gb_w) / 2),
            (pb_l, (width_m + gb_w) / 2),
            (pb_l, (width_m + pb_w) / 2),
            (length_m / 2, 0),
            (length_m / 2, width_m / 2 - CENTRE_CIRCLE_RADIUS),
            (length_m / 2, width_m / 2 + CENTRE_CIRCLE_RADIUS),
            (length_m / 2, width_m),
            (length_m - pb_l, (width_m - pb_w) / 2),
            (length_m - pb_l, (width_m - gb_w) / 2),
            (length_m - pb_l, (width_m + gb_w) / 2),
            (length_m - pb_l, (width_m + pb_w) / 2),
            (length_m - PENALTY_SPOT, width_m / 2),
            (length_m - gb_l, (width_m - gb_w) / 2),
            (length_m - gb_l, (width_m + gb_w) / 2),
            (length_m, 0),
            (length_m, (width_m - pb_w) / 2),
            (length_m, (width_m - gb_w) / 2),
            (length_m, (width_m + gb_w) / 2),
            (length_m, (width_m + pb_w) / 2),
            (length_m, width_m),
            (length_m / 2 - CENTRE_CIRCLE_RADIUS, width_m / 2),
            (length_m / 2 + CENTRE_CIRCLE_RADIUS, width_m / 2),
        ],
        dtype=np.float32,
    )


def homography_from_keypoints(
    image_points: Array,
    scores: Array | None = None,
    *,
    min_points: int = 6,
    min_confidence: float = 0.45,
) -> Array | None:
    """Pixel → metre homography from visible pitch landmarks."""
    import cv2

    vertices = pitch_vertices()
    points = np.asarray(image_points, dtype=np.float32).reshape(-1, 2)
    if len(points) != len(vertices):
        return None
    visible = (points[:, 0] > 1) & (points[:, 1] > 1)
    if scores is not None:
        visible &= np.asarray(scores, dtype=np.float32).reshape(-1) >= min_confidence
    if int(visible.sum()) < min_points:
        return None
    matrix, mask = cv2.findHomography(
        points[visible], vertices[visible], method=cv2.RANSAC, ransacReprojThreshold=8.0
    )
    if matrix is None or mask is None or int(mask.sum()) < min_points:
        return None
    if not np.isfinite(matrix).all():
        return None
    return np.asarray(matrix, dtype=np.float64)


def calibration_from_keypoint_result(
    result: Any, frame_width: int, frame_height: int
) -> Calibration | None:
    keypoints = getattr(result, "keypoints", None)
    if keypoints is None or getattr(keypoints, "xy", None) is None:
        return None
    xy = keypoints.xy
    if xy is None or len(xy) == 0:
        return None
    first = xy[0]
    points = first.detach().cpu().numpy() if hasattr(first, "detach") else np.asarray(first)
    scores = None
    if getattr(keypoints, "conf", None) is not None:
        raw = keypoints.conf[0]
        scores = raw.detach().cpu().numpy() if hasattr(raw, "detach") else np.asarray(raw)
    matrix = homography_from_keypoints(points, scores)
    if matrix is None:
        return None
    return Calibration(
        points=[],
        length_m=LENGTH_M,
        width_m=WIDTH_M,
        fixed_camera=True,
        homography=matrix.tolist(),
        frame_width=frame_width,
        frame_height=frame_height,
        source="pitch-keypoints",
    )
