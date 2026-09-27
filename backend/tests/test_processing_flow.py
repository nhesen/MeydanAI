import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import internal_processing
from app.core.database import Base
from app.core.exceptions import DomainError
from app.core.processing import ProcessingStage, ProcessingStatus
from app.schemas.ingestion import (
    AnalyticsMetricsIngest,
    PlayerAnalyticsIngest,
    PositionSampleIngest,
    TrackMappingIngest,
)
from app.schemas.matches import AssignmentCreate, MatchCreate
from app.schemas.processing import ProcessingJobStateUpdate
from app.services.analytics_ingestion import AnalyticsIngestionService
from app.services.analytics_provider import ProviderJobStatus
from app.services.matches import MatchService
from app.services.processing import ProcessingService
from app.services.video_storage import LocalVideoStorage


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database_session:
        yield database_session
    Base.metadata.drop_all(engine)


def create_match(session: Session, suffix: str = ""):
    start = datetime.now(UTC) + timedelta(hours=1)
    return MatchService(session).create_match(
        MatchCreate(
            venue_name=f"Processing venue {suffix}".strip(),
            starts_at=start,
            expected_ends_at=start + timedelta(hours=1),
            team_a_name=f"Home {suffix}".strip(),
            team_b_name=f"Away {suffix}".strip(),
        )
    )


def create_job(session: Session):
    match = create_match(session)
    job = ProcessingService(session).create_job(
        match_id=match.match.id,
        organizer_token=match.organizer_token,
        source_reference="video/test.mp4",
        source_media_type="video/mp4",
        source_size_bytes=1024,
        provider="external",
    )
    return match, job


def test_processing_job_creation(session: Session) -> None:
    match, job = create_job(session)

    assert job.match_id == match.match.id
    assert job.status == ProcessingStatus.QUEUED
    assert job.stage == ProcessingStage.QUEUED
    assert job.progress == 0


def test_processing_job_rejects_invalid_match_and_unauthorized_access(
    session: Session,
) -> None:
    service = ProcessingService(session)
    with pytest.raises(DomainError) as missing:
        service.create_job(
            match_id=uuid.uuid4(),
            organizer_token="invalid",
            source_reference="video/test.mp4",
            source_media_type="video/mp4",
            source_size_bytes=1024,
            provider="external",
        )
    assert missing.value.error_code == "MATCH_NOT_FOUND"

    match = create_match(session)
    with pytest.raises(DomainError) as unauthorized:
        service.create_job(
            match_id=match.match.id,
            organizer_token="invalid",
            source_reference="video/test.mp4",
            source_media_type="video/mp4",
            source_size_bytes=1024,
            provider="external",
        )
    assert unauthorized.value.error_code == "ORGANIZER_ACCESS_DENIED"


def test_processing_job_valid_and_invalid_transitions(session: Session) -> None:
    _, job = create_job(session)
    service = ProcessingService(session)
    processing = service.update_state(
        job.id,
        ProcessingJobStateUpdate(
            status=ProcessingStatus.PROCESSING,
            stage=ProcessingStage.VALIDATING,
            progress=10,
        ),
    )
    assert processing.started_at is not None

    completed = service.update_state(
        job.id,
        ProcessingJobStateUpdate(
            status=ProcessingStatus.COMPLETED,
            stage=ProcessingStage.COMPLETED,
            progress=100,
        ),
    )
    assert completed.completed_at is not None

    with pytest.raises(DomainError) as raised:
        service.update_state(
            job.id,
            ProcessingJobStateUpdate(
                status=ProcessingStatus.PROCESSING,
                stage=ProcessingStage.VALIDATING,
                progress=10,
            ),
        )
    assert raised.value.error_code == "INVALID_JOB_TRANSITION"


def test_failed_job_retry_and_completed_retry_rejection(session: Session) -> None:
    match, failed_job = create_job(session)
    service = ProcessingService(session)
    service.update_state(
        failed_job.id,
        ProcessingJobStateUpdate(
            status=ProcessingStatus.PROCESSING,
            stage=ProcessingStage.PREPROCESSING,
            progress=20,
        ),
    )
    service.update_state(
        failed_job.id,
        ProcessingJobStateUpdate(
            status=ProcessingStatus.FAILED,
            stage=ProcessingStage.PREPROCESSING,
            progress=20,
            error_code="PROCESSING_FAILED",
            error_message="Internal provider stack trace",
        ),
    )
    retry = service.retry_job(failed_job.id, match.organizer_token)
    assert retry.retry_of_id == failed_job.id
    assert retry.status == ProcessingStatus.QUEUED

    completed_match, completed_job = create_job(session)
    service.update_state(
        completed_job.id,
        ProcessingJobStateUpdate(
            status=ProcessingStatus.PROCESSING,
            stage=ProcessingStage.PERSISTING_RESULTS,
            progress=95,
        ),
    )
    service.update_state(
        completed_job.id,
        ProcessingJobStateUpdate(
            status=ProcessingStatus.COMPLETED,
            stage=ProcessingStage.COMPLETED,
            progress=100,
        ),
    )
    with pytest.raises(DomainError) as raised:
        service.retry_job(completed_job.id, completed_match.organizer_token)
    assert raised.value.error_code == "JOB_NOT_RETRYABLE"


