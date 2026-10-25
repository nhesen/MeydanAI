from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

import numpy as np

from app.core.config import AppConfig
from app.core.types import PlayerTrack, TrackSample


@dataclass
class MotionSummary:
    distance_m: float | None
    avg_speed_kmh: float | None
    max_speed_kmh: float | None
    sprint_count: int
    active_seconds: float
    measured_seconds: float
    rejected_jumps: int
    peak_speed_at_s: float | None
    zone_activity: dict[str, float]


def _motion_windows(track: PlayerTrack, config: AppConfig) -> tuple[list[tuple[float, float, float]], int]:
    """Median 0.4-second observations suppress box/keypoint jitter before velocity.

    Never connect metric observations through missing calibration or a long gap.
    Returns (start seconds, end seconds, km/h) intervals.
    """
    segments: list[list[TrackSample]] = []
    current: list[TrackSample] = []
    for sample in track.samples:
        sample.speed_mps = None
        if sample.world is None or not sample.calibrated:
            if current:
                segments.append(current)
            current = []
            continue
        if current and not 0 < sample.time_s-current[-1].time_s <= 0.5:
            segments.append(current)
            current = []
        current.append(sample)
    if current:
        segments.append(current)
    windows: list[tuple[float, float, float]] = []
    rejected = 0
    maximum = config.tracking.max_speed_kmh
    for segment in segments:
        if len(segment) < 2:
            continue
        raw_duration = segment[-1].time_s-segment[0].time_s
        if raw_duration < 0.2:
            first, last = segment[0], segment[-1]
            if raw_duration > 0 and np.hypot(last.world[0]-first.world[0], last.world[1]-first.world[1]) / raw_duration * 3.6 > maximum:
                rejected += 1
            continue
        # Preserve endpoints while representing intermediate 0.4s bins by a robust median.
        bins: dict[int, list[TrackSample]] = defaultdict(list)
        for sample in segment[1:-1]:
            bins[int((sample.time_s-segment[0].time_s)/0.4)].append(sample)
        anchors = [(segment[0].time_s, *segment[0].world)]
        for values in bins.values():
            anchors.append(tuple(float(value) for value in np.median(
                [[item.time_s, *item.world] for item in values], axis=0)))
        anchors.append((segment[-1].time_s, *segment[-1].world))
        for first, last in zip(anchors, anchors[1:], strict=False):
            dt = last[0]-first[0]
            if dt < 0.16 - 1e-6:
                continue
            speed = float(np.hypot(last[1]-first[1], last[2]-first[2]) / dt * 3.6)
            if not np.isfinite(speed) or speed > maximum + 1e-6:
                rejected += 1
                continue
            speed = 0.0 if speed < config.tracking.standing_kmh else speed
            windows.append((first[0], last[0], speed))
    window_index = 0
    for sample in track.samples:
        while window_index < len(windows) and windows[window_index][1] < sample.time_s:
            window_index += 1
        if window_index < len(windows):
            start, end, speed = windows[window_index]
            if sample.calibrated and start < sample.time_s <= end:
                sample.speed_mps = speed/3.6
    return windows, rejected


def motion_intensity(track: PlayerTrack, config: AppConfig) -> list[dict[str, float | int]]:
    windows, _ = _motion_windows(track, config)
    buckets: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for start, end, speed in windows:
        while start < end:
            minute = int(start // 60)
            stop = min(end, (minute+1)*60)
            buckets[minute].append((speed, stop-start))
            start = stop
    return [{"from_minute": minute, "to_minute": minute+1,
             "intensity": round(min(100, sum(speed*duration for speed, duration in values)
                                    / sum(duration for _, duration in values)
                                    / config.tracking.max_speed_kmh * 100), 1)}
            for minute, values in sorted(buckets.items())]


def summarize_motion(
    track: PlayerTrack,
    config: AppConfig,
    zone_fn=None,
) -> MotionSummary:
    distance = 0.0
    measured = 0.0
    speeds: list[tuple[float, float]] = []
    rejected = 0
    zones: dict[str, float] = {}
    for sample in track.samples:
        if sample.world is None:
            continue
        if zone_fn is not None:
            key = zone_fn(sample.world[0], sample.world[1])
            zones[key] = zones.get(key, 0.0) + 1.0
    windows, rejected = _motion_windows(track, config)
    for start, end, speed in windows:
        measured += end-start
        distance += speed/3.6*(end-start)
        speeds.append((end, speed))
    available = measured > 0
    sprints = count_sprints(windows, config)
    max_pair = max(speeds, key=lambda item: item[1], default=None)
    active = sum(current.time_s-previous.time_s for previous, current in zip(track.samples, track.samples[1:], strict=False)
                 if 0 < current.time_s-previous.time_s <= 0.7)
    total_zone = sum(zones.values()) or 1.0
    return MotionSummary(
        distance_m=round(distance, 2) if available else None,
        avg_speed_kmh=round(distance / measured * 3.6, 2) if available else None,
        max_speed_kmh=round(max_pair[1], 2) if max_pair else None,
        sprint_count=sprints,
        active_seconds=round(active, 2),
        measured_seconds=round(measured, 2),
        rejected_jumps=rejected,
        peak_speed_at_s=None if max_pair is None else round(max_pair[0], 3),
        zone_activity={key: round(value / total_zone, 3) for key, value in zones.items()},
    )


def count_sprints(windows: list[tuple[float, float, float]], config: AppConfig) -> int:
    """Count sustained bouts; jitter and unmeasured gaps cannot create a sprint."""
    count = 0
    duration = 0.0
    counted = False
    previous_end = None
    threshold = config.tracking.sprint_kmh
    for start, end, speed in windows:
        if previous_end is None or start - previous_end > 1e-6:
            duration, counted = 0.0, False
        previous_end = end
        if speed < threshold - config.tracking.sprint_hysteresis_kmh:
            duration, counted = 0.0, False
        elif speed >= threshold or duration > 0:
            duration += end - start
            if not counted and duration >= config.tracking.sprint_min_duration_s - 1e-6:
                count += 1
                counted = True
    return count
