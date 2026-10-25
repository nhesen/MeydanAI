import json
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_processing_integrity import VIDEO, WORKER_HEADERS, claim_job, upload_job
from test_processing_integrity import processing_app as processing_app

from app.models.domain import (
    AuditLog,
    Match,
    PlayerAnalyticsEvent,
    PlayerIntensityBucket,
    ProcessingJob,
    User,
)
from app.schemas.analysis import UploadCalibrationConfig


def complete_analysis(client, *, first_metrics=None, second_calibrated=True):
    match_id, job_id, owner = upload_job(client)
    claim_job(client, job_id)
    roster = client.post(
        f"/api/v1/internal/processing-jobs/{job_id}/detected-roster",
        headers=WORKER_HEADERS,
        json={"track_count": 2},
    ).json()["data"]["assignments"]
    for index, player in enumerate(roster):
        calibrated = index == 0 or second_calibrated
        metrics = {
            "distance_m": (index + 1) * 100,
            "rating": 6 + index,
            "active_seconds": 600,
            "max_speed_kmh": 20,
        }
        if index == 0 and first_metrics:
            metrics.update(first_metrics)
        if not calibrated:
            metrics.update(
                distance_m=None, avg_speed_kmh=None, max_speed_kmh=None, sprint_count=None
            )
        result = client.post(
            f"/api/v1/internal/processing-jobs/{job_id}/analytics",
            headers={**WORKER_HEADERS, "Idempotency-Key": f"review-track-{index}"},
            json={
                "player_id": player["player_id"],
                "team_id": player["team_id"],
                "provider_track_id": str(index + 1),
                "metrics": metrics,
                "positions": [
                    {"timestamp_ms": 0, "x": 0.2 + index * 0.5, "y": 0.5},
                    {"timestamp_ms": 1000, "x": 0.21 + index * 0.5, "y": 0.5},
                ],
                "intensity": [{"from_minute": 0, "to_minute": 1, "intensity": 20 + index * 60}],
                "events": [
                    {
                        "event_type": "goal" if index == 0 else "shot",
                        "timestamp_ms": (index + 1) * 1000,
                        "title": f"Possible event {index}",
                    }
                ],
                "calibration": {
                    "version": "test-v1",
                    "source_frame_width": 1280,
                    "source_frame_height": 720,
                    "pitch_length_m": 40,
                    "pitch_width_m": 20,
                    "transform_metadata": {
                        "method": "manual" if calibrated else "relative",
                        "calibrated": calibrated,
                        "calibration_coverage": 1.0 if calibrated else 0.0,
                        "measured_seconds": metrics["active_seconds"] if calibrated else 0,
                    },
                },
                "track_evidence": {
                    "image_url": f"/api/v1/public/media/tracks/track-{index + 1}.jpg",
                    "first_seen_ms": 0,
                    "last_seen_ms": 1000,
                    "jersey_candidate": 7,
                    "jersey_confidence": 0.97,
                    "ocr_observations": 3,
                },
                "complete_job": index == 1,
            },
        )
        assert result.status_code == 200, result.text
    return match_id, job_id, owner, roster


def test_calibration_geometry_and_upload_configuration_survive_ingestion(processing_app):
    client, session, _ = processing_app
    match_id, job_id, owner, _ = complete_analysis(client)
    job = session.get(ProcessingJob, uuid.UUID(job_id))
    assert job.calibration_metadata["upload_config"]["mode"] == "relative"
    assert job.calibration_metadata["result"]["transform_metadata"]["calibrated"] is True
    assert len(job.calibration_metadata["track_evidence"]) == 2
    manual = {
        "mode": "manual",
        "pitch_mode": "hali_saha",
        "camera_mode": "fixed",
        "length_m": 40,
        "width_m": 20,
        "points": [[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]],
    }
    uploaded = client.post(
        f"/api/v1/matches/{match_id}/processing-jobs",
        headers=owner,
        files={"video": ("manual.mp4", VIDEO, "video/mp4")},
        data={"calibration": json.dumps(manual)},
    )
    assert uploaded.status_code == 202, uploaded.text
    next_job = uploaded.json()["data"]["id"]
    context = client.get(
        f"/api/v1/internal/processing-jobs/{next_job}/context", headers=WORKER_HEADERS
    )
    assert context.json()["data"]["calibration_config"] == manual
    bad = {**manual, "camera_mode": "broadcast"}
    rejected = client.post(
        f"/api/v1/matches/{match_id}/processing-jobs",
        headers=owner,
        files={"video": ("invalid.mp4", VIDEO, "video/mp4")},
        data={"calibration": json.dumps(bad)},
    )
    assert rejected.status_code == 422
    assert rejected.json()["errorCode"] == "INVALID_CALIBRATION"


