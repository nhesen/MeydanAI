from app.analytics.rating import rate_player
from app.core.types import PlayerStats, Role, TeamId


def _stats(**overrides) -> PlayerStats:
    payload = dict(
        track_id=1,
        team=TeamId.HOME,
        role=Role.PLAYER,
        name=None,
        jersey=7,
        distance_m=20.0,
        avg_speed_kmh=8.0,
        max_speed_kmh=18.0,
        sprint_count=1,
        active_seconds=10.0,
        on_ball_seconds=2.0,
        off_ball_seconds=8.0,
        possession_pct=20.0,
        passes=2,
        successful_passes=2,
        failed_passes=0,
        pass_accuracy=100.0,
        key_passes=0,
        assists=0,
        shots=1,
        shots_on_target=1,
        goals=0,
        tackles=1,
        interceptions=1,
        turnovers=0,
        recoveries=1,
        dribbles=2,
        saves=0,
        zone_activity={},
        rating=0.0,
        mvp_score=0.0,
    )
    payload.update(overrides)
    return PlayerStats(**payload)


def test_unmeasured_player_has_no_rating() -> None:
    rating = rate_player(_stats(
        distance_m=None, avg_speed_kmh=None, max_speed_kmh=None, sprint_count=None,
        measured_seconds=0, passes=0, successful_passes=0, pass_accuracy=None,
        shots=0, shots_on_target=0, tackles=0, interceptions=0, recoveries=0, goals=0,
    ))
    assert rating is None


def test_ten_second_clip_stays_near_average() -> None:
    rating = rate_player(_stats())
    assert 5.8 <= rating <= 6.6


def test_goal_in_a_short_clip_does_not_reach_eight() -> None:
    rating = rate_player(_stats(goals=1, shots=1, shots_on_target=1))
    assert rating < 8.0


def test_full_match_contribution_can_reach_a_high_rating() -> None:
    rating = rate_player(
        _stats(
            active_seconds=25 * 60,
            distance_m=9000,
            sprint_count=12,
            passes=40,
            successful_passes=34,
            pass_accuracy=85.0,
            shots=4,
            shots_on_target=2,
            goals=1,
            assists=1,
        )
    )
    assert rating >= 8.0
