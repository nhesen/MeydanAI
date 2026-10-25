from app.analytics.heatmap import render_heatmap
from app.analytics.restarts import RestartWatch
from app.analytics.shooting import detect_shots
from app.analytics.stats import build_team_stats
from app.calibration.zones import PitchZones
from app.core.types import BallSample, EventType, MatchEvent, TeamId
from app.events.detector import EventDetector
from app.highlights.clips import highlight_events
from tests.conftest import make_ball, make_track


def _shots(config, points, tracks):
    zones = PitchZones.from_config(config)
    window = None
    events = []
    for ball in make_ball(points):
        created, window, _scored = detect_shots(
            ball, 1, TeamId.HOME, tracks, window, zones, config
        )
        events.extend(created)
    return events


def test_hali_saha_shot_can_start_past_a_full_size_penalty_box(config):
    events = _shots(
        config,
        [(i, 20.0 + i * 0.45, 10.0) for i in range(5)] + [(5, 21.8, 10.0)],
        {1: make_track(1, [(0, 20.0, 10.0)], team=TeamId.HOME)},
    )
    assert EventType.SHOT in {item.event_type for item in events}
    shooter = {1: make_track(1, [(0, 30.0, 10.0)], team=TeamId.HOME)}
    on_target = _shots(
        config,
        [(i, 30.0 + i * 0.4, 10.0) for i in range(5)] + [(5, 31.6, 10.0)],
        shooter,
    )
    wide = _shots(
        config,
        [(i, 24.0 + i * 0.4, 12.0) for i in range(5)] + [(5, 25.6, 12.0)],
        shooter,
    )
    assert EventType.SHOT_ON_TARGET in {item.event_type for item in on_target}
    assert EventType.SHOT_OFF_TARGET not in {item.event_type for item in on_target}
    assert EventType.SHOT_OFF_TARGET in {item.event_type for item in wide}
    assert EventType.SHOT_ON_TARGET not in {item.event_type for item in wide}
    shot = next(item for item in on_target if item.event_type is EventType.SHOT)
    assert (EventType.BIG_CHANCE in {item.event_type for item in on_target}) is (
        shot.extra["xg"] >= 0.40
    )


def test_post_rebound_is_woodwork_and_not_a_goal_or_save(config):
    events = _shots(
        config,
        [
            (0, 32.00, 11.40),
            (1, 32.32, 11.40),
            (2, 32.64, 11.40),
            (3, 39.70, 11.48),
            (4, 39.40, 11.48),
            (5, 39.40, 11.48),
        ],
        {},
    )
    kinds = {item.event_type for item in events}
    assert EventType.WOODWORK in kinds
    assert EventType.GOAL not in kinds
    assert EventType.SHOT_ON_TARGET not in kinds
    assert EventType.SAVE not in kinds


def test_corner_and_goal_kick_need_a_wide_exit_then_a_restart(config):
    zones = PitchZones.from_config(config)
    watch = RestartWatch(config, zones)
    taker = {
        7: make_track(7, [(0, 39.0, 1.0), (25, 39.0, 1.0), (50, 38.0, 10.0)], team=TeamId.AWAY)
    }
    corner_balls = make_ball([(0, 40.2, 1.0), (25, 40.0, 0.2)])
    events = []
    for ball in corner_balls:
        events.extend(watch.update(ball, TeamId.HOME, taker, goal_scored=False))
    assert [item.event_type for item in events] == [EventType.CORNER]
    assert events[0].team is TeamId.AWAY
    assert events[0].player_id == 7

    watch = RestartWatch(config, zones)
    kick_balls = make_ball([(0, 40.2, 1.0), (25, 38.5, 10.0), (50, 38.5, 10.0)])
    events = []
    for ball in kick_balls:
        events.extend(watch.update(ball, TeamId.HOME, taker, goal_scored=False))
    assert [item.event_type for item in events] == [EventType.GOAL_KICK]
    assert events[0].team is TeamId.AWAY


def test_uncalibrated_ball_creates_no_shot_corner_or_foul(config):
    detector = EventDetector(config, PitchZones.from_config(config))
    tracks = {
        1: make_track(1, [(0, 12.0, 10.0), (25, 12.0, 10.0)], team=TeamId.HOME),
        7: make_track(7, [(0, 39.0, 1.0), (25, 39.0, 1.0)], team=TeamId.AWAY),
    }
    balls = make_ball([(0, 40.2, 1.0), (25, 40.0, 0.2)])
    for ball in balls:
        ball.calibrated = False
    created = []
    for ball in balls:
        created.extend(detector.update(ball, tracks))
    kinds = {item.event_type for item in created}
    assert EventType.CORNER not in kinds
    assert EventType.GOAL_KICK not in kinds
    assert EventType.SHOT not in kinds
    assert "foul" not in {item.value for item in EventType}
    teams = build_team_stats([], [])
    assert all(team.fouls is None for team in teams)


def test_heatmap_ignores_positions_without_a_measured_pitch(tmp_path):
    measured = make_track(1, [(i, 30.0, 16.0) for i in range(12)])
    unmeasured = make_track(2, [(i, 30.0, 16.0) for i in range(12)])
    for sample in unmeasured.samples:
        sample.calibrated = False
    measured_path = render_heatmap([measured], tmp_path / "measured.png", 40, 20)
    empty_path = render_heatmap([unmeasured], tmp_path / "empty.png", 40, 20)
    import cv2

    measured_image = cv2.imread(measured_path)
    empty_image = cv2.imread(empty_path)
    assert int((empty_image == 255).sum()) > int((measured_image == 255).sum())
    assert int(cv2.absdiff(measured_image, empty_image).max()) > 0


def test_goal_and_its_big_chance_share_one_highlight():
    goal = MatchEvent(EventType.GOAL, 10.0, 250, 1, TeamId.HOME)
    chance = MatchEvent(EventType.BIG_CHANCE, 10.4, 260, 1, TeamId.HOME)
    separate = MatchEvent(EventType.BIG_CHANCE, 20.0, 500, 1, TeamId.HOME)
    passed = MatchEvent(EventType.SUCCESSFUL_PASS, 4.0, 100, 1, TeamId.HOME)
    chosen = highlight_events([passed, chance, goal, separate])
    assert [item.event_type for item in chosen] == [EventType.GOAL, EventType.BIG_CHANCE]
    assert chosen[1].time_s == 20.0


def test_paused_corner_without_an_exit_is_not_a_corner(config):
    watch = RestartWatch(config, PitchZones.from_config(config))
    taker = {7: make_track(7, [(0, 39.0, 0.4)], team=TeamId.AWAY)}
    ball = BallSample(
        frame=0,
        time_s=0.0,
        pixel=(800, 8),
        world=(40.0, 0.2),
        confidence=0.9,
        velocity_mps=(0.0, 0.0),
    )
    assert watch.update(ball, TeamId.AWAY, taker, goal_scored=False) == []
