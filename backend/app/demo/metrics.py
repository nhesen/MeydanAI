"""Measured track statistics. Unknown physical units remain null."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel, Field, model_validator


class Calibration(BaseModel):
    # Correspond to (0,0), (length,0), (length,width), (0,width).
    # Empty points means the first video frame should detect the visible pitch.
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=4)
    length_m: float = Field(gt=1, le=150, allow_inf_nan=False)
    width_m: float = Field(gt=1, le=100, allow_inf_nan=False)
    fixed_camera: bool
    compensate_camera: bool = False
    homography: list[list[float]] | None = None
    frame_width: int | None = Field(default=None, gt=0)
    frame_height: int | None = Field(default=None, gt=0)
    source: str = "manual"

    @model_validator(mode="after")
    def validate_geometry(self) -> Calibration:
        if not self.fixed_camera and not self.compensate_camera:
            raise ValueError("Metric calibration requires a fixed camera without cuts or zoom.")
        if self.fixed_camera and self.compensate_camera:
            raise ValueError("Select either fixed camera or experimental camera compensation.")
        if self.homography is not None:
            matrix = np.asarray(self.homography, dtype=np.float64)
            if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
                raise ValueError("Pitch homography must be a finite 3x3 matrix.")
            if self.frame_width is None or self.frame_height is None:
                raise ValueError("Pitch homography requires the video frame size.")
            return self
        if len(self.points) not in {0, 4}:
            raise ValueError(
                "Select four distinct corners, or leave them empty for automatic detection."
            )
        if not self.points:
            return self
        if any(not math.isfinite(v) or not 0 <= v <= 1 for p in self.points for v in p):
            raise ValueError("Calibration points must be finite normalized image coordinates.")
        polygon = np.array(self.points, dtype=np.float32)
        if not cv2.isContourConvex(polygon) or cv2.contourArea(polygon) < 0.005:
            raise ValueError("Select four distinct corners in perimeter order, without crossing.")
        return self

    def matrix(self) -> np.ndarray[Any, Any]:
        if self.homography is not None:
            return np.asarray(self.homography, dtype=np.float64)
        return cv2.getPerspectiveTransform(
            np.array(self.points, dtype=np.float32),
            np.array(
                [(0, 0), (self.length_m, 0), (self.length_m, self.width_m), (0, self.width_m)],
                dtype=np.float32,
            ),
        )


def ground_point(
    x: float, y: float, calibration: Calibration | None, matrix: np.ndarray[Any, Any] | None
) -> tuple[float, float] | None:
    if calibration is None or matrix is None:
        return None
    if calibration.homography is not None:
        pixel = np.array(
            [x * float(calibration.frame_width), y * float(calibration.frame_height), 1.0]
        )
        projected = matrix @ pixel
        if abs(projected[2]) < 1e-9:
            return None
        east, north = float(projected[0] / projected[2]), float(projected[1] / projected[2])
        if (
            -2.5 <= east <= calibration.length_m + 2.5
            and -2.5 <= north <= calibration.width_m + 2.5
        ):
            return east, north
        return None
    polygon = np.array(calibration.points, dtype=np.float32)
    # Small margin keeps players whose feet sit on the touchline.
    if cv2.pointPolygonTest(polygon, (x, y), True) < -0.02:
        return None
    projected = matrix @ np.array([x, y, 1.0])
    if abs(projected[2]) < 1e-9:
        return None
    return float(projected[0] / projected[2]), float(projected[1] / projected[2])


def summarize_track(
    track_id: int,
    samples: list[dict[str, Any]],
    detected_frames: int,
    fps: float,
    calibrated: bool,
) -> dict[str, Any]:
    distance = 0.0
    measured_seconds = 0.0
    speeds: list[float] = []
    rejected = 0
    previous: dict[str, Any] | None = None
    # Samples are spaced at least 0.4 s apart, avoiding frame-to-frame box jitter.
    for sample in samples:
        if sample["ground"] is None:
            previous = None
            continue
        if previous is not None:
            dt = sample["t"] - previous["t"]
            if 0 < dt <= 0.65 and sample.get("segment") == previous.get("segment"):
                step = math.dist(previous["ground"], sample["ground"])
                speed = step / dt * 3.6
                # Exclude impossible jumps, never clamp them into believable numbers.
                if speed <= 45:
                    distance += step
                    measured_seconds += dt
                    speeds.append(speed)
                else:
                    rejected += 1
        previous = sample
    available = calibrated and measured_seconds > 0
    return {
        "track_id": track_id,
        "first_seen_s": round(samples[0]["t"], 3),
        "last_seen_s": round(samples[-1]["t"], 3),
        "visible_seconds": round(detected_frames / fps, 2),
        "detections": detected_frames,
        "mean_confidence": round(sum(s["confidence"] for s in samples) / len(samples), 3),
        "measured_seconds": round(measured_seconds, 2),
        "distance_m": round(distance, 2) if available else None,
        "avg_speed_kmh": round(distance / measured_seconds * 3.6, 2) if available else None,
        "max_speed_kmh": round(max(speeds), 2) if available else None,
        "rejected_jumps": rejected,
        "samples": samples,
    }
