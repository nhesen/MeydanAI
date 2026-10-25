from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.analytics_bounds import reconstruct_display_path

MAX_POSITION_SAMPLES = 2500


@dataclass
class TrackSample:
    timestamp_ms: int
    x: float
    y: float


@dataclass
class MotionTrack:
    track_id: str
    samples: list[TrackSample] = field(default_factory=list)
    misses: int = 0

    @property
    def median_x(self) -> float:
        values = [sample.x for sample in self.samples]
        return float(np.median(values)) if values else 0.5


@dataclass(frozen=True)
class PlayerMotionResult:
    track_id: str
    positions: list[TrackSample]
    rating: float | None
    distance_m: float | None
    avg_speed_kmh: float | None
    max_speed_kmh: float | None
    sprint_count: int | None
    active_seconds: int
    activity_count: int
    peak_speed_at_ms: int | None
    intensity: list[tuple[int, int, float]]
    events: list[tuple[str, int, float | None, str]]
    frame_width: int
    frame_height: int
    team: str | None = None
    jersey_number: int | None = None
    calibration: dict[str, Any] | None = None
    event_media: dict[int, dict[str, Any]] = field(default_factory=dict)
    track_evidence: dict[str, Any] | None = None


def analyze_video(path: Path) -> list[PlayerMotionResult]:
    """Production path is FootballVision. Motion blobs stay only as an explicit fallback."""
    mode = os.environ.get("FOOTBALLVISION_ENABLED", "auto").strip().lower()
    if mode in {"0", "false", "no", "motion"}:
        return analyze_video_motion(path)
    from app.worker.footballvision import analyze_with_footballvision

    return analyze_with_footballvision(path)


def analyze_video_motion(path: Path) -> list[PlayerMotionResult]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("VIDEO_UNREADABLE")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        capture.release()
        raise ValueError("VIDEO_UNREADABLE")

    sample_stride = max(1, round(fps / 4))
    subtractor = cv2.createBackgroundSubtractorMOG2(
        history=300,
        varThreshold=16,
        detectShadows=True,
    )
    active: dict[int, MotionTrack] = {}
    next_track_id = 1
    finished: list[MotionTrack] = []
    frame_index = 0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            working = _downscale(frame)
            if frame_index % sample_stride != 0:
                subtractor.apply(working)
                frame_index += 1
                continue
            timestamp_ms = int(frame_index / fps * 1000)
            detections = _detect_blobs(subtractor, working)
            active, retired, next_track_id = _associate(
                active,
                detections,
                timestamp_ms,
                next_track_id,
            )
            finished.extend(retired)
            frame_index += 1
    finally:
        capture.release()

    finished.extend(active.values())
    usable = [track for track in finished if len(track.samples) >= 2]
    results = [_metrics_for_track(track, width, height) for track in usable]
    return [item for item in results if len(item.positions) >= 2]


def _detect_blobs(
    subtractor: cv2.BackgroundSubtractor,
    frame: np.ndarray,
) -> list[tuple[float, float]]:
    mask = subtractor.apply(frame)
    _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    height, width = frame.shape[:2]
    min_area = max(18.0, width * height * 0.00018)
    max_area = width * height * 0.12
    points: list[tuple[float, float]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        cx = (x + w / 2) / width
        cy = (y + h / 2) / height
        points.append((_clamp01(cx), _clamp01(cy)))
    return points[:22]


def _associate(
    active: dict[int, MotionTrack],
    detections: list[tuple[float, float]],
    timestamp_ms: int,
    next_track_id: int,
) -> tuple[dict[int, MotionTrack], list[MotionTrack], int]:
    unused = set(range(len(detections)))
    for _track_id, track in active.items():
        last = track.samples[-1]
        best_index = None
        best_distance = 0.07
        for index in unused:
            dx = detections[index][0] - last.x
            dy = detections[index][1] - last.y
            distance = (dx * dx + dy * dy) ** 0.5
            if distance < best_distance:
                best_distance = distance
                best_index = index
        if best_index is None:
            track.misses += 1
            continue
        x, y = detections[best_index]
        track.misses = 0
        track.samples.append(TrackSample(timestamp_ms=timestamp_ms, x=x, y=y))
        unused.remove(best_index)

    retired = [track for track in active.values() if track.misses > 4]
    remaining = {track_id: track for track_id, track in active.items() if track.misses <= 4}
    for index in unused:
        if len(remaining) >= 22:
            break
        x, y = detections[index]
        remaining[next_track_id] = MotionTrack(
            track_id=f"track-{next_track_id}",
            samples=[TrackSample(timestamp_ms=timestamp_ms, x=x, y=y)],
        )
        next_track_id += 1
    return remaining, retired, next_track_id


def _downscale(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    if width <= 960:
        return frame
    scale = 960 / width
    return cv2.resize(frame, (960, max(1, int(height * scale))))


def _metrics_for_track(track: MotionTrack, width: int, height: int) -> PlayerMotionResult:
    """Blob tracks are image positions. They are not a measured pitch."""
    samples = reconstruct_display_path(_downsample(track.samples))
    duration_ms = samples[-1].timestamp_ms - samples[0].timestamp_ms if len(samples) > 1 else 0
    return PlayerMotionResult(
        track_id=track.track_id,
        positions=samples,
        rating=None,
        distance_m=None,
        avg_speed_kmh=None,
        max_speed_kmh=None,
        sprint_count=None,
        active_seconds=max(1, duration_ms // 1000) if samples else 0,
        activity_count=len(samples),
        peak_speed_at_ms=None,
        intensity=[],
        events=[],
        frame_width=width,
        frame_height=height,
        calibration={
            "version": "motion-blobs",
            "source_frame_width": width,
            "source_frame_height": height,
            "transform_metadata": {
                "method": "relative",
                "calibrated": False,
                "physical_metrics_available": False,
            },
        },
    )


def _downsample(samples: list[TrackSample]) -> list[TrackSample]:
    if len(samples) <= MAX_POSITION_SAMPLES:
        return samples
    step = len(samples) / MAX_POSITION_SAMPLES
    return [
        samples[min(len(samples) - 1, int(index * step))] for index in range(MAX_POSITION_SAMPLES)
    ]


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
