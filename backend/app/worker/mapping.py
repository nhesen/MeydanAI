from __future__ import annotations

from app.schemas.processing import WorkerAssignmentContext
from app.worker.analyzer import PlayerMotionResult


def map_tracks_to_assignments(
    tracks: list[PlayerMotionResult],
    assignments: list[WorkerAssignmentContext],
) -> list[tuple[WorkerAssignmentContext, PlayerMotionResult]]:
    if not tracks or not assignments:
        return []

    ranked = sorted(tracks, key=lambda item: item.activity_count, reverse=True)
    home = [item for item in assignments if item.side == "home"]
    away = [item for item in assignments if item.side == "away"]
    if not home:
        home = assignments
        away = []
    if not away:
        away = []

    home_tracks = [track for track in ranked if track.positions and _median_x(track) < 0.5]
    away_tracks = [track for track in ranked if track not in home_tracks]
    paired: list[tuple[WorkerAssignmentContext, PlayerMotionResult]] = []
    paired.extend(_pair(home, home_tracks))
    paired.extend(_pair(away, away_tracks))
    if len(paired) < min(len(assignments), len(ranked)):
        used_players = {item[0].player_id for item in paired}
        used_tracks = {item[1].track_id for item in paired}
        leftover_players = [item for item in assignments if item.player_id not in used_players]
        leftover_tracks = [item for item in ranked if item.track_id not in used_tracks]
        paired.extend(_pair(leftover_players, leftover_tracks))
    return paired


def _pair(
    players: list[WorkerAssignmentContext],
    tracks: list[PlayerMotionResult],
) -> list[tuple[WorkerAssignmentContext, PlayerMotionResult]]:
    ordered_players = sorted(players, key=lambda item: item.jersey_number)
    return list(zip(ordered_players, tracks, strict=False))


def _median_x(track: PlayerMotionResult) -> float:
    values = [sample.x for sample in track.positions]
    if not values:
        return 0.5
    middle = sorted(values)[len(values) // 2]
    return middle
