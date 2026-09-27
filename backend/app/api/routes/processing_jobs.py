import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import OrganizerTokenHeader, get_optional_user
from app.models.domain import User
from app.schemas.common import ApiResponse
from app.schemas.processing import ProcessingJobResponse
from app.services.processing import ProcessingService

router = APIRouter(prefix="/processing-jobs", tags=["processing-jobs"])
DatabaseSession = Annotated[Session, Depends(get_db)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


@router.get("/{job_id}", response_model=ApiResponse[ProcessingJobResponse])
def get_processing_job(
    job_id: uuid.UUID,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[ProcessingJobResponse]:
    return ApiResponse(data=ProcessingService(session).get_job(job_id, organizer_token, user))


@router.post(
    "/{job_id}/retry",
    response_model=ApiResponse[ProcessingJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_processing_job(
    job_id: uuid.UUID,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[ProcessingJobResponse]:
    return ApiResponse(data=ProcessingService(session).retry_job(job_id, organizer_token, user))
