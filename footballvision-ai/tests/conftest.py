from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import AppConfig, EventConfig, PitchConfig, TrackingConfig
from app.core.types import BBox, BallSample, PlayerTrack, Role, TeamId, TrackSample


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(
        pitch=PitchConfig(mode="hali_saha", length_m=40, width_m=20, goal_width_m=3),
        tracking=TrackingConfig(sprint_kmh=18, max_speed_kmh=36, lost_track_buffer=20),
        events=EventConfig(
            possession_radius_m=2.0,
            possession_min_frames=1,
            pass_min_distance_m=2.0,
            pass_min_time_s=0.04,
            shot_min_speed_kmh=20.0,
            shot_min_frames=3,
            goal_min_frames=1,
            dribble_min_distance_m=3.0,
        ),
        home_name="Qirmizi",
        away_name="Mavi",
    )


def sample(
    track_id: int,
    frame: int,
    x: float,
    y: float,
    *,
    team: TeamId = TeamId.HOME,
    role: Role = Role.PLAYER,
    fps: float = 25.0,
) -> TrackSample:
    return TrackSample(
        frame=frame,
        time_s=frame / fps,
        pixel=(x * 20, y * 20),
        bbox=BBox(x * 20 - 4, y * 20 - 12, x * 20 + 4, y * 20),
        world=(x, y),
        confidence=0.9,
        team=team,
        role=role,
    )


def make_track(
    track_id: int,
    points: list[tuple[int, float, float]],
    *,
    team: TeamId = TeamId.HOME,
    role: Role = Role.PLAYER,
) -> PlayerTrack:
    track = PlayerTrack(track_id=track_id, role=role, team=team)
    track.samples = [sample(track_id, frame, x, y, team=team, role=role) for frame, x, y in points]
    return track


def make_ball(points: list[tuple[int, float, float]], fps: float = 25.0) -> list[BallSample]:
    samples: list[BallSample] = []
    previous = None
    for frame, x, y in points:
        time_s = frame / fps
        velocity = None
        if previous is not None:
            dt = time_s - previous[0]
            if dt > 0:
                velocity = ((x - previous[1]) / dt, (y - previous[2]) / dt)
        samples.append(
            BallSample(
                frame=frame,
                time_s=time_s,
                pixel=(x * 20, y * 20),
                world=(x, y),
                confidence=0.8,
                interpolated=False,
                velocity_mps=velocity,
            )
        )
        previous = (time_s, x, y)
    return samples


@pytest.fixture
def tmp_out(tmp_path: Path) -> Path:
    dest = tmp_path / "out"
    dest.mkdir()
    return dest
