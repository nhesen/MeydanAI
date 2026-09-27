import logging
import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.core.processing import (
    ProcessingSourceType,
    ProcessingStage,
    ProcessingStatus,
    can_transition,
)
from app.models.domain import ProcessingJob
from app.repositories.processing import ProcessingRepository
from app.schemas.processing import ProcessingJobResponse, ProcessingJobStateUpdate
from app.services.analytics_provider import AnalyticsProcessor, get_analytics_processor
from app.services.matches import MatchService

logger = logging.getLogger(__name__)

SAFE_PROCESSING_ERRORS = {
    "INVALID_VIDEO": "The uploaded video could not be validated.",
    "UPLOAD_FAILED": "The video could not be stored.",
    "PROCESSING_FAILED": "Video processing could not be completed.",
    "INVALID_ANALYTICS_PAYLOAD": "The processing result was invalid.",
    "PLAYER_MAPPING_FAILED": "Some detected players could not be mapped.",
    "PERSISTENCE_FAILED": "The analytics result could not be saved.",
}

PROCESSING_STAGE_ORDER = {
    stage: index
    for index, stage in enumerate(
        [
            ProcessingStage.QUEUED,
            ProcessingStage.UPLOADING,
            ProcessingStage.VALIDATING,
            ProcessingStage.PREPROCESSING,
            ProcessingStage.DETECTING_PLAYERS,
            ProcessingStage.TRACKING_PLAYERS,
            ProcessingStage.CALIBRATING_FIELD,
            ProcessingStage.CALCULATING_METRICS,
            ProcessingStage.PERSISTING_RESULTS,
            ProcessingStage.COMPLETED,
        ]
    )
}


