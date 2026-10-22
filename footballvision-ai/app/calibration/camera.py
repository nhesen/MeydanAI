from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

Array = np.ndarray


@dataclass
class CameraCompensator:
    """Optical-flow homography that maps the current frame back to the first frame."""

    enabled: bool = False
    previous: Array | None = None
    mask: Array | None = None
    current_to_reference: Array = field(default_factory=lambda: np.eye(3, dtype=np.float64))
    valid: bool = True
    reason: str | None = None

    def warp_point(self, x: float, y: float, scale: float = 1.0) -> tuple[float, float]:
        if not self.enabled or not self.valid:
            return x, y
        point = np.array([x * scale, y * scale, 1.0], dtype=np.float64)
        projected = np.linalg.inv(self.current_to_reference) @ point
        if abs(projected[2]) < 1e-9:
            return x, y
        return float(projected[0] / projected[2] / scale), float(projected[1] / projected[2] / scale)

    def update(self, frame: Array, boxes: list[tuple[float, float, float, float]]) -> bool:
        if not self.enabled:
            return True
        import cv2

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
            self.previous, maxCorners=400, qualityLevel=0.01, minDistance=10, mask=self.mask
        )
        if points is None or len(points) < 20:
            return self._fail("insufficient_background_features")
        moved, status, _ = cv2.calcOpticalFlowPyrLK(self.previous, gray, points, points.copy())
        if moved is None or status is None:
            return self._fail("optical_flow_failed")
        good = status.ravel() == 1
        a, b = points.reshape(-1, 2)[good], moved.reshape(-1, 2)[good]
        if len(a) < 20:
            return self._fail("insufficient_consistent_features")
        matrix, mask = cv2.findHomography(a, b, cv2.RANSAC, 2.5)
        if matrix is None or mask is None or int(mask.sum()) < 18:
            return self._fail("homography_failed")
        if not np.isfinite(matrix).all():
            return self._fail("unstable_camera_transform")
        self.current_to_reference = matrix @ self.current_to_reference
        self.previous, self.mask = gray, new_mask
        return True

    def _fail(self, reason: str) -> bool:
        self.valid = False
        self.reason = reason
        return False
