"""Experimental propagation of a user's first-frame calibration through camera motion.

Uses background optical flow and a robust homography. A failed link invalidates the
remaining chain: it must never silently return the previous transform as valid.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

Array = np.ndarray[Any, Any]


class CameraRegistration:
    def __init__(self) -> None:
        self.previous: Array | None = None
        self.mask: Array | None = None
        self.current_to_reference = np.eye(3, dtype=np.float64)
        self.valid = True
        self.reason: str | None = None
        self.inliers = 0

    def update(self, frame: Array, boxes: list[list[float]]) -> bool:
        height, width = frame.shape[:2]
        scale = min(1.0, 960 / width)
        gray = cv2.cvtColor(
            cv2.resize(frame, (round(width * scale), round(height * scale))), cv2.COLOR_BGR2GRAY
        )
        new_mask = np.full(gray.shape, 255, np.uint8)
        for x1, y1, x2, y2 in boxes:
            cv2.rectangle(
                new_mask,
                (max(0, round(x1 * scale) - 8), max(0, round(y1 * scale) - 8)),
                (round(x2 * scale) + 8, round(y2 * scale) + 8),
                0,
                -1,
            )
        if self.previous is None:
            self.previous, self.mask = gray, new_mask
            return True
        if not self.valid:
            return False
        points = cv2.goodFeaturesToTrack(
            self.previous, maxCorners=500, qualityLevel=0.01, minDistance=10, mask=self.mask
        )
        if points is None or len(points) < 20:
            return self._fail("insufficient_background_features")
        moved, status, _ = cv2.calcOpticalFlowPyrLK(self.previous, gray, points, points.copy())
        if moved is None or status is None:
            return self._fail("optical_flow_failed")
        backward, back_status, _ = cv2.calcOpticalFlowPyrLK(
            gray, self.previous, moved, moved.copy()
        )
        if backward is None or back_status is None:
            return self._fail("optical_flow_failed")
        good = (status.ravel() == 1) & (back_status.ravel() == 1)
        good &= np.linalg.norm(points.reshape(-1, 2) - backward.reshape(-1, 2), axis=1) < 1.5
        a, b = points.reshape(-1, 2)[good], moved.reshape(-1, 2)[good]
        if len(a) < 20:
            return self._fail("insufficient_consistent_features")
        matrix, mask = cv2.findHomography(a, b, cv2.RANSAC, 2.5)
        if matrix is None or mask is None:
            return self._fail("homography_failed")
        self.inliers = int(mask.sum())
        if self.inliers < 20 or self.inliers / len(a) < 0.65:
            return self._fail("poor_camera_registration")
        matched = a[mask.ravel().astype(bool)]
        if cv2.contourArea(cv2.convexHull(matched)) < gray.size * 0.10:
            return self._fail("background_features_too_local")
        if not np.isfinite(matrix).all() or np.linalg.cond(matrix) > 1e7:
            return self._fail("unstable_camera_transform")
        # A cut can occasionally produce spurious matches; reject implausible jumps/zoom.
        corners = np.array(
            [
                [
                    [0.0, 0.0],
                    [gray.shape[1], 0.0],
                    [gray.shape[1], gray.shape[0]],
                    [0.0, gray.shape[0]],
                ]
            ],
            np.float32,
        )
        warped = cv2.perspectiveTransform(corners, matrix)
        area_ratio = abs(cv2.contourArea(warped)) / gray.size
        if (
            not 0.7 < area_ratio < 1.4
            or np.max(np.linalg.norm(warped - corners, axis=2)) > gray.shape[1] * 0.2
        ):
            return self._fail("camera_cut_or_large_motion")
        # Convert pixel transform to normalized image coordinates before accumulating.
        pixels = np.diag([gray.shape[1], gray.shape[0], 1.0])
        normalized = np.linalg.inv(pixels) @ matrix @ pixels
        self.current_to_reference = self.current_to_reference @ np.linalg.inv(normalized)
        self.current_to_reference /= self.current_to_reference[2, 2]
        if not np.isfinite(self.current_to_reference).all():
            return self._fail("unstable_accumulated_transform")
        self.previous, self.mask = gray, new_mask
        return True

    def _fail(self, reason: str) -> bool:
        self.valid, self.reason = False, reason
        return False

    def reference_point(self, x: float, y: float) -> tuple[float, float] | None:
        if not self.valid:
            return None
        point = self.current_to_reference @ np.array([x, y, 1.0])
        if abs(point[2]) < 1e-9:
            return None
        return float(point[0] / point[2]), float(point[1] / point[2])
