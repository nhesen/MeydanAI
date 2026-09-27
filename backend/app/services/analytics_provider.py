import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from app.core.processing import ProcessingStage, ProcessingStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderJobStatus:
    status: ProcessingStatus
    stage: ProcessingStage
    progress: int | None
    provider_run_id: str | None = None


class AnalyticsProcessor(Protocol):
    def enqueue(self, job_id: uuid.UUID, source_reference: str) -> None: ...

    def get_status(self, job_id: uuid.UUID) -> ProviderJobStatus | None: ...

    def cancel(self, job_id: uuid.UUID) -> bool: ...


class ExternalWorkerAnalyticsProcessor:
    """Queue boundary for a separately deployed worker.

    This provider intentionally creates no analytics. An authenticated worker
    must claim jobs, report state, and ingest validated results through the
    internal API.
    """

    def enqueue(self, job_id: uuid.UUID, source_reference: str) -> None:
        logger.info(
            "processing_job_available_for_external_worker",
            extra={"job_id": str(job_id)},
        )

    def get_status(self, job_id: uuid.UUID) -> ProviderJobStatus | None:
        return None

    def cancel(self, job_id: uuid.UUID) -> bool:
        return False


def get_analytics_processor(provider: str) -> AnalyticsProcessor:
    if provider == "external":
        return ExternalWorkerAnalyticsProcessor()
    raise ValueError(f"Unsupported analytics provider: {provider}")
