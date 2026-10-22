from __future__ import annotations

from dataclasses import dataclass

from app.analytics.xg import expected_goals, goal_angle
from app.core.config import AppConfig
from app.core.types import BallSample, EventType, MatchEvent, PlayerTrack, Role, TeamId
from app.calibration.zones import PitchZones


@dataclass
class ShotWindow:
    player_id: int
    team: TeamId
    start_s: float
    start_xy: tuple[float, float]
    toward_left: bool
    frames: int = 1
    max_speed_kmh: float = 0.0


def _speed_kmh(ball: BallSample) -> float:
    if ball.velocity_mps is None:
        return 0.0
    return (ball.velocity_mps[0] ** 2 + ball.velocity_mps[1] ** 2) ** 0.5 * 3.6


def _toward_goal(ball: BallSample, toward_left: bool) -> bool:
    if ball.world is None or ball.velocity_mps is None:
        return False
    vx = ball.velocity_mps[0]
    return vx < -0.4 if toward_left else vx > 0.4


def detect_shots(
    ball: BallSample,
    owner_id: int | None,
    owner_team: TeamId | None,
    tracks: dict[int, PlayerTrack],
    window: ShotWindow | None,
    zones: PitchZones,
    config: AppConfig,
) -> tuple[list[MatchEvent], ShotWindow | None, bool]:
    events: list[MatchEvent] = []
    if ball.world is None:
        return events, window, False
    speed = _speed_kmh(ball)
    toward_left = window.toward_left if window is not None else owner_team is TeamId.AWAY
    aligned = _toward_goal(ball, toward_left)
    opening = (
        owner_id is not None
        and owner_team in {TeamId.HOME, TeamId.AWAY}
        and speed >= config.events.shot_min_speed_kmh
        and aligned
    )
    in_flight = (
        window is not None
        and speed >= config.events.shot_min_speed_kmh * 0.5
        and aligned
        and not zones.in_goal(ball.world[0], ball.world[1], config.pitch.goal_width_m, toward_left)
    )
    if opening or in_flight:
        if window is not None:
            window.frames += 1
            window.max_speed_kmh = max(window.max_speed_kmh, speed)
        else:
            window = ShotWindow(
                player_id=owner_id or 0,
                team=owner_team or TeamId.UNKNOWN,
                start_s=ball.time_s,
                start_xy=ball.world,
                toward_left=toward_left,
                max_speed_kmh=speed,
            )
        return events, window, False

    if window is None or window.frames < config.events.shot_min_frames:
        return events, None, False

    goal = zones.goal_center(window.toward_left)
    dist = ((window.start_xy[0] - goal[0]) ** 2 + (window.start_xy[1] - goal[1]) ** 2) ** 0.5
    angle = goal_angle(
        window.start_xy[0], window.start_xy[1], goal[0], goal[1], config.pitch.goal_width_m
    )
    gk_dist = _keeper_distance(tracks, window.team, ball.world)
    defenders = _defenders_in_path(tracks, window.team, window.start_xy, goal)
    xg = expected_goals(
        distance_m=dist,
        goal_angle_rad=angle,
        gk_distance_m=gk_dist,
        defenders_in_path=defenders,
    )
    on_target = zones.in_goal(ball.world[0], ball.world[1], config.pitch.goal_width_m, window.toward_left) or (
        abs(ball.world[1] - goal[1]) <= config.pitch.goal_width_m and aligned
    )
    scored = False
    if zones.in_goal(ball.world[0], ball.world[1], config.pitch.goal_width_m, window.toward_left):
        scored = True
    shot_type = EventType.SHOT_ON_TARGET if on_target else EventType.SHOT_OFF_TARGET
    extra = {
        "distance_m": round(dist, 2),
        "angle_deg": round(angle * 180 / 3.1416, 1),
        "xg": xg,
        "speed_kmh": round(window.max_speed_kmh, 1),
        "zone": zones.band(window.start_xy[0], window.start_xy[1], attacking_home=window.team is TeamId.HOME),
        "on_target": on_target,
    }
    events.append(
        MatchEvent(
            EventType.SHOT,
            ball.time_s,
            ball.frame,
            window.player_id,
            window.team,
            x=window.start_xy[0],
            y=window.start_xy[1],
            confidence=min(0.9, 0.5 + window.frames / 10),
            extra=extra,
        )
    )
    events.append(
        MatchEvent(
            shot_type,
            ball.time_s,
            ball.frame,
            window.player_id,
            window.team,
            x=window.start_xy[0],
            y=window.start_xy[1],
            confidence=min(0.88, 0.48 + window.frames / 10),
            extra=extra,
        )
    )
    if scored:
        events.append(
            MatchEvent(
                EventType.GOAL,
                ball.time_s,
                ball.frame,
                window.player_id,
                window.team,
                x=ball.world[0],
                y=ball.world[1],
                confidence=0.86,
                extra=extra,
            )
        )
    elif on_target:
        keeper = _nearest_keeper(tracks, window.team)
        if keeper is not None:
            events.append(
                MatchEvent(
                    EventType.SAVE,
                    ball.time_s,
                    ball.frame,
                    keeper,
                    TeamId.AWAY if window.team is TeamId.HOME else TeamId.HOME,
                    related_player_id=window.player_id,
                    x=ball.world[0],
                    y=ball.world[1],
                    confidence=0.58,
                )
            )
    return events, None, scored


def _nearest_keeper(tracks: dict[int, PlayerTrack], shooting_team: TeamId) -> int | None:
    keepers = [
        track
        for track in tracks.values()
        if track.role is Role.GOALKEEPER and track.team not in {shooting_team, TeamId.UNKNOWN}
    ]
    if not keepers:
        keepers = [track for track in tracks.values() if track.team not in {shooting_team, TeamId.UNKNOWN}]
    return keepers[0].track_id if keepers else None


def _keeper_distance(
    tracks: dict[int, PlayerTrack], shooting_team: TeamId, ball_xy: tuple[float, float]
) -> float | None:
    best = None
    for track in tracks.values():
        if track.role is not Role.GOALKEEPER or track.team == shooting_team or track.last is None:
            continue
        if track.last.world is None:
            continue
        dist = (
            (track.last.world[0] - ball_xy[0]) ** 2 + (track.last.world[1] - ball_xy[1]) ** 2
        ) ** 0.5
        best = dist if best is None else min(best, dist)
    return best


def _defenders_in_path(
    tracks: dict[int, PlayerTrack],
    shooting_team: TeamId,
    start: tuple[float, float],
    goal: tuple[float, float],
) -> int:
    count = 0
    for track in tracks.values():
        if track.team in {shooting_team, TeamId.UNKNOWN} or track.last is None or track.last.world is None:
            continue
        px, py = track.last.world
        dx, dy = goal[0] - start[0], goal[1] - start[1]
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        t = max(0.0, min(1.0, ((px - start[0]) * dx + (py - start[1]) * dy) / (length * length)))
        nearest = (start[0] + t * dx, start[1] + t * dy)
        dist = ((px - nearest[0]) ** 2 + (py - nearest[1]) ** 2) ** 0.5
        if dist < 2.4:
            count += 1
    return count
