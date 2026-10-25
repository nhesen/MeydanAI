from __future__ import annotations

from app.analytics.passing import PassCandidate, detect_passes
from app.analytics.possession import PossessionEngine
from app.analytics.restarts import RestartWatch
from app.analytics.shooting import ShotWindow, detect_shots
from app.calibration.zones import PitchZones
from app.core.config import AppConfig
from app.core.types import BallSample, EventType, MatchEvent, PlayerTrack, TeamId


class EventDetector:
    def __init__(self, config: AppConfig, zones: PitchZones) -> None:
        self.config = config
        self.zones = zones
        self.possession = PossessionEngine(config)
        self.restarts = RestartWatch(config, zones)
        self.open_pass: PassCandidate | None = None
        self.shot_window: ShotWindow | None = None
        self.events: list[MatchEvent] = []
        self._last_owner: int | None = None
        self._last_team: TeamId | None = None
        self._on_ball_origin: dict[int, tuple[float, float]] = {}
        self._still_ball_s: float | None = None
        self._last_ball: tuple[float, float] | None = None

    def update(
        self, ball: BallSample, tracks: dict[int, PlayerTrack]
    ) -> list[MatchEvent]:
        if ball.scene_cut:
            self.possession.reset_context()
            self.open_pass = None
            self.shot_window = None
            self.restarts.exit = None
            self._last_owner = None
            self._last_team = None
            self._on_ball_origin.clear()
            self._still_ball_s = None
            self._last_ball = None
        if not ball.calibrated:
            self.shot_window = None
            self._on_ball_origin.clear()
            self._still_ball_s = None
        state = self.possession.update(ball, tracks)
        created: list[MatchEvent] = []
        xy = ball.world if ball.calibrated else ball.pixel
        relative_distance = None
        if self.open_pass and state.player_id is not None:
            giver, receiver = tracks.get(self.open_pass.giver_id), tracks.get(state.player_id)
            if giver and giver.last and receiver and receiver.last:
                a, b = giver.last, receiver.last
                relative_distance = ((a.pixel[0]-b.pixel[0])**2 + (a.pixel[1]-b.pixel[1])**2)**.5 / max(1, (a.bbox.height+b.bbox.height)/2)

        opponent_near = self._opponent_close(state.player_id, state.team, tracks)
        pass_events, self.open_pass = detect_passes(
            self._last_owner,
            self._last_team,
            state.player_id,
            state.team,
            ball.time_s,
            ball.frame,
            xy,
            self.open_pass,
            self.config,
            opponent_near,
            metric=ball.calibrated,
            relative_distance=relative_distance,
        )
        created.extend(pass_events)
        if not ball.calibrated:
            self._last_owner, self._last_team = state.player_id, state.team
            self.events.extend(created)
            return created
        # A shot can start just after the ball leaves the observed owner's feet.
        release = self.open_pass if self.open_pass and ball.time_s-self.open_pass.start_s <= 0.35 else None
        shot_events, self.shot_window, scored = detect_shots(
            ball,
            state.player_id if state.player_id is not None else (release.giver_id if release else None),
            state.team if state.team is not None else (release.giver_team if release else None),
            tracks,
            self.shot_window,
            self.zones,
            self.config,
        )
        created.extend(shot_events)
        created.extend(
            self.restarts.update(ball, state.team, tracks, goal_scored=scored)
        )
        if scored:
            goal = next(item for item in shot_events if item.event_type is EventType.GOAL)
            created.extend(self._link_assist(ball.time_s, goal.player_id, goal.team))
        # Ball travel alone does not prove beating an opponent, a referee's
        # decision or a restart type. These need separate evidence/review.
        self._last_owner = state.player_id
        self._last_team = state.team
        self.events.extend(created)
        return created

    def flush(
        self, ball: BallSample, tracks: dict[int, PlayerTrack]
    ) -> list[MatchEvent]:
        if self.shot_window is None:
            return []
        closing = BallSample(
            frame=ball.frame,
            time_s=ball.time_s,
            pixel=ball.pixel,
            world=ball.world,
            confidence=ball.confidence,
            interpolated=True,
            velocity_mps=(0.0, 0.0),
        )
        created, self.shot_window, scored = detect_shots(
            closing, None, None, tracks, self.shot_window, self.zones, self.config
        )
        if scored:
            goal = next(item for item in created if item.event_type is EventType.GOAL)
            created.extend(self._link_assist(ball.time_s, goal.player_id, goal.team))
        self.events.extend(created)
        return created

    def _link_assist(self, goal_time: float, scorer_id: int | None, scoring_team: TeamId | None) -> list[MatchEvent]:
        window = self.config.events.key_pass_shot_window_s
        recent = [
            event
            for event in reversed(self.events)
            if event.event_type is EventType.SUCCESSFUL_PASS
            and goal_time - event.time_s <= window
            and event.team == scoring_team
            and event.related_player_id == scorer_id
            and event.player_id != scorer_id
            and not event.extra.get("estimated")
        ]
        if not recent:
            return []
        last_pass = recent[0]
        key = MatchEvent(
            EventType.KEY_PASS,
            last_pass.time_s,
            last_pass.frame,
            last_pass.player_id,
            last_pass.team,
            related_player_id=last_pass.related_player_id,
            x=last_pass.x,
            y=last_pass.y,
            confidence=0.7,
        )
        assist = MatchEvent(
            EventType.ASSIST,
            last_pass.time_s,
            last_pass.frame,
            last_pass.player_id,
            last_pass.team,
            related_player_id=last_pass.related_player_id,
            x=last_pass.x,
            y=last_pass.y,
            confidence=0.72,
        )
        return [key, assist]

    def _dribble(
        self, owner: int | None, xy: tuple[float, float] | None, ball: BallSample
    ) -> list[MatchEvent]:
        if owner is None or xy is None:
            self._on_ball_origin.clear()
            return []
        if owner != self._last_owner:
            self._on_ball_origin.clear()
        origin = self._on_ball_origin.get(owner)
        if origin is None:
            self._on_ball_origin[owner] = xy
            return []
        dist = ((xy[0] - origin[0]) ** 2 + (xy[1] - origin[1]) ** 2) ** 0.5
        if dist < self.config.events.dribble_min_distance_m:
            return []
        self._on_ball_origin[owner] = xy
        return [
            MatchEvent(
                EventType.DRIBBLE,
                ball.time_s,
                ball.frame,
                owner,
                self._last_team,
                x=xy[0],
                y=xy[1],
                confidence=0.57,
                extra={"distance_m": round(dist, 2)},
            )
        ]

    def _set_pieces(
        self, ball: BallSample, xy: tuple[float, float] | None, team: TeamId | None
    ) -> list[MatchEvent]:
        if xy is None or ball.velocity_mps is None:
            return []
        speed = (ball.velocity_mps[0] ** 2 + ball.velocity_mps[1] ** 2) ** 0.5
        if speed < 0.35:
            if self._still_ball_s is None:
                self._still_ball_s = ball.time_s
            return []
        paused = self._still_ball_s
        self._still_ball_s = None
        if paused is None or ball.time_s - paused < self.config.events.set_piece_stop_s:
            return []
        if (xy[0] < 1.2 or xy[0] > self.zones.length_m - 1.2) and (
            abs(xy[1] - self.zones.width_m / 2) < self.config.pitch.goal_width_m
        ):
            return [
                MatchEvent(
                    EventType.PENALTY
                    if self.zones.in_penalty(xy[0], xy[1], xy[0] < self.zones.length_m / 2)
                    else EventType.FREE_KICK,
                    ball.time_s,
                    ball.frame,
                    self._last_owner,
                    team,
                    x=xy[0],
                    y=xy[1],
                    confidence=0.4,
                )
            ]
        if xy[1] < 1.0 or xy[1] > self.zones.width_m - 1.0:
            if xy[0] < 4 or xy[0] > self.zones.length_m - 4:
                return [
                    MatchEvent(
                        EventType.CORNER,
                        ball.time_s,
                        ball.frame,
                        self._last_owner,
                        team,
                        x=xy[0],
                        y=xy[1],
                        confidence=0.45,
                    )
                ]
            return [
                MatchEvent(
                    EventType.FREE_KICK,
                    ball.time_s,
                    ball.frame,
                    self._last_owner,
                    team,
                    x=xy[0],
                    y=xy[1],
                    confidence=0.38,
                )
            ]
        return []

    def _opponent_close(
        self, owner: int | None, team: TeamId | None, tracks: dict[int, PlayerTrack]
    ) -> bool:
        if owner is None or team is None:
            return False
        source = tracks.get(owner)
        if source is None or source.last is None or source.last.world is None:
            return False
        radius = self.config.events.tackle_radius_m
        sx, sy = source.last.world
        for track in tracks.values():
            if track.track_id == owner or track.team in {team, TeamId.UNKNOWN}:
                continue
            if track.last is None or track.last.world is None:
                continue
            dist = (
                (track.last.world[0] - sx) ** 2 + (track.last.world[1] - sy) ** 2
            ) ** 0.5
            if dist <= radius:
                return True
        return False
