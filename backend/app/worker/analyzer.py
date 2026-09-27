from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

import cv2
import numpy as np

from app.core.analytics_bounds import (
    MAX_AVG_KMH,
    MAX_PLAUSIBLE_STEP_KMH,
    MAX_PLAYER_KMH,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    SPRINT_KMH,
    STANDING_KMH,
    intensity_from_positions,
    reconstruct_display_path,
)

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
    rating: float
    distance_m: float
    avg_speed_kmh: float
    max_speed_kmh: float
    sprint_count: int
    active_seconds: int
    activity_count: int
    peak_speed_at_ms: int | None
    intensity: list[tuple[int, int, float]]
    events: list[tuple[str, int, float | None, str]]
    frame_width: int
    frame_height: int


def analyze_video(path: Path) -> list[PlayerMotionResult]:
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
    return [item for item in results if item.distance_m > 0 and len(item.positions) >= 2]


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
    raw_samples = _downsample(track.samples)
    display = reconstruct_display_path(raw_samples)
    samples = _smooth_path(_plausible_path(raw_samples))
    distance_m = 0.0
    speeds: list[tuple[int, float]] = []
    for previous, current in pairwise(samples):
        dt = max(current.timestamp_ms - previous.timestamp_ms, 1) / 1000
        raw_kmh = _step_kmh(previous, current, dt)
        if raw_kmh > MAX_PLAUSIBLE_STEP_KMH:
            continue
        speed = 0.0 if raw_kmh < STANDING_KMH else min(raw_kmh, MAX_PLAYER_KMH)
        distance_m += (speed / 3.6) * dt
        speeds.append((current.timestamp_ms, speed))

    duration_ms = (samples[-1].timestamp_ms - samples[0].timestamp_ms) if len(samples) > 1 else 0
    duration_s = max(duration_ms / 1000, 1.0)
    max_speed = min(max((speed for _, speed in speeds), default=0.0), MAX_PLAYER_KMH)
    avg_speed = min((distance_m / duration_s) * 3.6, MAX_AVG_KMH)
    sprint_count = _sprint_bursts(speeds)
    peak_at = next((stamp for stamp, speed in speeds if speed == max_speed), None)
    intensity = intensity_from_positions(display) or _intensity_buckets(speeds, duration_ms)
    events: list[tuple[str, int, float | None, str]] = []
    if peak_at is not None and max_speed > 0:
        events.append(("peak_speed", peak_at, round(max_speed, 1), "Peak recorded speed"))
    events.extend(_sprint_events(speeds))

    meters_per_minute = distance_m / (duration_s / 60)
    rating = max(
        4.2,
        min(
            9.4,
            round(
                5.0
                + min(2.0, meters_per_minute / 70)
                + min(1.4, max(0.0, max_speed - 18) / 12)
                + min(1.0, sprint_count / 4),
                1,
            ),
        ),
    )
    return PlayerMotionResult(
        track_id=track.track_id,
        positions=display or samples,
        rating=rating,
        distance_m=round(distance_m, 1),
        avg_speed_kmh=round(avg_speed, 1),
        max_speed_kmh=round(max_speed, 1),
        sprint_count=sprint_count,
        active_seconds=max(1, duration_ms // 1000),
        activity_count=len(samples),
        peak_speed_at_ms=peak_at,
        intensity=intensity,
        events=events,
        frame_width=width,
        frame_height=height,
    )


def _step_kmh(previous: TrackSample, current: TrackSample, dt: float) -> float:
    dx = (current.x - previous.x) * PITCH_LENGTH_M
    dy = (current.y - previous.y) * PITCH_WIDTH_M
    return float((((dx * dx + dy * dy) ** 0.5) / dt) * 3.6)


def _plausible_path(samples: list[TrackSample]) -> list[TrackSample]:
    if not samples:
        return []
    kept = [samples[0]]
    for sample in samples[1:]:
        previous = kept[-1]
        dt = max(sample.timestamp_ms - previous.timestamp_ms, 1) / 1000
        if _step_kmh(previous, sample, dt) <= MAX_PLAUSIBLE_STEP_KMH:
            kept.append(sample)
    return kept


def _smooth_path(samples: list[TrackSample]) -> list[TrackSample]:
    if len(samples) < 3:
        return samples
    smoothed = [samples[0]]
    for index in range(1, len(samples) - 1):
        window = samples[index - 1 : index + 2]
        smoothed.append(
            TrackSample(
                timestamp_ms=samples[index].timestamp_ms,
                x=sum(item.x for item in window) / len(window),
                y=sum(item.y for item in window) / len(window),
            )
        )
    smoothed.append(samples[-1])
    return smoothed


def _sprint_events(
    speeds: list[tuple[int, float]],
    limit: int = 8,
) -> list[tuple[str, int, float | None, str]]:
    events: list[tuple[str, int, float | None, str]] = []
    in_burst = False
    for stamp, speed in speeds:
        if speed < SPRINT_KMH:
            in_burst = False
            continue
        if in_burst:
            continue
        in_burst = True
        if len(events) < limit:
            events.append(("sprint", stamp, round(speed, 1), "Sprint"))
    return events


def _sprint_bursts(speeds: list[tuple[int, float]]) -> int:
    bursts = 0
    active = False
    streak = 0
    for _, speed in speeds:
        if speed >= SPRINT_KMH:
            streak += 1
            if not active and streak >= 2:
                bursts += 1
                active = True
        else:
            active = False
            streak = 0
    return bursts


def _intensity_buckets(
    speeds: list[tuple[int, float]],
    duration_ms: int,
) -> list[tuple[int, int, float]]:
    if not speeds:
        return []
    buckets: dict[int, list[float]] = {}
    for stamp, speed in speeds:
        minute = stamp // 60_000
        buckets.setdefault(minute, []).append(speed)
    last_minute = max(duration_ms // 60_000, max(buckets))
    result: list[tuple[int, int, float]] = []
    for minute in range(last_minute + 1):
        values = buckets.get(minute, [])
        intensity = (
            min(100.0, (sum(values) / len(values) / MAX_PLAYER_KMH) * 100) if values else 0.0
        )
        result.append((minute, minute + 1, round(intensity, 1)))
    return result


def _downsample(samples: list[TrackSample]) -> list[TrackSample]:
    if len(samples) <= MAX_POSITION_SAMPLES:
        return samples
    step = len(samples) / MAX_POSITION_SAMPLES
    return [
        samples[min(len(samples) - 1, int(index * step))] for index in range(MAX_POSITION_SAMPLES)
    ]


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
