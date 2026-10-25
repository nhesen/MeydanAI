from app.analytics.physics import summarize_motion
from app.analytics.physics import motion_intensity
import numpy as np
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


def test_estimated_samples_never_join_into_metric_distance(config):
    track = make_track(1, [(i, i*0.08, 10) for i in range(50)])
    for sample in track.samples[20:30]:
        sample.world = (35, 19)
        sample.calibrated = False
    summary = summarize_motion(track, config)
    assert summary.distance_m is not None
    assert summary.distance_m < 3.2
    assert summary.measured_seconds < 1.6
    assert summary.max_speed_kmh < 8
    intensity = motion_intensity(track, config)
    assert len(intensity) == 1
    assert intensity[0]["intensity"] < 25


def test_median_windows_suppress_stationary_detection_jitter(config):
    rng = np.random.default_rng(7)
    track = make_track(1, [(i, 10+float(rng.normal(0, 0.08)), 10) for i in range(150)])
    summary = summarize_motion(track, config)
    assert summary.distance_m is not None
    assert summary.distance_m < 2.0
    assert summary.avg_speed_kmh < 2.0
