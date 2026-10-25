import json
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.schemas.processing import WorkerAssignmentContext
from app.worker.analyzer import PlayerMotionResult, TrackSample
from app.worker.api import WorkerApiError
from app.worker.footballvision import _publish_clip, load_motion_results
from app.worker.mapping import map_tracks_to_assignments
from app.worker.runner import process_job


def test_team_detection_takes_precedence_over_field_half() -> None:
    home = WorkerAssignmentContext(
        player_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
        team_name="Home",
        side="home",
        jersey_number=7,
        display_name="Home seven",
    )
    away = home.model_copy(
        update={"player_id": uuid.uuid4(), "team_id": uuid.uuid4(), "side": "away"}
    )
    home_track = PlayerMotionResult(
        track_id="1",
        positions=[TrackSample(0, 0.8, 0.5), TrackSample(1000, 0.81, 0.5)],
        rating=6,
        distance_m=None,
        avg_speed_kmh=None,
        max_speed_kmh=None,
        sprint_count=None,
        active_seconds=1,
        activity_count=2,
        peak_speed_at_ms=None,
        intensity=[],
        events=[],
        frame_width=1920,
        frame_height=1080,
        team="home",
    )
    away_track = replace(
        home_track, track_id="2", team="away", positions=[TrackSample(0, 0.2, 0.5)]
    )
    assert map_tracks_to_assignments([away_track, home_track], [home, away]) == [
        (home, home_track),
        (away, away_track),
    ]
    # A brief but observed passer must not disappear behind long background tracks.
    passer = replace(home_track, track_id="3", activity_count=1,
                     events=[("successful_pass", 100, None, "Possible successful pass")])
    assert map_tracks_to_assignments([home_track, passer], [home])[0][1] is passer


def test_worker_rejects_sibling_video_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "videos"
    root.mkdir()
    sibling = tmp_path / "videos-other"
    sibling.mkdir()
    (sibling / "clip.mp4").write_bytes(b"test")
    api = Mock()
    api.get_context.return_value = {
        "status": "queued",
        "assignments": [],
        "source_reference": "../videos-other/clip.mp4",
    }
    analyzer = Mock()
    monkeypatch.setattr("app.worker.runner.analyze_video", analyzer)
    process_job(api, root, uuid.uuid4())
    analyzer.assert_not_called()
    assert api.update_state.call_args.args[1]["error_code"] == "INVALID_VIDEO"


def test_claim_conflict_never_fails_another_workers_job(tmp_path: Path) -> None:
    api = Mock()
    api.get_context.return_value = {
        "status": "queued",
        "assignments": [],
        "source_reference": "clip.mp4",
    }
    api.update_state.side_effect = WorkerApiError(409, "JOB_STATE_CONFLICT")
    process_job(api, tmp_path, uuid.uuid4())
    assert api.update_state.call_count == 1
    assert api.update_state.call_args.args[1]["expected_status"] == "queued"


def test_unexpected_inference_error_marks_job_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "clip.mp4").write_bytes(b"test")
    api = Mock()
    api.get_context.return_value = {
        "status": "queued",
        "assignments": [],
        "source_reference": "clip.mp4",
    }
    monkeypatch.setattr(
        "app.worker.runner.analyze_video", Mock(side_effect=RuntimeError("CUDA failure"))
    )
    process_job(api, tmp_path, uuid.uuid4())
    assert api.update_state.call_args.args[1]["status"] == "failed"


def test_clip_export_is_contained_and_playable_url_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    storage = tmp_path / "storage"
    monkeypatch.setenv("VIDEO_STORAGE_PATH", str(storage))
    clip = output / "goal.mp4"
    clip.write_bytes(b"test video")
    (tmp_path / "outside.mp4").write_bytes(b"private file")
    assert _publish_clip(output, tmp_path / "outside.mp4") is None
    (output / "tracks.json").write_text(
        json.dumps(
            {
                "1": {
                    "role": "player",
                    "team": "home",
                    "positions": [
                        {"timestamp_ms": 0, "x": 0.2, "y": 0.5},
                        {"timestamp_ms": 1000, "x": 0.3, "y": 0.5},
                    ],
                }
            }
        )
    )
    (output / "events.csv").write_text(f"event_type,time_s,player_id,clip_path\ngoal,1,1,{clip}\n")
    result = load_motion_results(output)[0]
    url = result.event_media[1000]["video_url"]
    assert url.startswith("/api/v1/public/media/highlights/")
    assert (storage / "highlights" / url.rsplit("/", 1)[1]).read_bytes() == b"test video"
