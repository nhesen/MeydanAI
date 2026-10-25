"""Corners and goal kicks from a measured byline exit plus a dead-ball restart.

A paused ball near a corner is not enough. The ball has to be seen leaving
the goal line outside the posts, then restarting from the corner or the
goal area. The team that touched it out is not awarded the restart.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from app.calibration.zones import PitchZones
from app.core.config import AppConfig
from app.core.types import BallSample, EventType, MatchEvent, PlayerTrack, Role, TeamId


@dataclass
class _Exit:
    time_s: float
    left: bool
    y: float
    team: TeamId


class RestartWatch:
    def __init__(self, config: AppConfig, zones: PitchZones) -> None:
        self.config = config
        self.zones = zones
        self.exit: _Exit | None = None

    def update(
        self,
        ball: BallSample,
        team: TeamId | None,
        tracks: dict[int, PlayerTrack],
        *,
        goal_scored: bool,
    ) -> list[MatchEvent]:
        if goal_scored or not ball.calibrated or ball.interpolated or ball.world is None:
            if goal_scored:
                self.exit = None
            return []
        x, y = ball.world
        if self._wide_of_goal(x, y):
            if team in {TeamId.HOME, TeamId.AWAY}:
                self.exit = _Exit(ball.time_s, x < self.zones.length_m / 2, y, team)
            return []
        pending = self.exit
        if pending is None:
            return []
        if ball.time_s - pending.time_s > 15:
            self.exit = None
            return []
        speed = 0.0 if ball.velocity_mps is None else hypot(*ball.velocity_mps)
        if speed > 1.5:
            return []
        if not self._same_end(x, pending.left):
            return []
        restart_team = TeamId.AWAY if pending.team is TeamId.HOME else TeamId.HOME
        taker = _nearest_teammate(tracks, restart_team, (x, y))
        if taker is None:
            return []
        if self._near_corner(x, y, pending.left):
            self.exit = None
            return [
                MatchEvent(
                    EventType.CORNER,
                    ball.time_s,
                    ball.frame,
                    taker,
                    restart_team,
                    x=x,
                    y=y,
                    confidence=0.7,
                    extra={"evidence": "byline-exit-then-corner-restart"},
                )
            ]
        if self._in_goal_area(x, y, pending.left):
            self.exit = None
            return [
                MatchEvent(
                    EventType.GOAL_KICK,
                    ball.time_s,
                    ball.frame,
                    taker,
                    restart_team,
                    x=x,
                    y=y,
                    confidence=0.7,
                    extra={"evidence": "byline-exit-then-goal-area-restart"},
                )
            ]
        return []

    def _wide_of_goal(self, x: float, y: float) -> bool:
        outside = x <= -0.05 or x >= self.zones.length_m + 0.05
        half = self.config.pitch.goal_width_m / 2 + 0.25
        center = self.zones.width_m / 2
        return outside and not (center - half <= y <= center + half)

    def _same_end(self, x: float, left: bool) -> bool:
        return x <= self.zones.length_m * 0.35 if left else x >= self.zones.length_m * 0.65

    def _near_corner(self, x: float, y: float, left: bool) -> bool:
        end = 0.0 if left else self.zones.length_m
        return min(hypot(x - end, y), hypot(x - end, y - self.zones.width_m)) <= 2.0

    def _in_goal_area(self, x: float, y: float, left: bool) -> bool:
        depth = 5.5 if self.zones.length_m >= 90 else 2.5
        along = x if left else self.zones.length_m - x
        center = self.zones.width_m / 2
        half = max(4.0, self.config.pitch.goal_width_m)
        return 0 <= along <= depth and abs(y - center) <= half


def _nearest_teammate(
    tracks: dict[int, PlayerTrack], team: TeamId, point: tuple[float, float]
) -> int | None:
    best: tuple[float, int] | None = None
    for track in tracks.values():
        if track.team is not team or track.role not in {Role.PLAYER, Role.GOALKEEPER}:
            continue
        sample = track.last
        if sample is None or sample.world is None or not sample.calibrated:
            continue
        dist = hypot(sample.world[0] - point[0], sample.world[1] - point[1])
        if best is None or dist < best[0]:
            best = (dist, track.track_id)
    return None if best is None else best[1]
