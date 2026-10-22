import json
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.demo.main import create_app
from app.demo.metrics import Calibration, ground_point, summarize_track


def calibration():
    return Calibration(
        points=[(0, 0), (1, 0), (1, 1), (0, 1)], length_m=40, width_m=20, fixed_camera=True
    )


def sample(t, x, ground=True, segment=0):
    return {
        "t": t,
        "x": x / 40,
        "y": 0.5,
        "confidence": 0.9,
        "ground": [x, 10] if ground else None,
        "segment": segment,
    }


def test_calibration_uses_pitch_geometry_and_rejects_outside():
    cal = calibration()
    assert np.allclose(ground_point(0.5, 0.5, cal, cal.matrix()), (20, 10))
    assert ground_point(1.1, 0.5, cal, cal.matrix()) is None


@pytest.mark.parametrize(
    "points",
    [
        [(0, 0), (1, 1), (0, 1), (1, 0)],
        [(0, 0), (0, 0), (1, 1), (0, 1)],
        [(0, 0), (float("nan"), 0), (1, 1), (0, 1)],
    ],
)
def test_bad_calibration_is_rejected(points):
    with pytest.raises(ValidationError):
        Calibration(points=points, length_m=40, width_m=20, fixed_camera=True)


def test_moving_camera_cannot_claim_metric_calibration():
    data = calibration().model_dump()
    data["fixed_camera"] = False
    with pytest.raises(ValidationError):
        Calibration.model_validate(data)


def test_known_trajectory_has_correct_physical_units():
    result = summarize_track(1, [sample(0, 0), sample(0.4, 2), sample(0.8, 4)], 25, 25, True)
    assert result["distance_m"] == 4
    assert result["avg_speed_kmh"] == 18
    assert result["max_speed_kmh"] == 18
    assert result["measured_seconds"] == 0.8
    assert result["visible_seconds"] == 1


def test_uncalibrated_metrics_are_unknown_not_zero():
    result = summarize_track(1, [sample(0, 0, False), sample(0.4, 4, False)], 10, 25, False)
    assert result["distance_m"] is None
    assert result["max_speed_kmh"] is None


def test_occlusions_and_impossible_jumps_are_not_filled_or_clamped():
    samples = [sample(0, 0), sample(0.4, 30), sample(2, 31), sample(2.4, 33)]
    result = summarize_track(1, samples, 10, 25, True)
    assert result["distance_m"] == 2
    assert result["measured_seconds"] == 0.4
    assert result["rejected_jumps"] == 1
    short_gap = summarize_track(1, [sample(0, 0), sample(0.4, 2, segment=1)], 4, 25, True)
    assert short_gap["distance_m"] is None


def test_stationary_track_reports_zero_when_measured():
    result = summarize_track(1, [sample(0, 5), sample(0.4, 5)], 10, 25, True)
    assert result["distance_m"] == 0
    assert result["avg_speed_kmh"] == 0


def test_upload_job_artifacts_and_single_worker(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def fake_analyze(source, directory, cal, progress):
        assert source.read_bytes() == b"clip"
        entered.set()
        assert release.wait(5)
        progress(90, "test")
        (directory / "report.json").write_text('{"tracks":[]}', encoding="utf-8")
        return {"tracks": []}

    monkeypatch.setattr("app.demo.main.analyze", fake_analyze)
    with TestClient(create_app(tmp_path)) as client:
        response = client.post("/api/jobs", files={"file": ("clip.mp4", b"clip", "video/mp4")})
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert entered.wait(5)
        try:
            assert client.get(f"/api/jobs/{job_id}/report.json").status_code == 409
            assert (
                client.post("/api/jobs", files={"file": ("clip.mp4", b"clip")}).status_code == 409
            )
        finally:
            release.set()
        for _ in range(100):
            state = client.get(f"/api/jobs/{job_id}").json()
            if state["status"] == "completed":
                break
            time.sleep(0.01)
        assert state["status"] == "completed"
        assert client.get(f"/api/jobs/{job_id}/report.json").json() == {"tracks": []}
        assert client.get(f"/api/jobs/{job_id}/source.mp4").status_code == 404
        assert client.get("/api/jobs/not-a-uuid").status_code == 422


def test_upload_validation_and_origin(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/jobs", files={"file": ("x.exe", b"x")}).status_code == 422
        assert client.post("/api/jobs", files={"file": ("x.mp4", b"")}).status_code == 422
        assert (
            client.post(
                "/api/jobs", data={"calibration": "{}"}, files={"file": ("x.mp4", b"x")}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/jobs",
                headers={"Origin": "https://example.com"},
                files={"file": ("x.mp4", b"x")},
            ).status_code
            == 403
        )


def test_restart_marks_interrupted_jobs_failed(tmp_path: Path):
    directory = tmp_path / ("a" * 32)
    directory.mkdir()
    state_path = directory / "state.json"
    state_path.write_text(json.dumps({"status": "processing"}), encoding="utf-8")
    with TestClient(create_app(tmp_path)):
        assert json.loads(state_path.read_text())["status"] == "failed"
