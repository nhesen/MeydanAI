from __future__ import annotations

from dataclasses import dataclass

from app.core.config import AppConfig
from app.core.types import EventType, MatchEvent, TeamId


@dataclass
class PassCandidate:
    giver_id: int
    giver_team: TeamId
    start_s: float
    start_xy: tuple[float, float]
    start_frame: int
    metric: bool = True


def detect_passes(
    previous_owner: int | None,
    previous_team: TeamId | None,
    current_owner: int | None,
    current_team: TeamId | None,
    time_s: float,
    frame: int,
    ball_xy: tuple[float, float] | None,
    open_pass: PassCandidate | None,
    config: AppConfig,
    opponent_near: bool,
    *,
    metric: bool = True,
    relative_distance: float | None = None,
) -> tuple[list[MatchEvent], PassCandidate | None]:
    events: list[MatchEvent] = []
    # Keep the last observed contact through flight/missing detections. The
    # flight clock starts at release, not at the beginning of a long dribble.
    if open_pass is not None and time_s - open_pass.start_s > config.events.pass_max_time_s:
        open_pass = None
    if ball_xy is None:
        return events, open_pass
    if current_owner is None:
        return events, open_pass
    if current_team not in {TeamId.HOME, TeamId.AWAY}:
        return events, None
    if open_pass is None or current_owner == open_pass.giver_id:
        return events, PassCandidate(current_owner, current_team, time_s, ball_xy, frame, metric)

    dt = time_s - open_pass.start_s
    dist = (
        (ball_xy[0] - open_pass.start_xy[0]) ** 2
        + (ball_xy[1] - open_pass.start_xy[1]) ** 2
    ) ** 0.5
    measured = metric and open_pass.metric
    if not measured:
        dist = relative_distance or 0.0
    details = {"duration_s": round(dt, 2), "estimated": not measured,
               "evidence": "observed-control-transfer",
               "coordinate_space": "pitch" if measured else "image"}
    details["distance_m" if measured else "separation_body_heights"] = round(dist, 2)
    event_x, event_y = ball_xy if measured else (None, None)
    same_team = current_team == open_pass.giver_team and current_owner is not None
    plausible = config.events.pass_min_time_s <= dt <= config.events.pass_max_time_s
    long_enough = dist >= (config.events.pass_min_distance_m if measured else 1.2)

    if same_team and current_owner != open_pass.giver_id and plausible and long_enough:
        events.append(
            MatchEvent(
                EventType.SUCCESSFUL_PASS,
                time_s,
                frame,
                open_pass.giver_id,
                open_pass.giver_team,
                related_player_id=current_owner,
                x=event_x,
                y=event_y,
                confidence=min(0.85, 0.6 + dist / 40) if measured else 0.6,
                extra=dict(details),
            )
        )
        return events, PassCandidate(
            current_owner, current_team or TeamId.UNKNOWN, time_s, ball_xy, frame, metric
        )

    if (
        current_team in {TeamId.HOME, TeamId.AWAY}
        and open_pass.giver_team in {TeamId.HOME, TeamId.AWAY}
        and current_team != open_pass.giver_team
        and plausible
    ):
        kind = EventType.INTERCEPTION if not opponent_near else EventType.TACKLE
        events.append(
            MatchEvent(
                kind,
                time_s,
                frame,
                current_owner,
                current_team,
                related_player_id=open_pass.giver_id,
                x=event_x,
                y=event_y,
                confidence=0.64 if kind is EventType.TACKLE else 0.7,
                extra=dict(details),
            )
        )
        events.append(
            MatchEvent(
                EventType.FAILED_PASS,
                time_s,
                frame,
                open_pass.giver_id,
                open_pass.giver_team,
                related_player_id=current_owner,
                x=event_x,
                y=event_y,
                confidence=0.62,
                extra=dict(details),
            )
        )
        events.append(
            MatchEvent(
                EventType.TURNOVER,
                time_s,
                frame,
                open_pass.giver_id,
                open_pass.giver_team,
                related_player_id=current_owner,
                x=event_x,
                y=event_y,
                confidence=0.6,
                extra=dict(details),
            )
        )
        events.append(
            MatchEvent(
                EventType.BALL_RECOVERY,
                time_s,
                frame,
                current_owner,
                current_team,
                related_player_id=open_pass.giver_id,
                x=event_x,
                y=event_y,
                confidence=0.6,
                extra=dict(details),
            )
        )
        return events, PassCandidate(
            current_owner, current_team or TeamId.UNKNOWN, time_s, ball_xy, frame, metric
        )

    if current_owner is not None and current_team is not None:
        return events, PassCandidate(
            current_owner, current_team, time_s, ball_xy, frame, metric
        )
    return events, None
