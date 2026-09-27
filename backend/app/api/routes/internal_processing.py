import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import DomainError
from app.schemas.common import ApiResponse
from app.schemas.ingestion import AnalyticsIngestionResponse, PlayerAnalyticsIngest
from app.schemas.processing import ProcessingJobResponse, ProcessingJobStateUpdate
from app.services.analytics_ingestion import AnalyticsIngestionService
from app.services.processing import ProcessingService

router = APIRouter(
    prefix="/internal/processing-jobs",
    tags=["internal-processing"],
)
DatabaseSession = Annotated[Session, Depends(get_db)]
WorkerToken = Annotated[str | None, Header(alias="X-Worker-Token")]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=120),
]


def require_internal_worker(worker_token: WorkerToken = None) -> None:
    configured_token = get_settings().internal_worker_token
    if configured_token is None:
        raise DomainError(
            status=503,
            title="Worker ingestion unavailable",
            detail="Internal worker authentication is not configured.",
            error_code="WORKER_AUTH_NOT_CONFIGURED",
        )
    if worker_token is None or not secrets.compare_digest(
        configured_token,
        worker_token,
    ):
        raise DomainError(
            status=403,
            title="Worker access denied",
            detail="A valid internal worker token is required.",
            error_code="WORKER_ACCESS_DENIED",
        )


@router.patch(
    "/{job_id}",
    response_model=ApiResponse[ProcessingJobResponse],
    dependencies=[Depends(require_internal_worker)],
)
def update_processing_job_state(
    job_id: uuid.UUID,
    payload: ProcessingJobStateUpdate,
    session: DatabaseSession,
) -> ApiResponse[ProcessingJobResponse]:
    return ApiResponse(data=ProcessingService(session).update_state(job_id, payload))


@router.post(
    "/{job_id}/analytics",
    response_model=ApiResponse[AnalyticsIngestionResponse],
    dependencies=[Depends(require_internal_worker)],
)
def ingest_player_analytics(
    job_id: uuid.UUID,
    payload: PlayerAnalyticsIngest,
    session: DatabaseSession,
    idempotency_key: IdempotencyKey,
) -> ApiResponse[AnalyticsIngestionResponse]:
    settings = get_settings()
    return ApiResponse(
        data=AnalyticsIngestionService(
            session,
            max_position_samples=settings.max_position_samples_per_ingestion,
        ).ingest(job_id, idempotency_key, payload)
    )
