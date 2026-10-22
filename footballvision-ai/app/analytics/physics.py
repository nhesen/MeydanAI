from __future__ import annotations

from dataclasses import dataclass

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
    previous: TrackSample | None = None
    for sample in track.samples:
        if sample.world is None:
            previous = None
            continue
        if zone_fn is not None:
            key = zone_fn(sample.world[0], sample.world[1])
            zones[key] = zones.get(key, 0.0) + 1.0
        if previous is not None and previous.world is not None:
            dt = sample.time_s - previous.time_s
            if 0 < dt <= 0.7:
                step = (
                    (sample.world[0] - previous.world[0]) ** 2
                    + (sample.world[1] - previous.world[1]) ** 2
                ) ** 0.5
                kmh = step / dt * 3.6
                if kmh <= config.tracking.max_speed_kmh + 9:
                    distance += step
                    measured += dt
                    sample.speed_mps = step / dt
                    speeds.append((sample.time_s, kmh))
                else:
                    rejected += 1
                    previous = None
                    continue
        previous = sample
    available = measured > 0
    sprints = 0
    in_sprint = False
    for _, kmh in speeds:
        if kmh >= config.tracking.sprint_kmh:
            if not in_sprint:
                sprints += 1
                in_sprint = True
        else:
            in_sprint = False
    max_pair = max(speeds, key=lambda item: item[1], default=None)
    active = (
        track.samples[-1].time_s - track.samples[0].time_s if len(track.samples) >= 2 else 0.0
    )
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
