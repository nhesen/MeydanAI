from app.analytics.shooting import ShotWindow, detect_shots
from app.calibration.zones import PitchZones
from app.core.types import BallSample, EventType, MatchEvent, TeamId
from app.events.detector import EventDetector


def test_interpolated_ball_cannot_confirm_goal(config):
    zones = PitchZones.from_config(config)
    window = ShotWindow(1, TeamId.HOME, 0, (24, 10), False, frames=4, observed_frames=4)
    ball = BallSample(10, 0.4, (800, 200), (40.2, 10), 0.8, interpolated=True, velocity_mps=(0, 0))
    events, _, scored = detect_shots(ball, None, None, {}, window, zones, config)
    assert not scored
    assert EventType.GOAL not in {event.event_type for event in events}


def test_goal_requires_configured_observed_crossing_frames(config):
    config.events.goal_min_frames = 2
    zones = PitchZones.from_config(config)
    window = ShotWindow(1, TeamId.HOME, 0, (24, 10), False, frames=4, observed_frames=4)
    first = BallSample(10, 0.4, (800, 200), (40.2, 10), 0.8, velocity_mps=(4, 0))
    events, window, scored = detect_shots(first, None, None, {}, window, zones, config)
    assert not events and not scored and window is not None
    second = BallSample(11, 0.44, (802, 200), (40.4, 10), 0.8, velocity_mps=(4, 0))
    events, _, scored = detect_shots(second, None, None, {}, window, zones, config)
    assert scored
    assert next(event for event in events if event.event_type is EventType.GOAL).extra["goal_evidence_frames"] == 2


def test_ball_inside_pitch_is_not_a_goal(config):
    zones = PitchZones.from_config(config)
    assert not zones.in_goal(39.9, 10, 3, left=False)


def test_assist_must_be_same_team_and_pass_to_scorer(config):
    detector = EventDetector(config, PitchZones.from_config(config))
    detector.events = [MatchEvent(EventType.SUCCESSFUL_PASS, 1, 25, 7, TeamId.AWAY, related_player_id=1)]
    assert detector._link_assist(2, 1, TeamId.HOME) == []
    detector.events.append(MatchEvent(EventType.SUCCESSFUL_PASS, 1.2, 30, 2, TeamId.HOME, related_player_id=1))
    linked = detector._link_assist(2, 1, TeamId.HOME)
    assert len(linked) == 2
    assert all(event.player_id == 2 for event in linked)


def test_uncalibrated_ball_resets_pending_shot(config):
    detector = EventDetector(config, PitchZones.from_config(config))
    detector.shot_window = ShotWindow(1, TeamId.HOME, 0, (24, 10), False, frames=4)
    ball = BallSample(10, 0.4, (800, 200), (40.2, 10), 0.9, calibrated=False)
    assert detector.update(ball, {}) == []
    assert detector.shot_window is None