class ProcessingService:
    def __init__(
        self,
        session: Session,
        processor: AnalyticsProcessor | None = None,
    ) -> None:
        self.session = session
        self.repository = ProcessingRepository(session)
        self.processor = processor

    def create_job(
        self,
        *,
        match_id: uuid.UUID,
        organizer_token: str,
        source_reference: str,
        source_media_type: str,
        source_size_bytes: int,
        provider: str,
    ) -> ProcessingJobResponse:
        MatchService(self.session).get_organizer_match(match_id, organizer_token)
        job = ProcessingJob(
            match_id=match_id,
            status=ProcessingStatus.QUEUED.value,
            stage=ProcessingStage.QUEUED.value,
            progress=0,
            source_type=ProcessingSourceType.UPLOADED_VIDEO.value,
            source_reference=source_reference,
            source_media_type=source_media_type,
            source_size_bytes=source_size_bytes,
            provider=provider,
        )
        self.repository.add(job)
        self.session.commit()
        stored = self._require_job(job.id)
        processor = self.processor or get_analytics_processor(provider)
        processor.enqueue(stored.id, stored.source_reference)
        self._log_lifecycle(stored, "processing_job_created")
        return self.to_response(stored)

    def list_jobs(
        self,
        match_id: uuid.UUID,
        organizer_token: str,
    ) -> list[ProcessingJobResponse]:
        MatchService(self.session).get_organizer_match(match_id, organizer_token)
        return [self.to_response(job) for job in self.repository.list_jobs(match_id)]

    def get_job(
        self,
        job_id: uuid.UUID,
        organizer_token: str,
    ) -> ProcessingJobResponse:
        job = self._require_job(job_id)
        MatchService(self.session).get_organizer_match(job.match_id, organizer_token)
        return self.to_response(job)

    def update_state(
        self,
        job_id: uuid.UUID,
        payload: ProcessingJobStateUpdate,
    ) -> ProcessingJobResponse:
        job = self._require_job(job_id, for_update=True)
        current_status = ProcessingStatus(job.status)
        if payload.status != current_status and not can_transition(current_status, payload.status):
            raise self._conflict(
                f"Cannot transition processing job from {current_status.value} "
                f"to {payload.status.value}.",
                "INVALID_JOB_TRANSITION",
            )
        if (
            payload.status == current_status == ProcessingStatus.PROCESSING
            and PROCESSING_STAGE_ORDER[payload.stage]
            < PROCESSING_STAGE_ORDER[ProcessingStage(job.stage)]
        ):
            raise self._conflict(
                "Processing stage cannot move backwards.",
                "INVALID_JOB_STAGE",
            )
        if (
            payload.progress is not None
            and job.progress is not None
            and payload.status != ProcessingStatus.FAILED
            and payload.progress < job.progress
        ):
            raise self._conflict(
                "Processing progress cannot decrease.",
                "INVALID_JOB_PROGRESS",
            )

        now = datetime.now(UTC)
        job.status = payload.status.value
        job.stage = payload.stage.value
        job.progress = payload.progress
        if payload.provider_run_id is not None:
            job.provider_run_id = payload.provider_run_id
        if payload.status == ProcessingStatus.PROCESSING and job.started_at is None:
            job.started_at = now
        if payload.status == ProcessingStatus.COMPLETED:
            job.completed_at = now
        if payload.status == ProcessingStatus.FAILED:
            job.failed_at = now
            job.error_code = payload.error_code
            job.error_message = payload.error_message
        self.session.commit()
        stored = self._require_job(job.id)
        self._log_lifecycle(stored, "processing_job_state_changed")
        return self.to_response(stored)

    def retry_job(
        self,
        job_id: uuid.UUID,
        organizer_token: str,
    ) -> ProcessingJobResponse:
        failed_job = self._require_job(job_id, for_update=True)
        MatchService(self.session).get_organizer_match(
            failed_job.match_id,
            organizer_token,
        )
        if ProcessingStatus(failed_job.status) != ProcessingStatus.FAILED:
            raise self._conflict(
                "Only failed processing jobs can be retried.",
                "JOB_NOT_RETRYABLE",
            )
        retry = ProcessingJob(
            match_id=failed_job.match_id,
            retry_of_id=failed_job.id,
            status=ProcessingStatus.QUEUED.value,
            stage=ProcessingStage.QUEUED.value,
            progress=0,
            source_type=failed_job.source_type,
            source_reference=failed_job.source_reference,
            source_media_type=failed_job.source_media_type,
            source_size_bytes=failed_job.source_size_bytes,
            provider=failed_job.provider,
        )
        self.repository.add(retry)
        self.session.commit()
        stored = self._require_job(retry.id)
        self._log_lifecycle(stored, "processing_job_retried")
        return self.to_response(stored)

    def _require_job(
        self,
        job_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> ProcessingJob:
        job = self.repository.get_job(job_id, for_update=for_update)
        if job is None:
            raise DomainError(
                status=404,
                title="Resource not found",
                detail="Processing job was not found.",
                error_code="PROCESSING_JOB_NOT_FOUND",
            )
        return job

    @staticmethod
    def to_response(job: ProcessingJob) -> ProcessingJobResponse:
        return ProcessingJobResponse(
            id=job.id,
            match_id=job.match_id,
            retry_of_id=job.retry_of_id,
            status=cast(ProcessingStatus, job.status),
            progress=job.progress,
            stage=cast(ProcessingStage, job.stage),
            source_type=cast(ProcessingSourceType, job.source_type),
            provider=job.provider,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            failed_at=job.failed_at,
            error_code=job.error_code,
            error_message=(
                SAFE_PROCESSING_ERRORS.get(
                    job.error_code,
                    "Video processing could not be completed.",
                )
                if job.error_code
                else None
            ),
        )

    @staticmethod
    def _log_lifecycle(job: ProcessingJob, event: str) -> None:
        logger.info(
            event,
            extra={
                "job_id": str(job.id),
                "match_id": str(job.match_id),
                "stage": job.stage,
                "status": job.status,
            },
        )

    @staticmethod
    def _conflict(detail: str, code: str) -> DomainError:
        return DomainError(
            status=409,
            title="Invalid processing state",
            detail=detail,
            error_code=code,
        )
