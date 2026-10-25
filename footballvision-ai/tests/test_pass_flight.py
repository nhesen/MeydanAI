from app.analytics.passing import detect_passes
from app.analytics.possession import PossessionEngine
from app.analytics.physics import count_sprints
from app.core.config import with_video_calibration
from app.core.types import EventType, TeamId
from tests.conftest import make_ball, make_track


def step(config, candidate, owner, time, xy):
    return detect_passes(None, None, owner, TeamId.HOME if owner else None,
                         time, round(time * 25), xy, candidate, config, False)


def test_pass_survives_long_dribble_and_unowned_flight(config):
    _, candidate = step(config, None, 1, 0, (0, 0))
    for i in range(1, 151):
        events, candidate = step(config, candidate, 1, i / 25, (i / 25, 0))
        assert not events
    for i in range(151, 175):
        events, candidate = step(config, candidate, None, i / 25, (10, 0))
        assert not events and candidate is not None
    events, _ = step(config, candidate, 2, 7, (16, 0))
    passed = [event for event in events if event.event_type == EventType.SUCCESSFUL_PASS]
    assert len(passed) == 1
    assert passed[0].extra['duration_s'] == 1.0
    assert passed[0].extra['estimated'] is False


def test_missing_ball_does_not_invent_failed_pass_or_late_completion(config):
    _, candidate = step(config, None, 1, 0, (0, 0))
    events, candidate = step(config, candidate, None, 1, None)
    assert not events and candidate is not None
    events, candidate = step(config, candidate, None, 4, None)
    assert not events and candidate is None
    events, _ = step(config, candidate, 2, 4.2, (20, 0))
    assert not events


def test_possession_does_not_attribute_flight_or_interpolation(config):
    engine = PossessionEngine(config)
    track = make_track(1, [(0, 1, 1)])
    ball = make_ball([(0, 1, 1)])[0]
    assert engine.update(ball, {1: track}).player_id == 1
    ball.interpolated = True
    assert engine.update(ball, {1: track}).player_id is None
    assert engine.state.timeline[-1]['player_id'] is None


def test_sprint_requires_duration_and_breaks_at_measurement_gap(config):
    assert count_sprints([(0, .4, 25), (.4, .8, 10)], config) == 0
    assert count_sprints([(0, .6, 25), (1, 1.6, 25)], config) == 0
    assert count_sprints([(0, .6, 25), (.6, 1.2, 25)], config) == 1
    assert count_sprints([(0, 1, 20), (1, 1.4, 17), (1.4, 2, 20)], config) == 1


def test_pitch_change_uses_full_pitch_sprint_threshold(config):
    full = with_video_calibration(config, {'mode': 'automatic', 'pitch_mode': '11v11'})
    assert full.tracking.sprint_kmh == 24
    assert config.tracking.sprint_kmh == 18


def test_relative_pass_has_no_invented_metres(config):
    from app.analytics.passing import PassCandidate
    candidate = PassCandidate(1, TeamId.HOME, 0, (600, 300), 0, False)
    events, _ = detect_passes(None, None, 2, TeamId.HOME, 1, 25, (800, 300),
                              candidate, config, False, metric=False, relative_distance=3)
    event = next(e for e in events if e.event_type == EventType.SUCCESSFUL_PASS)
    assert event.x is None and event.y is None
    assert 'distance_m' not in event.extra
    assert event.extra['estimated']


def test_ball_tracker_rejects_distant_false_detection(config):
    from app.core.types import BBox, Detection, Role
    from app.tracking.ball_tracker import BallTracker
    tracker = BallTracker(config)
    tracker.update([Detection(BBox(50, 50, 56, 56), .8, Role.BALL)], 0, 0, lambda x, y: (x, y))
    ball = tracker.update([Detection(BBox(800, 50, 806, 56), .99, Role.BALL)], 1, .04, lambda x, y: (x, y))
    assert ball.interpolated
    assert ball.pixel[0] < 100


def test_fast_flyby_cannot_confirm_possession(config):
    from app.core.types import BBox
    engine = PossessionEngine(config)
    config.events.possession_min_frames = 4
    for frame in range(6):
        track = make_track(1, [(frame, 10, 10)])
        track.last.bbox = BBox(190, 140, 210, 200)
        ball = make_ball([(frame, 10, 10)])[0]
        ball.pixel = (150 + frame * 20, 200)
        ball.calibrated = False
        assert engine.update(ball, {1: track}).player_id is None


def test_shirt_color_groups_ignore_lighting_and_refresh_votes():
    import numpy as np
    from app.core.types import BBox, Role, TeamId
    from app.tracking.teams import TeamAssigner, lab_median
    teams = TeamAssigner()
    for track_id, rgb in enumerate([(230,230,230), (100,100,100), (245,245,245),
                                   (100,230,30), (50,130,15), (110,245,35)], 1):
        frame = np.full((100,60,3), rgb[::-1], dtype=np.uint8)
        feature = lab_median(frame, BBox(0,0,60,100))
        for _ in range(4):
            teams.observe(track_id, feature, Role.PLAYER)
    assert teams.fit()
    assert teams.team(1) == teams.team(2) == teams.team(3) != TeamId.UNKNOWN
    assert teams.team(4) == teams.team(5) == teams.team(6) != teams.team(1)
    before = {key: votes.copy() for key, votes in teams.votes.items()}
    assert teams.fit()
    assert dict(teams.votes) == before