def test_team_totals_use_available_calibrated_player_intervals(processing_app):
    client, _, _ = processing_app
    match_id, _, _, roster = complete_analysis(client, second_calibrated=False)
    detail = client.get(f"/api/v1/public/matches/{match_id}").json()["data"]
    totals = {row["team_id"]: row for row in detail["team_stats"]}
    measured = totals[roster[0]["team_id"]]
    assert measured["total_distance_m"] == 100
    assert measured["average_speed_kmh"] == 0.6
    if roster[1]["team_id"] != roster[0]["team_id"]:
        unmeasured = totals[roster[1]["team_id"]]
        assert unmeasured["total_distance_m"] is None
        assert unmeasured["average_speed_kmh"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"points": [[0, 0], [1, 1], [1, 0], [0, 1]]},
        {"points": [[0, 0], [1, 0], [1, 0], [0, 1]]},
        {"points": [[-0.1, 0], [1, 0], [1, 1], [0, 1]]},
        {"points": []},
        {"length_m": 0},
        {"width_m": 91},
        {"camera_mode": "broadcast"},
    ],
)
def test_invalid_manual_calibration_is_rejected(overrides):
    valid = {"mode": "manual", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}
    with pytest.raises(ValidationError):
        UploadCalibrationConfig.model_validate({**valid, **overrides})


def test_review_authorization_rejection_and_identity_swap_preserve_data(processing_app):
    client, session, _ = processing_app
    match_id, _, owner, roster = complete_analysis(client)
    match = session.get(Match, uuid.UUID(match_id))
    match.home_score, match.away_score = 3, 2
    session.commit()
    url = f"/api/v1/matches/{match_id}/analysis-review"
    assert client.get(url).status_code == 401
    review = client.get(url, headers=owner).json()["data"]
    assert review["analysis_quality"]["calibrated"] is True
    assert review["analysis_quality"]["identity_mapping"] == "estimated"
    assert review["mappings"][0]["evidence"]["jersey_confidence"] == 0.97
    event_id = review["events"][0]["id"]
    rejected = client.patch(
        f"/api/v1/matches/{match_id}/events/{event_id}/review",
        headers=owner,
        json={"status": "rejected"},
    )
    assert rejected.status_code == 200, rejected.text
    highlights = client.get(f"/api/v1/public/highlights?match_id={match_id}").json()["data"][
        "items"
    ]
    assert len(highlights) == 1
    ids_before = set(session.scalars(select(PlayerIntensityBucket.id)))
    mapping = next(item for item in review["mappings"] if item["provider_track_id"] == "1")
    swapped = client.patch(
        f"/api/v1/matches/{match_id}/track-mappings/{mapping['id']}/review",
        headers=owner,
        json={"player_id": roster[1]["player_id"], "team_id": roster[1]["team_id"]},
    )
    assert swapped.status_code == 200, swapped.text
    response = swapped.json()["data"]
    assert (
        next(item for item in response["events"] if item["id"] == event_id)["review_status"]
        == "rejected"
    )
    assert (
        next(item for item in response["events"] if item["id"] == event_id)["player_id"]
        == roster[1]["player_id"]
    )
    mapped = {item["provider_track_id"]: item for item in response["mappings"]}
    assert mapped["1"]["player_id"] == roster[1]["player_id"]
    assert mapped["1"]["review_status"] == "confirmed"
    assert mapped["2"]["player_id"] == roster[0]["player_id"]
    assert mapped["2"]["review_status"] == "estimated"
    assert set(session.scalars(select(PlayerIntensityBucket.id))) == ids_before
    for index, expected_distance in enumerate((200, 100)):
        detail = client.get(
            f"/api/v1/public/matches/{match_id}/players/{roster[index]['player_id']}/analytics"
        ).json()["data"]
        assert detail["player"]["distance_m"] == expected_distance
        assert detail["intensity_buckets"][0]["intensity"] == (80 if index == 0 else 20)
        assert detail["position_samples"][0]["x"] == (0.7 if index == 0 else 0.2)
        if index == 1:
            assert detail["events"] == []
            assert detail["analysis_quality"]["identity_mapping"] == "confirmed"
    assert session.get(PlayerAnalyticsEvent, uuid.UUID(event_id)) is not None
    assert session.get(Match, uuid.UUID(match_id)).home_score == 3
    assert len(list(session.scalars(select(AuditLog)))) == 2


