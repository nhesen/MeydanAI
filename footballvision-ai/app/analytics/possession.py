from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import AppConfig
from app.core.types import BallSample, PlayerTrack, Role, TeamId


@dataclass
class PossessionState:
    player_id: int | None = None
    team: TeamId | None = None
    frames: int = 0
    pending_player: int | None = None
    pending_team: TeamId | None = None
    pending_frames: int = 0
    pending_seen_s: float = -1.0
    timeline: list[dict] = field(default_factory=list)
    team_frames: dict[str, int] = field(
        default_factory=lambda: {"home": 0, "away": 0, "none": 0}
    )
    player_frames: dict[int, int] = field(default_factory=dict)


class PossessionEngine:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state = PossessionState()
        self._relative_positions: dict[int, tuple[float, float, float]] = {}

    def reset_context(self) -> None:
        self._relative_positions.clear()
        self.state.player_id = None
        self.state.team = None
        self.state.frames = 0
        self.state.pending_player = None
        self.state.pending_team = None
        self.state.pending_frames = 0

    def update(
        self,
        ball: BallSample,
        tracks: dict[int, PlayerTrack],
        min_frames: int | None = None,
    ) -> PossessionState:
        needed = (
            self.config.events.possession_min_frames
            if min_frames is None
            else min_frames
        )
        owner = self._nearest(ball, tracks)
        if owner is None:
            self.state.player_id = None
            self.state.team = None
            self.state.frames = 0
            self.state.team_frames["none"] += 1
            if ball.time_s - self.state.pending_seen_s > 0.3:
                self.state.pending_player = None
                self.state.pending_team = None
                self.state.pending_frames = 0
            self.state.timeline.append(
                {
                    "time_s": ball.time_s,
                    "player_id": self.state.player_id,
                    "team": None if self.state.team is None else self.state.team.value,
                }
            )
            return self.state
        player_id, team, _dist = owner
        if ball.time_s - self.state.pending_seen_s > 0.3:
            self.state.pending_player = None
            self.state.pending_frames = 0
        self.state.pending_seen_s = ball.time_s
        if player_id == self.state.player_id:
            self.state.frames += 1
            self.state.pending_frames = 0
        else:
            if self.state.pending_player == player_id:
                self.state.pending_frames += 1
            else:
                self.state.pending_player = player_id
                self.state.pending_team = team
                self.state.pending_frames = 1
            if self.state.pending_frames >= needed:
                self.state.player_id = player_id
                self.state.team = team
                self.state.frames = self.state.pending_frames
            else:
                self.state.player_id = None
                self.state.team = None
        if self.state.team in {TeamId.HOME, TeamId.AWAY}:
            self.state.team_frames[self.state.team.value] += 1
        else:
            self.state.team_frames["none"] += 1
        if self.state.player_id is not None:
            self.state.player_frames[self.state.player_id] = (
                self.state.player_frames.get(self.state.player_id, 0) + 1
            )
        self.state.timeline.append(
            {
                "time_s": ball.time_s,
                "player_id": self.state.player_id,
                "team": None if self.state.team is None else self.state.team.value,
            }
        )
        return self.state

    def _nearest(
        self, ball: BallSample, tracks: dict[int, PlayerTrack]
    ) -> tuple[int, TeamId, float] | None:
        if ball.interpolated or (ball.world is None and ball.pixel is None):
            return None
        best: tuple[int, TeamId, float] | None = None
        radius = self.config.events.possession_radius_m
        for track in tracks.values():
            if track.role not in {Role.PLAYER, Role.GOALKEEPER}:
                continue
            sample = track.last
            if sample is None or sample.frame != ball.frame:
                continue
            # A fast ball merely passing a player's projected feet is not control.
            if ball.pixel is not None:
                height = max(sample.bbox.height, 1.0)
                offset = ((ball.pixel[0]-sample.pixel[0])/height, (ball.pixel[1]-sample.pixel[1])/height)
                previous = self._relative_positions.get(track.track_id)
                self._relative_positions[track.track_id] = (ball.time_s, *offset)
                if previous and 0 < ball.time_s-previous[0] <= .3:
                    relative_speed = ((offset[0]-previous[1])**2 + (offset[1]-previous[2])**2)**.5 / (ball.time_s-previous[0])
                    if relative_speed > 3.0:
                        continue
            if ball.calibrated and sample.calibrated and ball.world is not None and sample.world is not None:
                dist = (
                    (ball.world[0] - sample.world[0]) ** 2
                    + (ball.world[1] - sample.world[1]) ** 2
                ) ** 0.5
            elif ball.pixel is not None:
                dist = (
                    (ball.pixel[0] - sample.pixel[0]) ** 2
                    + (ball.pixel[1] - sample.pixel[1]) ** 2
                ) ** 0.5 / max(sample.bbox.height, 1.0) * radius / 0.65
            else:
                continue
            if dist > radius:
                continue
            if best is None or dist < best[2]:
                best = (track.track_id, track.team, dist)
        return best

    def percentages(self) -> dict[str, float]:
        total = sum(self.state.team_frames.values()) or 1
        contested = self.state.team_frames["home"] + self.state.team_frames["away"]
        denom = contested or total
        return {
            "home": round(100.0 * self.state.team_frames["home"] / denom, 1),
            "away": round(100.0 * self.state.team_frames["away"] / denom, 1),
            "none": round(100.0 * self.state.team_frames["none"] / total, 1),
        }
