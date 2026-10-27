from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core.config import AppConfig

Array = np.ndarray


def order_quad(points: Array) -> Array:
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    by_y = pts[np.argsort(pts[:, 1])]
    near = by_y[2:][np.argsort(by_y[2:, 0])]
    far = by_y[:2][np.argsort(by_y[:2, 0])]
    return np.stack([near[0], near[1], far[1], far[0]])


def pitch_template(length_m: float, width_m: float) -> Array:
    return np.array(
        [(0.0, 0.0), (length_m, 0.0), (length_m, width_m), (0.0, width_m)],
        dtype=np.float32,
    )


@dataclass
class PitchMapper:
    length_m: float
    width_m: float
    matrix: Array | None = None
    inverse: Array | None = None
    image_points: Array | None = None
    frame_width: int = 0
    frame_height: int = 0
    estimated: bool = False
    support_polygon: Array | None = None
    calibration_source: str = "manual"
    quality: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_points(
        cls,
        points: list[tuple[float, float]],
        config: AppConfig,
        frame_width: int,
        frame_height: int,
        *,
        normalized: bool = True,
    ) -> PitchMapper:
        import cv2

        pts = np.asarray(points, dtype=np.float32)
        if pts.shape != (4, 2):
            raise ValueError("Calibration requires exactly four pitch corners.")
        if not np.isfinite(pts).all():
            raise ValueError("Calibration corners must be finite.")
        if normalized:
            if np.any(pts < 0) or np.any(pts > 1):
                raise ValueError(
                    "Normalized calibration corners must be between 0 and 1."
                )
            pts = pts * np.array([frame_width, frame_height], dtype=np.float32)
        contour = np.ascontiguousarray(pts.reshape(-1, 1, 2))
        area = abs(cv2.contourArea(contour))
        min_area = max(1.0, frame_width * frame_height * 0.005)
        if not cv2.isContourConvex(contour) or area < min_area:
            raise ValueError(
                "Calibration corners must form a non-degenerate convex quadrilateral in order."
            )
        world = pitch_template(config.pitch.length_m, config.pitch.width_m)
        matrix = cv2.getPerspectiveTransform(pts, world)
        inverse = cv2.getPerspectiveTransform(world, pts)
        return cls(
            length_m=config.pitch.length_m,
            width_m=config.pitch.width_m,
            matrix=matrix,
            inverse=inverse,
            image_points=pts,
            frame_width=frame_width,
            frame_height=frame_height,
        )

    @classmethod
    def from_matrix(
        cls, matrix: Array, config: AppConfig, frame_width: int, frame_height: int
    ) -> PitchMapper:
        import cv2

        inverse = np.linalg.inv(matrix)
        return cls(
            length_m=config.pitch.length_m,
            width_m=config.pitch.width_m,
            matrix=np.asarray(matrix, dtype=np.float64),
            inverse=inverse if inverse is not None else cv2.invert(matrix)[1],
            frame_width=frame_width,
            frame_height=frame_height,
        )

    @property
    def calibrated(self) -> bool:
        return self.matrix is not None and not self.estimated

    def to_world(self, x: float, y: float) -> tuple[float, float] | None:
        if self.support_polygon is not None:
            import cv2

            if cv2.pointPolygonTest(self.support_polygon, (x, y), True) < -self.frame_width * 0.08:
                return None
        if self.matrix is None:
            if self.frame_width and self.frame_height:
                return (
                    x / self.frame_width * self.length_m,
                    y / self.frame_height * self.width_m,
                )
            return None
        point = np.array([x, y, 1.0], dtype=np.float64)
        projected = self.matrix @ point
        if abs(projected[2]) < 1e-9:
            return None
        east, north = (
            float(projected[0] / projected[2]),
            float(projected[1] / projected[2]),
        )
        if -4 <= east <= self.length_m + 4 and -4 <= north <= self.width_m + 4:
            return east, north
        return None

    def to_pixel(self, x: float, y: float) -> tuple[float, float] | None:
        if self.inverse is None:
            return None
        point = np.array([x, y, 1.0], dtype=np.float64)
        projected = self.inverse @ point
        if abs(projected[2]) < 1e-9:
            return None
        return float(projected[0] / projected[2]), float(projected[1] / projected[2])


def trusted_visible_pitch(frame: Array, config: AppConfig) -> PitchMapper | None:
    """Use the visible grass quadrilateral as hali-saha metric calibration.

    A lineup graphic, a small patch of grass, or a mask that fills the whole
    picture is rejected. The whole picture is not the pitch: the goals sit
    inside it, so mapping the frame border to the goal lines cannot count a goal.
    """
    import cv2

    points = detect_visible_pitch(frame)
    if points is None:
        return None
    quad = np.asarray(points, dtype=np.float32)
    span = float(quad[:, 0].max() - quad[:, 0].min())
    span_y = float(quad[:, 1].max() - quad[:, 1].min())
    area = abs(float(cv2.contourArea(quad)))
    if span < 0.85 or area < 0.45 or (span > 0.97 and span_y > 0.97):
        return None
    height, width = frame.shape[:2]
    try:
        mapper = PitchMapper.from_points(points, config, width, height)
    except ValueError:
        return None
    mapper.calibration_source = "visible-pitch"
    mapper.support_polygon = (quad * np.array([width, height], dtype=np.float32)).reshape(-1, 1, 2)
    return mapper


def detect_visible_pitch(frame: Array) -> list[tuple[float, float]] | None:
    import cv2

    # Output is normalized, so the mask can be built on a downscaled frame.
    scale = min(1.0, 480 / frame.shape[1])
    if scale < 1.0:
        frame = cv2.resize(
            frame,
            (max(1, round(frame.shape[1] * scale)), max(1, round(frame.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )
    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (28, 35, 25), (95, 255, 255))
    kernel = max(3, round(21 * scale) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((kernel, kernel), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < mask.size * 0.12:
        return None
    box = cv2.boxPoints(cv2.minAreaRect(largest))
    box[:, 0] = np.clip(box[:, 0], 0, width - 1)
    box[:, 1] = np.clip(box[:, 1], 0, height - 1)
    ordered = order_quad(box)
    return [(float(x / width), float(y / height)) for x, y in ordered]


def pitch_outline(frame: Array) -> Array | None:
    """Visible grass outline for rejecting spectators and technical-area staff.

    This is a foreground mask, not metric calibration. When grass cannot be
    identified (indoor/artificial courts), leave detections unfiltered.
    """
    import cv2

    height, width = frame.shape[:2]
    scale = min(1.0, 480 / width)
    small = cv2.resize(
        frame, (max(1, round(width * scale)), max(1, round(height * scale)))
    )
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (28, 35, 25), (95, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < mask.size * 0.12:
        return None
    return cv2.convexHull(largest).astype(np.float32) / scale
