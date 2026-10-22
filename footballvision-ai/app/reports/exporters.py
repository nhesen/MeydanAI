from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.core.types import MatchEvent, PlayerStats, TeamStats


def export_tables(
    output_dir: Path,
    players: list[PlayerStats],
    teams: list[TeamStats],
    events: list[MatchEvent],
    possession: dict[str, float],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    player_path = output_dir / "player_stats.csv"
    team_path = output_dir / "team_stats.csv"
    event_path = output_dir / "events.csv"
    summary_path = output_dir / "match_summary.json"
    _write_csv(
        player_path,
        [
            {
                "player_id": item.track_id,
                "name": item.name or "",
                "jersey": item.jersey if item.jersey is not None else "",
                "team": item.team.value,
                "role": item.role.value,
                "distance_m": item.distance_m,
                "avg_speed_kmh": item.avg_speed_kmh,
                "max_speed_kmh": item.max_speed_kmh,
                "sprint_count": item.sprint_count,
                "on_ball_seconds": item.on_ball_seconds,
                "off_ball_seconds": item.off_ball_seconds,
                "possession_pct": item.possession_pct,
                "passes": item.passes,
                "successful_passes": item.successful_passes,
                "failed_passes": item.failed_passes,
                "pass_accuracy": item.pass_accuracy,
                "key_passes": item.key_passes,
                "assists": item.assists,
                "shots": item.shots,
                "shots_on_target": item.shots_on_target,
                "goals": item.goals,
                "tackles": item.tackles,
                "interceptions": item.interceptions,
                "turnovers": item.turnovers,
                "recoveries": item.recoveries,
                "dribbles": item.dribbles,
                "saves": item.saves,
                "rating": item.rating,
                "mvp_score": item.mvp_score,
            }
            for item in players
        ],
    )
    _write_csv(
        team_path,
        [
            {
                "team": item.team.value,
                "possession_pct": item.possession_pct,
                "passes": item.passes,
                "pass_accuracy": item.pass_accuracy,
                "shots": item.shots,
                "shots_on_target": item.shots_on_target,
                "goals": item.goals,
                "tackles": item.tackles,
                "interceptions": item.interceptions,
                "corners": item.corners,
                "distance_m": item.distance_m,
            }
            for item in teams
        ],
    )
    _write_csv(event_path, [event.to_dict() for event in events])
    summary: dict[str, Any] = {
        "possession": possession,
        "score": {
            "home": next((item.goals for item in teams if item.team.value == "home"), 0),
            "away": next((item.goals for item in teams if item.team.value == "away"), 0),
        },
        "leaders": _leaders(players),
        "player_count": len(players),
        "event_count": len(events),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {
        "player_stats": str(player_path),
        "team_stats": str(team_path),
        "events": str(event_path),
        "match_summary": str(summary_path),
    }


def _leaders(players: list[PlayerStats]) -> dict[str, Any]:
    def pick(key: str, metric):
        valid = [item for item in players if metric(item) is not None]
        if not valid:
            return None
        winner = max(valid, key=metric)
        return {"player_id": winner.track_id, "name": winner.name, "value": metric(winner)}

    return {
        "most_distance": pick("distance", lambda item: item.distance_m or 0),
        "fastest": pick("speed", lambda item: item.max_speed_kmh or 0),
        "most_passes": pick("passes", lambda item: item.passes),
        "most_shots": pick("shots", lambda item: item.shots),
        "mvp": pick("mvp", lambda item: item.mvp_score),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
