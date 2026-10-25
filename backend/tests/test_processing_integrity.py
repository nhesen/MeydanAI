import math
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.analytics_bounds import intensity_from_positions, reconstruct_display_path
from app.core.config import Settings
from app.core.database import Base, get_db
from app.core.exceptions import DomainError
from app.main import create_app
from app.models.domain import JerseyAssignment, Match, ProcessingJob
from app.schemas.ingestion import (
    AnalyticsEventIngest,
    AnalyticsMetricsIngest,
    IntensityBucketIngest,
    PlayerAnalyticsIngest,
    PositionSampleIngest,
)
from app.services.analytics_ingestion import AnalyticsIngestionService

WORKER_HEADERS = {"X-Worker-Token": "integrity-test-worker"}
VIDEO = b"\x00\x00\x00\x18ftypisom" + b"stored-video-fixture"


def test_detected_roster_starts_with_recording_not_analysis_time(processing_app) -> None:
    client, session, _ = processing_app
    match_id, job_id, _ = upload_job(client)
    match = session.get(Match, uuid.UUID(match_id))
    start = datetime.now(UTC) - timedelta(days=2)
    match.starts_at = start
    session.commit()
    claim_job(client, job_id)
    response = client.post(
        f"/api/v1/internal/processing-jobs/{job_id}/detected-roster",
        headers=WORKER_HEADERS,
        json={"track_count": 1},
    )
    assert response.status_code == 200
    assignment = session.scalars(
        select(JerseyAssignment).where(JerseyAssignment.match_id == uuid.UUID(match_id))
    ).one()
    assert assignment.started_at.replace(tzinfo=UTC) == start


@pytest.fixture
def processing_app(tmp_path: Path) -> Generator[tuple[TestClient, Session, Path], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    application = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql+psycopg://test:test@localhost:5432/test",
            cors_allowed_origins="http://localhost:3000",
            auth_rate_limit_enabled=False,
            internal_worker_token=WORKER_HEADERS["X-Worker-Token"],
            video_storage_path=tmp_path,
        )
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with factory() as session:

        def override_db() -> Generator[Session, None, None]:
            yield session

        application.dependency_overrides[get_db] = override_db
        with TestClient(application) as client:
            yield client, session, tmp_path
    engine.dispose()


def upload_job(client: TestClient) -> tuple[str, str, dict[str, str]]:
    start = datetime.now(UTC) + timedelta(hours=1)
    created = client.post(
        "/api/v1/matches",
        json={
            "venue_name": "Integrity pitch",
            "starts_at": start.isoformat(),
            "expected_ends_at": (start + timedelta(hours=1)).isoformat(),
            "team_a_name": "Red",
            "team_b_name": "Blue",
        },
    )
    assert created.status_code == 201
    match = created.json()["data"]
    match_id = match["match"]["id"]
    organizer = {"X-Organizer-Token": match["organizer_token"]}
    uploaded = client.post(
        f"/api/v1/matches/{match_id}/processing-jobs",
        headers=organizer,
        files={"video": ("match.mp4", VIDEO, "video/mp4")},
    )
    assert uploaded.status_code == 202, uploaded.text
    return match_id, uploaded.json()["data"]["id"], organizer


def claim_job(client: TestClient, job_id: str) -> None:
    claimed = client.patch(
        f"/api/v1/internal/processing-jobs/{job_id}",
        headers=WORKER_HEADERS,
        json={
            "status": "processing",
            "expected_status": "queued",
            "stage": "validating",
            "progress": 8,
            "provider_run_id": "first-worker",
        },
    )
    assert claimed.status_code == 200, claimed.text


