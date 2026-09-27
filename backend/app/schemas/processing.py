import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.processing import ProcessingSourceType, ProcessingStage, ProcessingStatus


class ProcessingJobResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    retry_of_id: uuid.UUID | None
    status: ProcessingStatus
    progress: int | None
    stage: ProcessingStage
    source_type: ProcessingSourceType
    provider: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_message: str | None


class ProcessingJobStateUpdate(BaseModel):
    status: ProcessingStatus
    stage: ProcessingStage
    progress: int | None = Field(default=None, ge=0, le=100)
    provider_run_id: str | None = Field(default=None, min_length=1, max_length=200)
    error_code: str | None = Field(default=None, min_length=1, max_length=80)
    error_message: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_state_details(self) -> "ProcessingJobStateUpdate":
        if self.status == ProcessingStatus.COMPLETED and (
            self.stage != ProcessingStage.COMPLETED or self.progress != 100
        ):
            raise ValueError("Completed jobs require completed stage and 100 progress")
        if self.status == ProcessingStatus.FAILED and self.error_code is None:
            raise ValueError("Failed jobs require an error_code")
        if self.status != ProcessingStatus.FAILED and (
            self.error_code is not None or self.error_message is not None
        ):
            raise ValueError("Error details are only valid for failed jobs")
        return self
