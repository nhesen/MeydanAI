from __future__ import annotations

from app.core.types import PlayerStats, Role


def rate_player(stats: PlayerStats) -> float:
    goals = stats.goals * 2.4
    assists = stats.assists * 1.6
    shots = min(1.2, stats.shots * 0.18 + stats.shots_on_target * 0.22)
    passing = 0.0
    if stats.pass_accuracy is not None:
        passing = min(1.4, stats.successful_passes * 0.04 + stats.pass_accuracy / 100)
    defense = min(1.3, stats.tackles * 0.18 + stats.interceptions * 0.16 + stats.recoveries * 0.08)
    work = 0.0
    if stats.distance_m is not None:
        work = min(1.4, stats.distance_m / 1200)
    work += min(0.6, stats.sprint_count * 0.08)
    keep = min(1.5, stats.saves * 0.35) if stats.role is Role.GOALKEEPER else 0.0
    turnover_pen = min(1.0, stats.turnovers * 0.12)
    score = 5.4 + goals + assists + shots + passing + defense + work + keep - turnover_pen
    return round(min(9.8, max(4.2, score)), 2)


def mvp_score(stats: PlayerStats) -> float:
    return round(
        rate_player(stats)
        + stats.goals * 0.4
        + stats.assists * 0.25
        + (stats.possession_pct / 40),
        3,
    )