def test_review_is_blocked_until_job_completes(processing_app):
    client, _, _ = processing_app
    match_id, _, owner = upload_job(client)
    response = client.patch(
        f"/api/v1/matches/{match_id}/events/{uuid.uuid4()}/review",
        headers=owner,
        json={"status": "confirmed"},
    )
    assert response.status_code == 409
    assert response.json()["errorCode"] == "MATCH_PROCESSING_ACTIVE"


def test_track_quality_and_short_calibrated_run_survive_public_read(processing_app):
    client, _, _ = processing_app
    match_id, _, _, roster = complete_analysis(
        client,
        first_metrics={
            "active_seconds": 6,
            "distance_m": 33.3,
            "avg_speed_kmh": 20,
            "max_speed_kmh": 28,
            "sprint_count": 1,
        },
        second_calibrated=False,
    )
    match = client.get(f"/api/v1/public/matches/{match_id}").json()["data"]
    assert match["analysis_quality"]["physical_metrics_available"] is True
    assert match["analysis_quality"]["calibration_coverage"] == 0.5
    assert match["analysis_quality"]["measured_seconds"] == 6
    for index, player in enumerate(roster):
        detail = client.get(
            f"/api/v1/public/matches/{match_id}/players/{player['player_id']}/analytics"
        ).json()["data"]
        assert detail["analysis_quality"]["calibrated"] is (index == 0)
        assert detail["analysis_quality"]["physical_metrics_available"] is (index == 0)
        if index == 0:
            assert detail["player"]["avg_speed_kmh"] == 20
            assert detail["player"]["distance_m"] == 33.3
            assert detail["player"]["sprint_count"] == 1
        else:
            assert detail["player"]["avg_speed_kmh"] is None
            assert detail["player"]["distance_m"] is None
    profile = client.get(f"/api/v1/public/players/{roster[0]['player_id']}").json()["data"]
    assert profile["recent_performances"][0]["avg_speed_kmh"] == 20


def test_confirmed_event_badges_and_temporary_name_review(processing_app):
    client, session, _ = processing_app
    match_id, _, owner, roster = complete_analysis(client)
    url = f"/api/v1/matches/{match_id}/analysis-review"
    review = client.get(url, headers=owner).json()["data"]
    first = review["mappings"][0]
    assert first["can_rename"] is True
    confirmed = client.patch(
        f"/api/v1/matches/{match_id}/track-mappings/{first['id']}/review",
        headers=owner,
        json={
            "player_id": first["player_id"],
            "team_id": first["team_id"],
            "display_name": "  Real   Player  ",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["mappings"][0]["display_name"] == "Real Player"
    event_id = review["events"][0]["id"]
    assert (
        client.patch(
            f"/api/v1/matches/{match_id}/events/{event_id}/review",
            headers=owner,
            json={"status": "confirmed"},
        ).status_code
        == 200
    )
    public = client.get(f"/api/v1/public/highlights?match_id={match_id}").json()["data"]["items"]
    assert (
        next(item for item in public if item["timestamp_ms"] == 1000)["review_status"]
        == "confirmed"
    )
    detail = client.get(f"/api/v1/public/matches/{match_id}").json()["data"]
    assert (
        next(item for item in detail["highlights"] if "event 0" in item["title"])["review_status"]
        == "confirmed"
    )
    session.add(
        User(
            email="protected@example.com",
            password_hash="unused",
            player_id=uuid.UUID(roster[1]["player_id"]),
        )
    )
    session.commit()
    current = client.get(url, headers=owner).json()["data"]["mappings"][1]
    assert current["can_rename"] is False
    protected = client.patch(
        f"/api/v1/matches/{match_id}/track-mappings/{current['id']}/review",
        headers=owner,
        json={
            "player_id": current["player_id"],
            "team_id": current["team_id"],
            "display_name": "Other name",
        },
    )
    assert protected.status_code == 422
    assert protected.json()["errorCode"] == "PLAYER_NAME_PROTECTED"
