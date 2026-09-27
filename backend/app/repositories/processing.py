import uuid

from sqlalchemy import func, select
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

    def list_queued_jobs(self, *, limit: int) -> list[ProcessingJob]:
        return list(
            self.session.scalars(
                select(ProcessingJob)
                .where(ProcessingJob.status == "queued")
                .order_by(ProcessingJob.created_at.asc())
                .limit(limit)
            )
        )

    def list_jobs(self, match_id: uuid.UUID) -> list[ProcessingJob]:
        return list(
            self.session.scalars(
                select(ProcessingJob)
                .where(ProcessingJob.match_id == match_id)
                .order_by(ProcessingJob.created_at.desc())
            )
        )

    def list_jobs_by_status(
        self,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[ProcessingJob]]:
        filters = []
        if status:
            filters.append(ProcessingJob.status == status)
        total = (
            self.session.scalar(select(func.count()).select_from(ProcessingJob).where(*filters))
            or 0
        )
        items = list(
            self.session.scalars(
                select(ProcessingJob)
                .where(*filters)
                .order_by(ProcessingJob.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return total, items

    def count_by_status(self, status: str) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(ProcessingJob)
                .where(ProcessingJob.status == status)
            )
            or 0
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
