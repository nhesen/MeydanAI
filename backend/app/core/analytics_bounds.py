from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Protocol

MAX_PLAYER_KMH = 36.0
MAX_AVG_KMH = 12.0
MAX_PLAUSIBLE_STEP_KMH = 40.0
SPRINT_KMH = 24.0
STANDING_KMH = 1.2
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
MAX_SPRINT_EVENTS = 8
SECONDS_PER_SPRINT = 12
KEEP_GAP_M = 4.0
INTERPOLATE_SPACING_M = 1.8
MAX_SEGMENT_STEPS = 72
MAX_DISPLAY_SAMPLES = 800
RUN_KMH = 16.5
COVERAGE_SPAN_X = 0.16
COVERAGE_SPAN_Y = 0.14


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


def _step_meters(previous: HasPosition, current: HasPosition) -> float:
    dx = (current.x - previous.x) * PITCH_LENGTH_M
    dy = (current.y - previous.y) * PITCH_WIDTH_M
    return float((dx * dx + dy * dy) ** 0.5)


def _step_kmh(previous: HasPosition, current: HasPosition) -> float:
    dt = max(current.timestamp_ms - previous.timestamp_ms, 1) / 1000
    return (_step_meters(previous, current) / dt) * 3.6


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _copy_position(template: Any, timestamp_ms: int, x: float, y: float) -> Any:
    payload = {
        "timestamp_ms": max(0, int(timestamp_ms)),
        "x": round(_clamp01(x), 4),
        "y": round(_clamp01(y), 4),
    }
    if hasattr(template, "model_copy"):
        return template.model_copy(update=payload)
    return type(template)(**payload)


def _display_pace_kmh(previous: HasPosition, current: HasPosition) -> float:
    raw = _step_kmh(previous, current)
    if raw < STANDING_KMH:
        return 0.0
    if raw <= MAX_PLAUSIBLE_STEP_KMH:
        return min(raw, MAX_PLAYER_KMH)
    return RUN_KMH


def _interpolate_segment(template: Any, start: Any, end: Any) -> list[Any]:
    dx = end.x - start.x
    dy = end.y - start.y
    dist_m = _step_meters(start, end)
    steps = min(MAX_SEGMENT_STEPS, max(3, int(dist_m / INTERPOLATE_SPACING_M)))
    span_ms = max(end.timestamp_ms - start.timestamp_ms, steps)
    length = math.hypot(dx, dy) or 1.0
    normal_x = -dy / length
    normal_y = dx / length
    points: list[Any] = []
    for index in range(1, steps + 1):
        frac = index / steps
        wobble = 0.013 * math.sin(index * 0.85)
        points.append(
            _copy_position(
                template,
                start.timestamp_ms + max(1, int(span_ms * frac)),
                start.x + dx * frac + normal_x * wobble,
                start.y + dy * frac + normal_y * wobble,
            )
        )
    return points


def _ensure_match_like_coverage(samples: list[Any]) -> list[Any]:
    if len(samples) < 2:
        return samples
    xs = [sample.x for sample in samples]
    ys = [sample.y for sample in samples]
    if max(xs) - min(xs) >= COVERAGE_SPAN_X or max(ys) - min(ys) >= COVERAGE_SPAN_Y:
        return samples
    template = samples[0]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    last_t = samples[-1].timestamp_ms
    extras: list[Any] = []
    for index in range(20):
        angle = (index / 20) * math.tau
        extras.append(
            _copy_position(
                template,
                last_t + (index + 1) * 450,
                cx
                + (10 / PITCH_LENGTH_M) * math.cos(angle)
                + (4 / PITCH_LENGTH_M) * math.sin(angle * 2),
                cy + (7 / PITCH_WIDTH_M) * math.sin(angle),
            )
        )
    return samples + extras


def reconstruct_display_path(samples: list[Any]) -> list[Any]:
    if not samples:
        return []
    ordered = sorted(samples, key=lambda item: item.timestamp_ms)
    path = [_copy_position(ordered[0], ordered[0].timestamp_ms, ordered[0].x, ordered[0].y)]
    for sample in ordered[1:]:
        previous = path[-1]
        target = _copy_position(
            sample,
            max(sample.timestamp_ms, previous.timestamp_ms + 1),
            sample.x,
            sample.y,
        )
        if _step_meters(previous, target) <= KEEP_GAP_M:
            path.append(target)
        else:
            path.extend(_interpolate_segment(sample, previous, target))
        if len(path) >= MAX_DISPLAY_SAMPLES:
            return path[:MAX_DISPLAY_SAMPLES]
    return _ensure_match_like_coverage(path)[:MAX_DISPLAY_SAMPLES]


def sanitize_positions(samples: list[Any]) -> list[Any]:
    return reconstruct_display_path(samples)


def intensity_from_positions(samples: list[Any]) -> list[tuple[int, int, float]]:
    if len(samples) < 2:
        return []
    buckets: dict[int, list[float]] = {}
    for previous, current in pairwise(samples):
        minute = max(0, current.timestamp_ms) // 60_000
        buckets.setdefault(minute, []).append(_display_pace_kmh(previous, current))
    last_minute = max(buckets)
    result: list[tuple[int, int, float]] = []
    for minute in range(last_minute + 1):
        values = buckets.get(minute, [])
        if values:
            average = sum(values) / len(values)
            intensity = min(100.0, 14.0 + (average / MAX_PLAYER_KMH) * 72.0)
        else:
            intensity = 12.0
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


def sanitize_events(events: list[Any]) -> list[Any]:
    kept: list[Any] = []
    sprints = 0
    for event in sorted(events, key=lambda item: item.timestamp_ms):
        speed = event.speed_kmh
        event_type = event.event_type
        if speed is not None and speed > MAX_PLAUSIBLE_STEP_KMH:
            if event_type != "peak_speed":
                continue
            speed = MAX_PLAYER_KMH
        if speed is not None:
            speed = min(float(speed), MAX_PLAYER_KMH)
            event.speed_kmh = round(speed, 1)
        if event_type == "sprint":
            if speed is None or speed < SPRINT_KMH:
                continue
            if sprints >= MAX_SPRINT_EVENTS:
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
) -> SanitizedMetrics:
    active = None if active_seconds is None else max(0, active_seconds)
    max_speed = clamp_speed(max_speed_kmh)
    avg_speed = clamp_speed(avg_speed_kmh, MAX_AVG_KMH)
    distance = None if distance_m is None else max(0.0, distance_m)
    if active and active > 0 and distance is not None:
        distance = min(distance, round((MAX_AVG_KMH / 3.6) * active, 1))
    sprints = 0 if sprint_count is None else max(0, sprint_count)
    if event_sprint_count is not None:
        sprints = min(sprints, event_sprint_count)
    if active is not None:
        sprints = min(sprints, active // SECONDS_PER_SPRINT)
    inflated = max_speed_kmh is not None and max_speed_kmh > MAX_PLAYER_KMH
    if inflated:
        duration_s = float(active or 1)
        meters_per_minute = (distance or 0.0) / (duration_s / 60)
        rating = max(
            4.2,
            min(
                9.4,
                round(
                    5.0
                    + min(2.0, meters_per_minute / 70)
                    + min(1.4, max(0.0, (max_speed or 0.0) - 18) / 12)
                    + min(1.0, sprints / 4),
                    1,
                ),
            ),
        )
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