def test_processing_progress_validation() -> None:
    with pytest.raises(ValidationError):
        ProcessingJobStateUpdate(
            status=ProcessingStatus.PROCESSING,
            stage=ProcessingStage.TRACKING_PLAYERS,
            progress=101,
        )


def test_local_video_storage_validates_and_sanitizes_upload(
    tmp_path,
) -> None:
    storage = LocalVideoStorage(tmp_path)
    content = b"\x00\x00\x00\x18ftypisom" + b"video-data"

    stored = storage.store(
        BytesIO(content),
        original_filename="../../unsafe.mp4",
        media_type="video/mp4",
        max_size_bytes=1024,
    )

    assert stored.reference.endswith(".mp4")
    assert "/" not in stored.reference
    assert "\\" not in stored.reference
    assert (tmp_path / stored.reference).read_bytes() == content


@pytest.mark.parametrize(
    ("content", "filename", "media_type", "max_size"),
    [
        (b"", "empty.mp4", "video/mp4", 1024),
        (b"not-a-video", "invalid.mp4", "video/mp4", 1024),
        (b"\x1a\x45\xdf\xa3payload", "video.mp4", "video/webm", 1024),
        (b"\x00\x00\x00\x18ftypisom", "large.mp4", "video/mp4", 4),
    ],
)
def test_local_video_storage_rejects_invalid_uploads(
    tmp_path,
    content: bytes,
    filename: str,
    media_type: str,
    max_size: int,
) -> None:
    storage = LocalVideoStorage(tmp_path)

    with pytest.raises(DomainError) as raised:
        storage.store(
            BytesIO(content),
            original_filename=filename,
            media_type=media_type,
            max_size_bytes=max_size,
        )

    assert raised.value.error_code in {"INVALID_VIDEO", "VIDEO_TOO_LARGE"}
    assert list(tmp_path.iterdir()) == []


class RecordingProcessor:
    def __init__(self) -> None:
        self.enqueued: list[uuid.UUID] = []

    def enqueue(self, job_id: uuid.UUID, source_reference: str) -> None:
        self.enqueued.append(job_id)

    def get_status(self, job_id: uuid.UUID) -> ProviderJobStatus | None:
        return None

    def cancel(self, job_id: uuid.UUID) -> bool:
        return False


def test_processing_provider_boundary_is_invoked(session: Session) -> None:
    match = create_match(session)
    processor = RecordingProcessor()
    job = ProcessingService(session, processor=processor).create_job(
        match_id=match.match.id,
        organizer_token=match.organizer_token,
        source_reference="video/test.mp4",
        source_media_type="video/mp4",
        source_size_bytes=1024,
        provider="external",
    )

    assert processor.enqueued == [job.id]


def create_processing_player(session: Session):
    service = MatchService(session)
    match = create_match(session)
    assignment = service.join_match(
        match.join_token,
        AssignmentCreate(
            team_id=match.match.teams[0].id,
            display_name="Tracked Player",
            jersey_number=7,
        ),
    )
    job = ProcessingService(session).create_job(
        match_id=match.match.id,
        organizer_token=match.organizer_token,
        source_reference="video/analytics.mp4",
        source_media_type="video/mp4",
        source_size_bytes=2048,
        provider="external",
    )
    ProcessingService(session).update_state(
        job.id,
        ProcessingJobStateUpdate(
            status=ProcessingStatus.PROCESSING,
            stage=ProcessingStage.CALCULATING_METRICS,
            progress=80,
        ),
    )
    return match, assignment, job


def analytics_payload(player_id: uuid.UUID, team_id: uuid.UUID, distance: float = 1000):
    return PlayerAnalyticsIngest(
        player_id=player_id,
        team_id=team_id,
        provider_track_id="track-17",
        metrics=AnalyticsMetricsIngest(
            distance_m=distance,
            avg_speed_kmh=10.5,
            max_speed_kmh=24.2,
            sprint_count=3,
            active_seconds=600,
            activity_count=20,
        ),
        positions=[
            PositionSampleIngest(timestamp_ms=1000, x=0.25, y=0.75),
        ],
        track_mappings=[
            TrackMappingIngest(
                provider_track_id="track-unknown",
                mapping_status="unresolved",
            )
        ],
    )


