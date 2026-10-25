from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Protocol

MAX_PLAYER_KMH = 36.0
MAX_AVG_KMH = 12.0
MAX_PLAUSIBLE_STEP_KMH = 40.0
SPRINT_KMH = 18.0
STANDING_KMH = 1.2
PITCH_LENGTH_M = 40.0
PITCH_WIDTH_M = 20.0
MAX_SPRINT_EVENTS = 8
SECONDS_PER_SPRINT = 12


class HasPosition(Protocol):
    timestamp_ms: int
    x: float
    y: float


@dataclass(frozen=True)
class SanitizedMetrics:
    rating: float | None
    distance_m: float | None
    avg_speed_kmh: float | None
    max_speed_kmh: float | None
    sprint_count: int | None
    active_seconds: int | None
    activity_count: int | None
    peak_speed_at_ms: int | None


def clamp_speed(value: float | None, ceiling: float = MAX_PLAYER_KMH) -> float | None:
    if value is None:
        return None
    return round(min(max(value, 0.0), ceiling), 1)


def _step_meters(
    previous: HasPosition,
    current: HasPosition,
    length_m: float = PITCH_LENGTH_M,
    width_m: float = PITCH_WIDTH_M,
) -> float:
    dx = (current.x - previous.x) * length_m
    dy = (current.y - previous.y) * width_m
    return float((dx * dx + dy * dy) ** 0.5)


def _step_kmh(
    previous: HasPosition,
    current: HasPosition,
    length_m: float = PITCH_LENGTH_M,
    width_m: float = PITCH_WIDTH_M,
) -> float:
    dt = max(current.timestamp_ms - previous.timestamp_ms, 1) / 1000
    return (_step_meters(previous, current, length_m, width_m) / dt) * 3.6


def reconstruct_display_path(samples: list[Any]) -> list[Any]:
    """Return observed samples without inventing movement or video timestamps."""
    observed: dict[int, Any] = {}
    for sample in samples:
        if (
            sample.timestamp_ms < 0
            or not math.isfinite(sample.x)
            or not math.isfinite(sample.y)
            or not 0.0 <= sample.x <= 1.0
            or not 0.0 <= sample.y <= 1.0
        ):
            continue
        observed[sample.timestamp_ms] = sample
    return [observed[timestamp] for timestamp in sorted(observed)]


def sanitize_positions(samples: list[Any]) -> list[Any]:
    return reconstruct_display_path(samples)


def intensity_from_positions(
    samples: list[Any],
    *,
    length_m: float = PITCH_LENGTH_M,
    width_m: float = PITCH_WIDTH_M,
) -> list[tuple[int, int, float]]:
    if len(samples) < 2:
        return []
    buckets: dict[int, list[tuple[float, int]]] = {}
    for previous, current in pairwise(samples):
        duration_ms = current.timestamp_ms - previous.timestamp_ms
        if duration_ms <= 0 or duration_ms > 10_000:
            continue
        speed = _step_kmh(previous, current, length_m, width_m)
        if not math.isfinite(speed) or speed > MAX_PLAUSIBLE_STEP_KMH:
            continue
        speed = 0.0 if speed < STANDING_KMH else min(speed, MAX_PLAYER_KMH)
        start = previous.timestamp_ms
        while start < current.timestamp_ms:
            minute = start // 60_000
            end = min(current.timestamp_ms, (minute + 1) * 60_000)
            buckets.setdefault(minute, []).append((speed, end - start))
            start = end
    result: list[tuple[int, int, float]] = []
    for minute, values in sorted(buckets.items()):
        average = sum(speed * duration for speed, duration in values) / sum(
            duration for _, duration in values
        )
        intensity = min(100.0, (average / MAX_PLAYER_KMH) * 100.0)
        result.append((minute, minute + 1, round(intensity, 1)))
    return result


