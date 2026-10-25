from __future__ import annotations

from app.core.types import PlayerStats, Role


def rate_player(stats: PlayerStats) -> float | None:
    """Rating only from measured running or confirmed events. No default 6."""
    actions = (
        stats.passes + stats.shots + stats.goals + stats.assists
        + stats.tackles + stats.interceptions + stats.saves + stats.recoveries
    )
    if stats.distance_m is None and stats.measured_seconds <= 0 and actions == 0:
        return None
    minutes = max(0.0, stats.active_seconds) / 60.0
    exposure = min(1.0, minutes / 20.0)
    goals = stats.goals * 2.2 * (0.5 + 0.5 * exposure)
    assists = stats.assists * 1.4 * (0.4 + 0.6 * exposure)
    shots = min(1.0, stats.shots * 0.14 + stats.shots_on_target * 0.18) * exposure
    passing = 0.0
    if stats.pass_accuracy is not None and stats.passes >= 4:
        passing = min(1.1, stats.successful_passes * 0.025 + max(0.0, stats.pass_accuracy - 75) / 80)
        passing *= exposure
    defense = min(1.1, stats.tackles * 0.16 + stats.interceptions * 0.14 + stats.recoveries * 0.06)
    defense *= exposure
    work = 0.0
    if stats.distance_m is not None:
        work = min(1.2, stats.distance_m / 1600)
    work += min(0.5, (stats.sprint_count or 0) * 0.06)
    work *= exposure
    keep = min(1.4, stats.saves * 0.3) * exposure if stats.role is Role.GOALKEEPER else 0.0
    turnover_pen = min(0.8, stats.turnovers * 0.1) * exposure
    score = 6.0 + goals + assists + shots + passing + defense + work + keep - turnover_pen
    return round(min(9.6, max(5.8, score)), 2)


def mvp_score(stats: PlayerStats) -> float | None:
    rating = rate_player(stats)
    if rating is None:
        return None
    return round(
        rating
        + stats.goals * 0.4
        + stats.assists * 0.25
        + (stats.possession_pct / 40),
        3,
    )