def test_analytics_ingestion_is_transactional_and_idempotent(
    session: Session,
) -> None:
    match, assignment, job = create_processing_player(session)
    payload = analytics_payload(assignment.player.id, assignment.team.id)
    service = AnalyticsIngestionService(session, max_position_samples=100)

    first = service.ingest(job.id, "player-17-batch-1", payload)
    duplicate = service.ingest(job.id, "player-17-batch-1", payload)
    detail = MatchService(session).get_player_analytics_detail(
        match.match.id,
        assignment.player.id,
    )

    assert first.duplicate is False
    assert duplicate.duplicate is True
    assert duplicate.batch_id == first.batch_id
    assert detail.player.distance_m == 1000
    assert len(detail.position_samples) == 1

    with pytest.raises(DomainError) as reused:
        service.ingest(
            job.id,
            "player-17-batch-1",
            analytics_payload(assignment.player.id, assignment.team.id, 2000),
        )
    assert reused.value.error_code == "IDEMPOTENCY_KEY_REUSED"


def test_analytics_ingestion_rejects_invalid_mapping_and_coordinates(
    session: Session,
) -> None:
    _, assignment, job = create_processing_player(session)
    other_match = create_match(session, "other")
    outsider = MatchService(session).join_match(
        other_match.join_token,
        AssignmentCreate(
            team_id=other_match.match.teams[0].id,
            display_name="Outsider",
            jersey_number=9,
        ),
    )
    service = AnalyticsIngestionService(session, max_position_samples=100)

    with pytest.raises(DomainError) as mapping_error:
        service.ingest(
            job.id,
            "outsider-batch",
            analytics_payload(outsider.player.id, outsider.team.id),
        )
    assert mapping_error.value.error_code == "PLAYER_MAPPING_FAILED"

    with pytest.raises(ValidationError):
        PositionSampleIngest(timestamp_ms=1000, x=1.2, y=0.5)

    valid_payload = analytics_payload(assignment.player.id, assignment.team.id)
    valid_payload.positions = [
        PositionSampleIngest(timestamp_ms=index, x=0.5, y=0.5) for index in range(2)
    ]
    limited_service = AnalyticsIngestionService(session, max_position_samples=1)
    with pytest.raises(DomainError) as batch_error:
        limited_service.ingest(job.id, "oversized-batch", valid_payload)
    assert batch_error.value.error_code == "ANALYTICS_BATCH_TOO_LARGE"


def test_analytics_ingestion_rolls_back_replacement_on_persistence_failure(
    session: Session,
    monkeypatch,
) -> None:
    match, assignment, job = create_processing_player(session)
    service = AnalyticsIngestionService(session, max_position_samples=100)
    service.ingest(
        job.id,
        "initial-batch",
        analytics_payload(assignment.player.id, assignment.team.id, 1000),
    )
    original_commit = session.commit

    def fail_commit() -> None:
        raise SQLAlchemyError("forced persistence failure")

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(DomainError) as raised:
        service.ingest(
            job.id,
            "replacement-batch",
            analytics_payload(assignment.player.id, assignment.team.id, 2000),
        )
    assert raised.value.error_code == "PERSISTENCE_FAILED"

    monkeypatch.setattr(session, "commit", original_commit)
    detail = MatchService(session).get_player_analytics_detail(
        match.match.id,
        assignment.player.id,
    )
    assert detail.player.distance_m == 1000


def test_internal_worker_auth_is_disabled_without_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        internal_processing,
        "get_settings",
        lambda: SimpleNamespace(internal_worker_token=None),
    )
    with pytest.raises(DomainError) as disabled:
        internal_processing.require_internal_worker()
    assert disabled.value.error_code == "WORKER_AUTH_NOT_CONFIGURED"

    monkeypatch.setattr(
        internal_processing,
        "get_settings",
        lambda: SimpleNamespace(internal_worker_token="worker-secret"),
    )
    with pytest.raises(DomainError) as denied:
        internal_processing.require_internal_worker("wrong-secret")
    assert denied.value.error_code == "WORKER_ACCESS_DENIED"
    internal_processing.require_internal_worker("worker-secret")


def test_final_ingestion_completes_job_and_blocks_new_batches(
    session: Session,
) -> None:
    _, assignment, job = create_processing_player(session)
    payload = analytics_payload(assignment.player.id, assignment.team.id)
    payload.complete_job = True
    service = AnalyticsIngestionService(session, max_position_samples=100)

    completed = service.ingest(job.id, "final-player-batch", payload)

    assert completed.job_status == ProcessingStatus.COMPLETED
    with pytest.raises(DomainError) as raised:
        service.ingest(
            job.id,
            "late-player-batch",
            analytics_payload(assignment.player.id, assignment.team.id),
        )
    assert raised.value.error_code == "JOB_NOT_ACCEPTING_ANALYTICS"