def sanitize_intensity(
    buckets: list[Any],
    *,
    raw_max_speed_kmh: float | None,
) -> list[Any]:
    scale = 1.0
    if raw_max_speed_kmh is not None and raw_max_speed_kmh > MAX_PLAYER_KMH:
        scale = MAX_PLAYER_KMH / raw_max_speed_kmh
    result: list[Any] = []
    for bucket in buckets:
        intensity = round(min(100.0, max(0.0, float(bucket.intensity) * scale)), 1)
        bucket.intensity = intensity
        result.append(bucket)
    return result


FOOTBALL_EVENT_TYPES = {
    "pass",
    "successful_pass",
    "failed_pass",
    "key_pass",
    "shot",
    "shot_on_target",
    "shot_off_target",
    "goal",
    "assist",
    "tackle",
    "interception",
    "turnover",
    "ball_recovery",
    "dribble",
    "save",
    "corner",
    "goal_kick",
    "woodwork",
    "big_chance",
    "free_kick",
    "penalty",
}


def sanitize_events(
    events: list[Any],
    *,
    calibrated: bool = False,
    sprint_kmh: float = SPRINT_KMH,
) -> list[Any]:
    kept: list[Any] = []
    sprints = 0
    for event in sorted(events, key=lambda item: item.timestamp_ms):
        speed = event.speed_kmh
        event_type = event.event_type
        if event_type in FOOTBALL_EVENT_TYPES:
            kept.append(event)
            continue
        if speed is not None and speed > MAX_PLAUSIBLE_STEP_KMH:
            if event_type != "peak_speed":
                continue
            speed = MAX_PLAYER_KMH
        if speed is not None:
            speed = min(float(speed), MAX_PLAYER_KMH)
            event.speed_kmh = round(speed, 1)
        if event_type == "sprint":
            if speed is None or speed < sprint_kmh:
                continue
            if not calibrated and sprints >= MAX_SPRINT_EVENTS:
                continue
            sprints += 1
        if event_type == "peak_speed" and event.speed_kmh is not None:
            event.speed_kmh = min(float(event.speed_kmh), MAX_PLAYER_KMH)
        kept.append(event)
    return kept


def sanitize_player_metrics(
    *,
    rating: float | None,
    distance_m: float | None,
    avg_speed_kmh: float | None,
    max_speed_kmh: float | None,
    sprint_count: int | None,
    active_seconds: int | None,
    activity_count: int | None,
    peak_speed_at_ms: int | None,
    event_sprint_count: int | None = None,
    calibrated: bool = False,
) -> SanitizedMetrics:
    active = None if active_seconds is None else max(0, active_seconds)
    max_speed = clamp_speed(max_speed_kmh)
    average_ceiling = MAX_PLAYER_KMH if calibrated else MAX_AVG_KMH
    avg_speed = clamp_speed(avg_speed_kmh, average_ceiling)
    distance = None if distance_m is None else max(0.0, distance_m)
    if active and active > 0 and distance is not None:
        distance = min(distance, round((average_ceiling / 3.6) * active, 1))
    sprints = 0 if sprint_count is None else max(0, sprint_count)
    if event_sprint_count is not None:
        sprints = min(sprints, event_sprint_count)
    if active is not None and not calibrated:
        sprints = min(sprints, active // SECONDS_PER_SPRINT)
    elif active is not None:
        sprints = min(sprints, active)
    if max_speed_kmh is not None and max_speed_kmh > MAX_PLAYER_KMH and rating is None:
        rating = 6.0
    return SanitizedMetrics(
        rating=None if rating is None else round(min(max(rating, 0.0), 10.0), 1),
        distance_m=None if distance is None else round(distance, 1),
        avg_speed_kmh=avg_speed,
        max_speed_kmh=max_speed,
        sprint_count=(
            sprints if sprint_count is not None or event_sprint_count is not None else None
        ),
        active_seconds=active,
        activity_count=activity_count,
        peak_speed_at_ms=peak_speed_at_ms,
    )
