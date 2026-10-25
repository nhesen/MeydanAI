import csv
import json

import cv2
import numpy as np
import pytest
from app import pipeline
from app.calibration.homography import PitchMapper, pitch_outline
from app.calibration.keypoints import CalibrationFit
from app.core.types import BBox, Detection, Role, TeamId
from app.tracking.reid import IdentityRepair
from tests.conftest import make_ball, make_track


def test_sparse_calibration_is_not_a_measurement() -> None:
    assert pipeline.measurement_is_trusted(19, 20)
    assert not pipeline.measurement_is_trusted(2, 20)
    assert not pipeline.measurement_is_trusted(9, 20)
    assert not pipeline.measurement_is_trusted(7, 7)


def test_uncalibrated_report_retains_relative_positions_but_no_physical_metrics(
    config, tmp_path
):
    track = make_track(1, [(0, 10, 10), (1, 10.1, 10)], team=TeamId.HOME)
    referee = make_track(2, [(0, 11, 10), (1, 11.1, 10)], role=Role.REFEREE)
    pipeline.analyze_observations(
        {1: track, 2: referee},
        make_ball([(0, 10, 10), (1, 10.1, 10)]),
        config,
        tmp_path,
        calibrated=False,
        frame_width=640,
        frame_height=360,
    )
    summary = json.loads((tmp_path / "match_summary.json").read_text())
    assert summary["calibrated"] is False
    assert summary["calibration_source"] == "relative"
    assert (summary["frame_width"], summary["frame_height"]) == (640, 360)
    tracks = json.loads((tmp_path / "tracks.json").read_text())
    assert set(tracks) == {"1"}
    assert len(tracks["1"]["positions"]) == 2
    with (tmp_path / "player_stats.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["distance_m"] == ""
    assert rows[0]["rating"] == ""
    assert rows[0]["sprint_count"] == ""
    assert float(rows[0]["active_seconds"]) == pytest.approx(0.04)


def test_reidentification_does_not_merge_players_across_camera_cuts(config):
    first = make_track(1, [(0, 10, 10)])
    second = make_track(2, [(1, 10.1, 10)])
    second.segment_id = 1
    for track in (first, second):
        track.samples[0].color_hist = [0.2] * 20
    assert len(IdentityRepair(config).merge({1: first, 2: second})) == 2


def test_automatic_grass_mapping_is_an_estimate(config):
    frame = np.full((100, 200, 3), (40, 120, 40), dtype=np.uint8)
    mapper = pipeline._init_mapper(frame, config, 200, 100, [])
    assert not mapper.calibrated
    assert mapper.to_world(100, 50) is not None


def test_pitch_outline_excludes_technical_area_and_leaves_indoor_fallback():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    frame[20:80, 10:190] = (40, 120, 40)
    outline = pitch_outline(frame)
    assert outline is not None
    assert cv2.pointPolygonTest(outline, (100, 50), False) >= 0
    assert cv2.pointPolygonTest(outline, (100, 95), False) < 0
    assert pitch_outline(np.zeros((100, 200, 3), dtype=np.uint8)) is None


@pytest.mark.parametrize(
    "points",
    [
        [(0, 0)] * 4,
        [(0, 0), (1, 1), (1, 0), (0, 1)],
        [(float("nan"), 0), (1, 0), (1, 1), (0, 1)],
    ],
)
def test_invalid_calibration_rejected(config, points):
    with pytest.raises(ValueError):
        PitchMapper.from_points(points, config, 200, 100)


def test_frame_stride_preserves_rendered_duration(config, tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"
    writer = cv2.VideoWriter(
        str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 100)
    )
    assert writer.isOpened()
    for _ in range(20):
        writer.write(np.full((100, 160, 3), 32, dtype=np.uint8))
    writer.release()

    class Detector:
        def __init__(self, cfg):
            pass

        def detect_many(self, frames):
            return [[Detection(BBox(30, 10, 50, 60), 0.9, Role.PLAYER)] for _ in frames]

    monkeypatch.setattr(pipeline, "FootballDetector", Detector)
    monkeypatch.setenv("FOOTBALLVISION_FRAME_STRIDE", "2")
    monkeypatch.setenv("FOOTBALLVISION_RENDER", "1")
    monkeypatch.setenv("FOOTBALLVISION_PLAYER_CLIPS", "0")
    result = pipeline.analyze_video(source, tmp_path / "out", config)
    cap = cv2.VideoCapture(result.annotated_video)
    try:
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
    finally:
        cap.release()
    assert duration == pytest.approx(2.0, abs=0.1)
    assert result.duration_s == 2.0


def test_per_frame_calibration_failure_preserves_gap_and_player_evidence(config, tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 100))
    for _ in range(20):
        writer.write(np.full((100, 160, 3), 40, dtype=np.uint8))
    writer.release()
    config.pitch.mode = "11v11"
    config.pitch.length_m, config.pitch.width_m = 105, 68
    config.detection.pitch_model = "injected-test-model"
    config.raw = {"calibration": {"mode": "automatic", "points": []}}

    class Detector:
        def __init__(self, cfg):
            pass

        def detect_many(self, frames):
            return [[Detection(BBox(40, 10, 60, 90), 0.9, Role.PLAYER, track_id=1)] for _ in frames]

    class Calibrator:
        def __init__(self, cfg):
            self.index = 0

        def calibrate(self, frame):
            self.index += 1
            if self.index == 10:
                return CalibrationFit(None, {"valid": False, "reason": "insufficient_landmarks", "source": "pitch-keypoints"})
            mapper = PitchMapper.from_points([(0, 0), (1, 0), (1, 1), (0, 1)], config, 160, 100)
            return CalibrationFit(mapper, {"valid": True, "source": "pitch-keypoints", "reason": None, "reprojection_rmse_px": 1.5})

    monkeypatch.setattr(pipeline, "FootballDetector", Detector)
    monkeypatch.setattr(pipeline, "KeypointCalibrator", Calibrator)
    monkeypatch.setenv("FOOTBALLVISION_RENDER", "0")
    monkeypatch.setenv("FOOTBALLVISION_PLAYER_CLIPS", "0")
    pipeline.analyze_video(source, tmp_path / "out", config)
    summary = json.loads((tmp_path / "out" / "match_summary.json").read_text())
    track = json.loads((tmp_path / "out" / "tracks.json").read_text())["1"]
    assert summary["calibrated"]
    assert summary["calibration_coverage"] == 0.95
    assert track["calibration_coverage"] == 0.95
    assert track["positions"][9]["calibrated"] is False
    assert track["measured_seconds"] < 1.8
    assert track["image_path"]
    assert 1 <= len(track["evidence_images"]) <= 3
    assert all(item["height"] >= 80 for item in track["evidence_images"])
