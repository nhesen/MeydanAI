import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    ProcessingIngestionBatch,
    ProcessingJob,
    ProcessingTrackMapping,
)


class ProcessingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_job(
        self,
        job_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> ProcessingJob | None:
        query = select(ProcessingJob).where(ProcessingJob.id == job_id)
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_jobs(self, match_id: uuid.UUID) -> list[ProcessingJob]:
        return list(
            self.session.scalars(
                select(ProcessingJob)
                .where(ProcessingJob.match_id == match_id)
                .order_by(ProcessingJob.created_at.desc())
            )
        )

    def get_ingestion_batch(
        self,
        job_id: uuid.UUID,
        idempotency_key: str,
    ) -> ProcessingIngestionBatch | None:
        return self.session.scalar(
            select(ProcessingIngestionBatch).where(
                ProcessingIngestionBatch.job_id == job_id,
                ProcessingIngestionBatch.idempotency_key == idempotency_key,
            )
        )

    def get_track_mapping(
        self,
        job_id: uuid.UUID,
        provider_track_id: str,
    ) -> ProcessingTrackMapping | None:
        return self.session.scalar(
            select(ProcessingTrackMapping).where(
                ProcessingTrackMapping.job_id == job_id,
                ProcessingTrackMapping.provider_track_id == provider_track_id,
            )
        )

    def add(self, entity: object) -> None:
        self.session.add(entity)

    def flush(self) -> None:
        self.session.flush()
