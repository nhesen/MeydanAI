from __future__ import annotations

from collections import defaultdict

from app.analytics.physics import summarize_motion
from app.analytics.rating import mvp_score, rate_player
from app.calibration.zones import PitchZones
from app.core.config import AppConfig
from app.core.types import (
    EventType,
    MatchEvent,
    PlayerStats,
    PlayerTrack,
    Role,
    TeamId,
    TeamStats,
)


def build_player_stats(
    tracks: dict[int, PlayerTrack],
    events: list[MatchEvent],
    possession_frames: dict[int, int],
    total_poss_frames: int,
    config: AppConfig,
    zones: PitchZones,
    sample_period_s: float = 0.04,
    calibrated: bool = True,
) -> list[PlayerStats]:
    grouped: dict[int, list[MatchEvent]] = defaultdict(list)
    for event in events:
        if event.player_id is not None:
            grouped[event.player_id].append(event)
    players: list[PlayerStats] = []
    denom = total_poss_frames or 1
    for track in tracks.values():
        if track.role not in {Role.PLAYER, Role.GOALKEEPER}:
            continue
        motion = summarize_motion(track, config, lambda x, y: zones.cell(x, y))
        ev = grouped.get(track.track_id, [])
        on_ball = possession_frames.get(track.track_id, 0)
        successful = _count(ev, EventType.SUCCESSFUL_PASS)
        failed = _count(ev, EventType.FAILED_PASS)
        total_passes = successful + failed
        stats = PlayerStats(
            track_id=track.track_id,
            team=track.team,
            role=track.role,
            name=track.name,
            jersey=track.jersey,
            distance_m=motion.distance_m if calibrated else None,
            avg_speed_kmh=motion.avg_speed_kmh if calibrated else None,
            max_speed_kmh=motion.max_speed_kmh if calibrated else None,
            sprint_count=motion.sprint_count if calibrated else None,
            active_seconds=motion.active_seconds,
            on_ball_seconds=round(on_ball * sample_period_s, 2),
            off_ball_seconds=round(
                max(0.0, motion.active_seconds - on_ball * sample_period_s), 2
            ),
            possession_pct=round(100.0 * on_ball / denom, 2),
            passes=total_passes,
            successful_passes=successful,
            failed_passes=failed,
            pass_accuracy=None
            if total_passes == 0
            else round(100.0 * successful / total_passes, 1),
            key_passes=_count(ev, EventType.KEY_PASS),
            assists=_count(ev, EventType.ASSIST),
            shots=_count(ev, EventType.SHOT),
            shots_on_target=_count(ev, EventType.SHOT_ON_TARGET),
            goals=_count(ev, EventType.GOAL),
            tackles=_count(ev, EventType.TACKLE),
            interceptions=_count(ev, EventType.INTERCEPTION),
            turnovers=_count(ev, EventType.TURNOVER),
            recoveries=_count(ev, EventType.BALL_RECOVERY),
            dribbles=_count(ev, EventType.DRIBBLE),
            saves=_count(ev, EventType.SAVE),
            zone_activity=motion.zone_activity,
            rating=0.0,
            mvp_score=0.0,
            measured_seconds=motion.measured_seconds if calibrated else 0.0,
            calibration_coverage=sum(item.calibrated for item in track.samples) / max(1, len(track.samples)) if calibrated else 0.0,
            peak_speed_at_ms=round(motion.peak_speed_at_s*1000) if calibrated and motion.peak_speed_at_s is not None else None,
        )
        stats.rating = rate_player(stats)
        stats.mvp_score = mvp_score(stats)
        players.append(stats)
    players.sort(key=lambda item: item.mvp_score or 0.0, reverse=True)
    return players


def build_team_stats(
    players: list[PlayerStats], events: list[MatchEvent]
) -> list[TeamStats]:
    result: list[TeamStats] = []
    for team in (TeamId.HOME, TeamId.AWAY):
        members = [item for item in players if item.team is team]
        team_events = [event for event in events if event.team is team]
        passes = sum(item.passes for item in members)
        successful = sum(item.successful_passes for item in members)
        distances = [item.distance_m for item in members if item.distance_m is not None]
        shot_xg = [
            float(event.extra["xg"])
            for event in team_events
            if event.event_type is EventType.SHOT
            and not event.extra.get("estimated")
            and isinstance(event.extra.get("xg"), (int, float))
        ]
        result.append(
            TeamStats(
                team=team,
                possession_pct=round(sum(item.possession_pct for item in members), 1),
                passes=passes,
                pass_accuracy=None
                if passes == 0
                else round(100.0 * successful / passes, 1),
                shots=sum(item.shots for item in members),
                shots_on_target=sum(item.shots_on_target for item in members),
                goals=_count(team_events, EventType.GOAL),
                tackles=sum(item.tackles for item in members),
                interceptions=sum(item.interceptions for item in members),
                corners=_count(team_events, EventType.CORNER),
                distance_m=None if not distances else round(sum(distances), 1),
                xg=None if not shot_xg else round(sum(shot_xg), 2),
                big_chances=_count(team_events, EventType.BIG_CHANCE),
                saves=_count(team_events, EventType.SAVE),
                goal_kicks=_count(team_events, EventType.GOAL_KICK),
                woodwork=_count(team_events, EventType.WOODWORK),
                fouls=None,
            )
        )
    return result


# These are counted from the image even when the pitch has no metre calibration.
# Shots, goals and xG stay out of that set: they need a trusted pitch.
_IMAGE_EVENTS = {
    EventType.PASS,
    EventType.SUCCESSFUL_PASS,
    EventType.FAILED_PASS,
    EventType.TACKLE,
    EventType.INTERCEPTION,
    EventType.TURNOVER,
    EventType.BALL_RECOVERY,
}


def _count(events: list[MatchEvent], kind: EventType) -> int:
    return sum(
        1
        for event in events
        if event.event_type is kind
        and (kind in _IMAGE_EVENTS or not event.extra.get("estimated"))
    )
