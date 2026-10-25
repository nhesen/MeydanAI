from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from app.worker.analyzer import TrackSample
from app.worker.footballvision import _calibrated_intensity, _track_evidence
from app.worker.jersey_ocr import JerseyObservation, JerseyReader, jersey_consensus


def test_jersey_requires_independent_matching_high_score_frames() -> None:
    assert jersey_consensus([JerseyObservation(17, 0.99, 0)]) == {}
    assert jersey_consensus([JerseyObservation(17, 0.99, 0), JerseyObservation(17, 0.99, 0)]) == {}
    assert (
        jersey_consensus([JerseyObservation(17, 0.99, 0), JerseyObservation(17, 0.99, 499)]) == {}
    )
    assert (
        jersey_consensus([JerseyObservation(17, 0.99, 0), JerseyObservation(17, 0.92, 1000)]) == {}
    )
    assert jersey_consensus(
        [JerseyObservation(17, 0.99, 0), JerseyObservation(17, 0.96, 1000)]
    ) == {
        "jersey_candidate": 17,
        "jersey_confidence": 0.96,
        "ocr_observations": 2,
    }


def test_jersey_ambiguity_and_invalid_values_remain_unknown() -> None:
    assert (
        jersey_consensus(
            [
                JerseyObservation(17, 0.99, 0),
                JerseyObservation(7, 0.99, 0),
                JerseyObservation(17, 0.99, 1000),
                JerseyObservation(7, 0.99, 1000),
            ]
        )
        == {}
    )
    assert (
        jersey_consensus(
            [
                JerseyObservation(100, 0.99, 0),
                JerseyObservation(100, 0.99, 1000),
                JerseyObservation(17, float("nan"), 0),
                JerseyObservation(17, 1.5, 1000),
            ]
        )
        == {}
    )


def test_ocr_reads_crop_numbers_as_suggestions_only(tmp_path: Path) -> None:
    crop = tmp_path / "player.jpg"
    cv2.imwrite(str(crop), np.zeros((160, 60, 3), dtype=np.uint8))
    reader = JerseyReader(
        engine=lambda _image, **_kwargs: SimpleNamespace(
            txts=["17", "sponsor"], scores=[0.99, 0.999]
        )
    )
    result = reader.read([(crop, 0), (crop, 1000)])
    assert result["jersey_candidate"] == 17
    assert "player_id" not in result
    assert "confirmed" not in result


def test_intensity_never_bridges_uncalibrated_frames_or_scene_cuts() -> None:
    points = [
        {"timestamp_ms": 0, "x": 0.1, "y": 0.2, "calibrated": True, "segment_id": 0},
        {"timestamp_ms": 500, "x": 0.2, "y": 0.2, "calibrated": False, "segment_id": 0},
        {"timestamp_ms": 1000, "x": 0.3, "y": 0.2, "calibrated": True, "segment_id": 1},
    ]
    assert _calibrated_intensity(points, 40, 20, True) == []
    assert _calibrated_intensity([points[0], points[-1]], 40, 20, True) == []
    measured = [
        {"timestamp_ms": 0, "x": 0.1, "y": 0.2, "calibrated": True},
        {"timestamp_ms": 500, "x": 0.15, "y": 0.2, "calibrated": True},
    ]
    assert _calibrated_intensity(measured, 40, 20, True) == [(0, 1, 40.0)]


def test_ocr_accepts_unicode_paths_and_skips_unreadable_images(tmp_path: Path) -> None:
    folder = tmp_path / "Meydan\u0130-\u0259"
    folder.mkdir()
    crop = folder / "oyun\u00e7u.jpg"
    ok, encoded = cv2.imencode(".jpg", np.zeros((160, 60, 3), dtype=np.uint8))
    assert ok
    crop.write_bytes(encoded.tobytes())
    reader = JerseyReader(
        engine=lambda _image, **_kwargs: SimpleNamespace(txts=["17"], scores=[0.99])
    )
    assert reader.read([(crop, 0), (crop, 1000)])["jersey_candidate"] == 17
    corrupt = folder / "corrupt.jpg"
    corrupt.write_bytes(b"not an image")
    assert reader.read([(folder / "missing.jpg", 0), (corrupt, 1000)]) == {}


def test_reference_images_cannot_escape_job_output(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    outside = tmp_path / "outside.jpg"
    cv2.imwrite(str(outside), np.zeros((160, 60, 3), dtype=np.uint8))
    payload = {
        "image_path": str(outside),
        "evidence_images": [{"path": str(outside), "timestamp_ms": 0}],
    }
    result = _track_evidence(
        output,
        payload,
        [TrackSample(0, 0.2, 0.3), TrackSample(1000, 0.3, 0.4)],
        JerseyReader(enabled=False),
    )
    assert result == {"first_seen_ms": 0, "last_seen_ms": 1000}
