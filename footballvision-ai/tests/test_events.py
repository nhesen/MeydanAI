from app.core.config import AppConfig
from app.core.types import EventType, TeamId
from app.pipeline import analyze_observations
from tests.conftest import make_ball, make_track


def test_pass_shot_and_goal_on_synthetic_hali_saha(config: AppConfig, tmp_out) -> None:
    home_a = make_track(1, [(i, 12.0, 10.0) for i in range(0, 40)], team=TeamId.HOME)
    home_b = make_track(2, [(i, 24.0, 10.0) for i in range(0, 40)], team=TeamId.HOME)
    away = make_track(3, [(i, 32.0, 4.0) for i in range(0, 40)], team=TeamId.AWAY)
    ball_points: list[tuple[int, float, float]] = []
    for i in range(0, 10):
        ball_points.append((i, 12.0, 10.0))
    for i in range(10, 20):
        t = (i - 10) / 10
        ball_points.append((i, 12.0 + 12.0 * t, 10.0))
    for i in range(20, 26):
        ball_points.append((i, 24.0, 10.0))
    for i in range(26, 34):
        t = (i - 26) / 8
        ball_points.append((i, 24.0 + 16.5 * t, 10.0))
    ball_points.append((34, 40.2, 10.0))
    result = analyze_observations(
        {1: home_a, 2: home_b, 3: away},
        make_ball(ball_points),
        config,
        tmp_out,
        fps=25,
        calibrated=True,
    )
    kinds = {event.event_type for event in result.events}
    assert EventType.SUCCESSFUL_PASS in kinds
    assert EventType.SHOT in kinds
    assert EventType.GOAL in kinds
    assert result.score[0] >= 1
    home = next(team for team in result.teams if team.team is TeamId.HOME)
    assert home.shots >= 1
    passer = next(player for player in result.players if player.track_id == 1)
    assert passer.successful_passes >= 1
    assert (tmp_out / "player_stats.csv").is_file()
    assert (tmp_out / "events.csv").is_file()
    assert (tmp_out / "match_summary.json").is_file()
    assert (tmp_out / "match_report.html").is_file()
    assert (tmp_out / "heatmaps" / "home.png").is_file()


def test_image_events_stay_visible_when_the_pitch_is_not_measured() -> None:
    from app.analytics.stats import _count
    from app.core.types import MatchEvent

    events = [
        MatchEvent(
            EventType.SUCCESSFUL_PASS, 1.0, 10, 4, TeamId.HOME, extra={"estimated": True}
        ),
        MatchEvent(EventType.SHOT, 2.0, 20, 4, TeamId.HOME, extra={"estimated": True}),
        MatchEvent(EventType.GOAL, 3.0, 30, 4, TeamId.HOME, extra={"estimated": True}),
    ]
    assert _count(events, EventType.SUCCESSFUL_PASS) == 1
    assert _count(events, EventType.SHOT) == 0
    assert _count(events, EventType.GOAL) == 0


def test_reid_merges_gap_with_matching_appearance(config: AppConfig) -> None:
    from app.core.types import BBox, PlayerTrack, TrackSample
    from app.tracking.reid import IdentityRepair

    hist = [0.2] * 20
    first = PlayerTrack(1, team=TeamId.HOME, role=__import__("app.core.types", fromlist=["Role"]).Role.PLAYER)
    first.samples = [
        TrackSample(0, 0.0, (10, 10), BBox(8, 4, 12, 10), (10, 10), 0.9, TeamId.HOME, first.role, hist)
    ]
    second = PlayerTrack(99, team=TeamId.HOME, role=first.role)
    second.samples = [
        TrackSample(8, 0.32, (12, 10), BBox(10, 4, 14, 10), (12, 10), 0.9, TeamId.HOME, first.role, hist)
    ]
    merged = IdentityRepair(config).merge({1: first, 99: second})
    assert 1 in merged
    assert 99 not in merged
    assert 99 in merged[1].merged_from
