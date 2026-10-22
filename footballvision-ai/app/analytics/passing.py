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
) -> tuple[list[MatchEvent], PassCandidate | None]:
    events: list[MatchEvent] = []
    if previous_owner is None or ball_xy is None:
        if current_owner is not None and current_team is not None:
            return events, PassCandidate(current_owner, current_team, time_s, ball_xy or (0, 0), frame)
        return events, open_pass

    if current_owner == previous_owner:
        return events, open_pass or PassCandidate(
            previous_owner, previous_team or TeamId.UNKNOWN, time_s, ball_xy, frame
        )

    if open_pass is None:
        if current_owner is not None and current_team is not None:
            return events, PassCandidate(current_owner, current_team, time_s, ball_xy, frame)
        return events, None

    dt = time_s - open_pass.start_s
    dist = (
        (ball_xy[0] - open_pass.start_xy[0]) ** 2 + (ball_xy[1] - open_pass.start_xy[1]) ** 2
    ) ** 0.5
    same_team = current_team == open_pass.giver_team and current_owner is not None
    plausible = config.events.pass_min_time_s <= dt <= config.events.pass_max_time_s
    long_enough = dist >= config.events.pass_min_distance_m

    if current_owner is None:
        if plausible and long_enough:
            events.append(
                MatchEvent(
                    EventType.FAILED_PASS,
                    time_s,
                    frame,
                    open_pass.giver_id,
                    open_pass.giver_team,
                    x=ball_xy[0],
                    y=ball_xy[1],
                    confidence=0.55,
                    extra={"distance_m": round(dist, 2)},
                )
            )
        return events, None

    if same_team and current_owner != open_pass.giver_id and plausible and long_enough:
        events.append(
            MatchEvent(
                EventType.SUCCESSFUL_PASS,
                time_s,
                frame,
                open_pass.giver_id,
                open_pass.giver_team,
                related_player_id=current_owner,
                x=ball_xy[0],
                y=ball_xy[1],
                confidence=min(0.92, 0.6 + dist / 20),
                extra={"distance_m": round(dist, 2), "duration_s": round(dt, 2)},
            )
        )
        events.append(
            MatchEvent(
                EventType.PASS,
                time_s,
                frame,
                open_pass.giver_id,
                open_pass.giver_team,
                related_player_id=current_owner,
                x=ball_xy[0],
                y=ball_xy[1],
                confidence=min(0.92, 0.6 + dist / 20),
            )
        )
        return events, PassCandidate(current_owner, current_team or TeamId.UNKNOWN, time_s, ball_xy, frame)

    if current_team != open_pass.giver_team and plausible:
        kind = EventType.INTERCEPTION if not opponent_near else EventType.TACKLE
        events.append(
            MatchEvent(
                kind,
                time_s,
                frame,
                current_owner,
                current_team,
                related_player_id=open_pass.giver_id,
                x=ball_xy[0],
                y=ball_xy[1],
                confidence=0.64 if kind is EventType.TACKLE else 0.7,
                extra={"distance_m": round(dist, 2)},
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
                x=ball_xy[0],
                y=ball_xy[1],
                confidence=0.62,
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
                x=ball_xy[0],
                y=ball_xy[1],
                confidence=0.6,
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
                x=ball_xy[0],
                y=ball_xy[1],
                confidence=0.6,
            )
        )
        return events, PassCandidate(current_owner, current_team or TeamId.UNKNOWN, time_s, ball_xy, frame)

    if current_owner is not None and current_team is not None:
        return events, PassCandidate(current_owner, current_team, time_s, ball_xy, frame)
    return events, None
