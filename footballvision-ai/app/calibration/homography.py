from __future__ import annotations

from dataclasses import dataclass

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
        if normalized:
            pts = pts * np.array([frame_width, frame_height], dtype=np.float32)
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
        return self.matrix is not None

    def to_world(self, x: float, y: float) -> tuple[float, float] | None:
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
        east, north = float(projected[0] / projected[2]), float(projected[1] / projected[2])
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


def detect_visible_pitch(frame: Array) -> list[tuple[float, float]] | None:
    import cv2

    height, width = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (28, 35, 25), (95, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
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
