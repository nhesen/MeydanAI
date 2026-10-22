from app.analytics.physics import summarize_motion
from app.core.config import AppConfig
from tests.conftest import make_track


def test_distance_and_sprint_from_world_path(config: AppConfig) -> None:
    track = make_track(1, [(i, 1.0 + i * 0.4, 10.0) for i in range(20)])
    summary = summarize_motion(track, config)
    assert summary.distance_m is not None and summary.distance_m > 6
    assert summary.max_speed_kmh is not None
    assert summary.rejected_jumps == 0


def test_impossible_jump_is_rejected(config: AppConfig) -> None:
    track = make_track(1, [(0, 1.0, 10.0), (1, 38.0, 10.0)])
    summary = summarize_motion(track, config)
    assert summary.rejected_jumps >= 1
    assert summary.distance_m in {None, 0.0} or summary.distance_m < 5
