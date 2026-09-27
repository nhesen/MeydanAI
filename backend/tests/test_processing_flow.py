import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.exceptions import DomainError
from app.core.processing import ProcessingStage, ProcessingStatus
from app.schemas.matches import MatchCreate
from app.schemas.processing import ProcessingJobStateUpdate
from app.services.matches import MatchService
from app.services.processing import ProcessingService


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
