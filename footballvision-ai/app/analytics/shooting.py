from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from app.analytics.xg import expected_goals, goal_angle
from app.calibration.zones import PitchZones
from app.core.config import AppConfig
from app.core.types import BallSample, EventType, MatchEvent, PlayerTrack, Role, TeamId


@dataclass
class ShotWindow:
    player_id: int
    team: TeamId
    start_s: float
    start_xy: tuple[float, float]
    toward_left: bool
    frames: int = 1
    max_speed_kmh: float = 0.0
    observed_frames: int = 1
    goal_frames: int = 0
    last_goal_frame: int | None = None
    last_goal_xy: tuple[float, float] | None = None
    min_post_m: float = 99.0
    post_approach: bool = False
    post_rebound: bool = False
    arrival_on_target: bool = False


def _shot_reach_m(length_m: float) -> float:
    """Small-sided shots start beyond a full-size penalty box."""
    if length_m < 70:
        return length_m * 0.55
    return max(18.0, length_m * 0.35)


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
    toward_left = window.toward_left if window is not None else bool(ball.velocity_mps and ball.velocity_mps[0] < 0)
    aligned = _toward_goal(ball, toward_left)
    goal = zones.goal_center(toward_left)
    vx, vy = ball.velocity_mps or (0.0, 0.0)
    arrival_y = ball.world[1] + vy * (goal[0]-ball.world[0]) / vx if abs(vx) > 0.4 else float("inf")
    threatening = (abs(goal[0]-ball.world[0]) <= _shot_reach_m(zones.length_m)
                   and abs(arrival_y-goal[1]) <= config.pitch.goal_width_m*1.5)
    in_goal = zones.in_goal(*ball.world, config.pitch.goal_width_m, toward_left)
    observed = not ball.interpolated and ball.calibrated and ball.confidence >= 0.35
    if window is not None and in_goal and observed:
        window.goal_frames = window.goal_frames+1 if window.last_goal_frame is None or ball.frame-window.last_goal_frame <= 3 else 1
        window.last_goal_frame = ball.frame
        window.last_goal_xy = ball.world
    opening = (
        not in_goal
        and observed
        and owner_id is not None
        and owner_team in {TeamId.HOME, TeamId.AWAY}
        and speed >= config.events.shot_min_speed_kmh
        and aligned
        and threatening
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
            window.observed_frames += int(observed)
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
    if window is not None and observed:
        _track_shot_geometry(ball, window, zones, config, window.toward_left)
    if opening or in_flight:
        return events, window, False

    if window is not None and in_goal and observed and window.goal_frames < config.events.goal_min_frames:
        return events, window, False
    if window is None or window.observed_frames < config.events.shot_min_frames:
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
    keeper_now = _keeper_distance(tracks, window.team, ball.world)
    woodwork = (
        window.post_rebound
        and window.min_post_m <= 0.35
        and window.goal_frames == 0
        and (keeper_now is None or keeper_now > 1.5)
    )
    on_target = (window.goal_frames > 0 or window.arrival_on_target) and not woodwork
    scored = False
    if window.goal_frames >= config.events.goal_min_frames:
        scored = True
    shot_type = EventType.SHOT_ON_TARGET if on_target else EventType.SHOT_OFF_TARGET
    extra = {
        "distance_m": round(dist, 2),
        "angle_deg": round(angle * 180 / 3.1416, 1),
        "xg": xg,
        "speed_kmh": round(window.max_speed_kmh, 1),
        "zone": zones.band(window.start_xy[0], window.start_xy[1], attacking_home=window.team is TeamId.HOME),
        "on_target": on_target,
        "big_chance": xg >= 0.40,
        "verification_required": True,
        "goal_evidence_frames": window.goal_frames,
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
    if extra["big_chance"]:
        events.append(
            MatchEvent(
                EventType.BIG_CHANCE,
                ball.time_s,
                ball.frame,
                window.player_id,
                window.team,
                x=window.start_xy[0],
                y=window.start_xy[1],
                confidence=min(0.8, 0.45 + xg),
                extra=extra,
            )
        )
    if woodwork:
        events.append(
            MatchEvent(
                EventType.WOODWORK,
                ball.time_s,
                ball.frame,
                window.player_id,
                window.team,
                x=ball.world[0],
                y=ball.world[1],
                confidence=0.62,
                extra={**extra, "post_distance_m": round(window.min_post_m, 2)},
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
        keeper = _nearest_keeper(tracks, window.team, ball.world)
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


def _track_shot_geometry(
    ball: BallSample,
    window: ShotWindow | None,
    zones: PitchZones,
    config: AppConfig,
    toward_left: bool,
) -> None:
    if window is None or ball.world is None:
        return
    dist = _post_distance(ball.world, zones, config.pitch.goal_width_m)
    window.min_post_m = min(window.min_post_m, dist)
    toward = _toward_goal(ball, toward_left)
    if dist <= 0.35 and toward:
        window.post_approach = True
    elif window.post_approach and not toward and dist <= 0.9:
        window.post_rebound = True
    if _arrival_inside_posts(ball, toward_left, zones, config.pitch.goal_width_m):
        window.arrival_on_target = True


def _post_distance(point: tuple[float, float], zones: PitchZones, goal_width_m: float) -> float:
    half = goal_width_m / 2
    center = zones.width_m / 2
    posts = (
        (0.0, center - half),
        (0.0, center + half),
        (zones.length_m, center - half),
        (zones.length_m, center + half),
    )
    return min(hypot(point[0] - px, point[1] - py) for px, py in posts)


def _arrival_inside_posts(
    ball: BallSample, toward_left: bool, zones: PitchZones, goal_width_m: float
) -> bool:
    if ball.world is None or ball.velocity_mps is None:
        return False
    goal_x, goal_y = zones.goal_center(toward_left)
    vx, vy = ball.velocity_mps
    if toward_left and vx >= -0.4 or not toward_left and vx <= 0.4:
        return False
    travel = (goal_x - ball.world[0]) / vx
    if travel < -0.05:
        return False
    arrival_y = ball.world[1] + vy * travel
    return abs(arrival_y - goal_y) <= goal_width_m / 2 + 0.12


def _nearest_keeper(tracks: dict[int, PlayerTrack], shooting_team: TeamId, ball_xy: tuple[float, float]) -> int | None:
    keepers = [
        track
        for track in tracks.values()
        if track.role is Role.GOALKEEPER and track.team not in {shooting_team, TeamId.UNKNOWN}
        and track.last and track.last.world and track.last.calibrated
    ]
    keeper = min(keepers, key=lambda track: (track.last.world[0]-ball_xy[0])**2+(track.last.world[1]-ball_xy[1])**2, default=None)
    if keeper is None:
        return None
    distance = ((keeper.last.world[0]-ball_xy[0])**2+(keeper.last.world[1]-ball_xy[1])**2)**0.5
    return keeper.track_id if distance <= 2.5 else None


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