def test_upload_guard_and_worker_claim_preserve_the_first_job(processing_app) -> None:
    client, session, storage = processing_app
    match_id, job_id, organizer = upload_job(client)
    assert len(list(storage.glob("*.mp4"))) == 1
    duplicate = client.post(
        f"/api/v1/matches/{match_id}/processing-jobs",
        headers=organizer,
        files={"video": ("second.mp4", VIDEO, "video/mp4")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["errorCode"] == "MATCH_PROCESSING_ACTIVE"
    assert len(list(storage.glob("*.mp4"))) == 1
    assert len(list(session.scalars(select(ProcessingJob)))) == 1

    claim_job(client, job_id)
    lost_claim = client.patch(
        f"/api/v1/internal/processing-jobs/{job_id}",
        headers=WORKER_HEADERS,
        json={
            "status": "processing",
            "expected_status": "queued",
            "stage": "validating",
            "progress": 8,
            "provider_run_id": "second-worker",
        },
    )
    assert lost_claim.status_code == 409
    assert lost_claim.json()["errorCode"] == "JOB_STATE_CONFLICT"
    job = session.get(ProcessingJob, uuid.UUID(job_id))
    assert job is not None
    assert job.provider_run_id == "first-worker"


def test_retry_cannot_queue_two_analyses_for_one_match(processing_app) -> None:
    client, _, _ = processing_app
    _, job_id, organizer = upload_job(client)
    claim_job(client, job_id)
    failed = client.patch(
        f"/api/v1/internal/processing-jobs/{job_id}",
        headers=WORKER_HEADERS,
        json={
            "status": "failed",
            "stage": "validating",
            "error_code": "INVALID_VIDEO",
        },
    )
    assert failed.status_code == 200
    first = client.post(f"/api/v1/processing-jobs/{job_id}/retry", headers=organizer)
    second = client.post(f"/api/v1/processing-jobs/{job_id}/retry", headers=organizer)
    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["errorCode"] == "MATCH_PROCESSING_ACTIVE"


def test_ingestion_retries_are_stable_and_public_results_preserve_observations(
    processing_app,
) -> None:
    client, session, _ = processing_app
    match_id, job_id, _ = upload_job(client)
    claim_job(client, job_id)
    roster = client.post(
        f"/api/v1/internal/processing-jobs/{job_id}/detected-roster",
        headers=WORKER_HEADERS,
        json={"track_count": 1},
    ).json()["data"]["assignments"]
    player = roster[0]
    payload = PlayerAnalyticsIngest(
        player_id=player["player_id"],
        team_id=player["team_id"],
        metrics=AnalyticsMetricsIngest(max_speed_kmh=72, active_seconds=5),
        positions=[
            PositionSampleIngest(timestamp_ms=0, x=0.5, y=0.5),
            PositionSampleIngest(timestamp_ms=1000, x=0.5, y=0.5),
        ],
        intensity=[IntensityBucketIngest(from_minute=0, to_minute=1, intensity=80)],
        complete_job=True,
    )
    original = payload.model_dump()
    service = AnalyticsIngestionService(session, max_position_samples=100)
    first = service.ingest(uuid.UUID(job_id), "stationary-retry", payload)
    repeated = service.ingest(uuid.UUID(job_id), "stationary-retry", payload)
    assert payload.model_dump() == original
    assert first.duplicate is False
    assert repeated.duplicate is True
    assert first.batch_id == repeated.batch_id
    detail = client.get(
        f"/api/v1/public/matches/{match_id}/players/{player['player_id']}/analytics"
    ).json()["data"]
    assert detail["position_samples"] == [
        {"timestamp_ms": 0, "x": 0.5, "y": 0.5},
        {"timestamp_ms": 1000, "x": 0.5, "y": 0.5},
    ]
    assert detail["intensity_buckets"] == [{"from_minute": 0, "to_minute": 1, "intensity": 40.0}]

    oversized = payload.model_copy(deep=True)
    oversized.positions *= 51
    with pytest.raises(DomainError) as error:
        service.ingest(uuid.UUID(job_id), "oversized-duplicate-positions", oversized)
    assert error.value.error_code == "ANALYTICS_BATCH_TOO_LARGE"


def test_observed_path_keeps_stationary_samples_and_the_whole_video() -> None:
    samples = [
        PositionSampleIngest(timestamp_ms=index * 1000, x=0.5, y=0.5) for index in range(1001)
    ]
    cleaned = reconstruct_display_path(list(reversed(samples)))
    assert cleaned == samples
    assert reconstruct_display_path(cleaned) == samples
    assert intensity_from_positions(samples[:2]) == [(0, 1, 0.0)]
    teleport = [samples[0], PositionSampleIngest(timestamp_ms=1, x=0.9, y=0.9)]
    assert intensity_from_positions(teleport) == []
    assert intensity_from_positions([samples[0], samples[100]]) == []


def test_highlight_clip_ingestion_and_range_playback(processing_app) -> None:
    client, _, storage = processing_app
    match_id, job_id, _ = upload_job(client)
    claim_job(client, job_id)
    roster = client.post(
        f"/api/v1/internal/processing-jobs/{job_id}/detected-roster",
        headers=WORKER_HEADERS,
        json={"track_count": 1},
    ).json()["data"]["assignments"]
    player = roster[0]
    clip_name = f"{uuid.uuid4().hex}-goal-1200.mp4"
    clip_url = f"/api/v1/public/media/highlights/{clip_name}"
    highlights = storage / "highlights"
    highlights.mkdir()
    (highlights / clip_name).write_bytes(VIDEO)
    payload = {
        "player_id": player["player_id"],
        "team_id": player["team_id"],
        "metrics": {},
        "events": [
            {
                "event_type": "goal",
                "timestamp_ms": 1200,
                "title": "Possible goal",
                "video_url": clip_url,
                "duration_ms": 4200,
            }
        ],
    }
    ingested = client.post(
        f"/api/v1/internal/processing-jobs/{job_id}/analytics",
        headers={**WORKER_HEADERS, "Idempotency-Key": "goal-clip-ingestion"},
        json=payload,
    )
    assert ingested.status_code == 200, ingested.text
    result = client.get(f"/api/v1/public/highlights?match_id={match_id}").json()["data"]
    assert len(result["items"]) == 1
    assert result["items"][0]["video_url"] == clip_url
    assert result["items"][0]["duration_ms"] == 4200
    played = client.get(clip_url, headers={"Range": "bytes=0-11"})
    assert played.status_code == 206
    assert played.content == VIDEO[:12]
    assert played.headers["content-type"] == "video/mp4"
    assert played.headers["content-disposition"].startswith("inline;")


@pytest.mark.parametrize(
    "video_url",
    [
        "https://untrusted.example/clip.mp4",
        "javascript:alert(1)",
        "/api/v1/public/media/highlights/../video.mp4",
        "/api/v1/public/media/highlights/clip.mp4?source=other",
    ],
)
def test_highlight_ingestion_rejects_unsafe_media_references(video_url: str) -> None:
    with pytest.raises(ValidationError):
        AnalyticsEventIngest(
            event_type="goal", timestamp_ms=0, title="Possible goal", video_url=video_url
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_analytics_rejects_nonfinite_measurements(value: float) -> None:
    with pytest.raises(ValidationError):
        PositionSampleIngest(timestamp_ms=0, x=value, y=0.5)
    with pytest.raises(ValidationError):
        AnalyticsMetricsIngest(distance_m=value)
    with pytest.raises(ValidationError):
        AnalyticsEventIngest(event_type="shot", timestamp_ms=0, speed_kmh=value, title="Shot")
