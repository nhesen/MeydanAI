import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import OrganizerTokenHeader, get_optional_user
from app.models.domain import User
from app.schemas.common import ApiResponse
from app.schemas.matches import (
    AssignmentCorrection,
    AssignmentResponse,
    JerseyChange,
    JoinTokenCreate,
    JoinTokenResponse,
    MatchCreate,
    MatchCreatedResponse,
    MatchResponse,
    MatchStateUpdate,
)
from app.schemas.processing import ProcessingJobResponse
from app.services.matches import MatchService
from app.services.processing import ProcessingService
from app.services.video_storage import LocalVideoStorage

router = APIRouter(prefix="/matches", tags=["matches"])
DatabaseSession = Annotated[Session, Depends(get_db)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
VideoUpload = Annotated[UploadFile, File()]


@router.post(
    "",
    response_model=ApiResponse[MatchCreatedResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_match(
    payload: MatchCreate,
    session: DatabaseSession,
    user: OptionalUser,
) -> ApiResponse[MatchCreatedResponse]:
    return ApiResponse(
        data=MatchService(session).create_match(
            payload,
            organizer_user_id=user.id if user is not None else None,
        )
    )


@router.get("/{match_id}", response_model=ApiResponse[MatchResponse])
def get_match(
    match_id: uuid.UUID,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[MatchResponse]:
    service = MatchService(session)
    match = service.get_organizer_match(match_id, organizer_token, user)
    return ApiResponse(data=service.to_match_response(match))


@router.patch("/{match_id}", response_model=ApiResponse[MatchResponse])
def update_match_state(
    match_id: uuid.UUID,
    payload: MatchStateUpdate,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[MatchResponse]:
    return ApiResponse(
        data=MatchService(session).update_match_state(match_id, organizer_token, payload, user)
    )


@router.post(
    "/{match_id}/processing-jobs",
    response_model=ApiResponse[ProcessingJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_processing_job(
    match_id: uuid.UUID,
    session: DatabaseSession,
    user: OptionalUser,
    video: VideoUpload,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[ProcessingJobResponse]:
    MatchService(session).get_organizer_match(match_id, organizer_token, user)
    settings = get_settings()
    storage = LocalVideoStorage(settings.video_storage_path)
    stored = storage.store(
        video.file,
        original_filename=video.filename or "",
        media_type=video.content_type or "",
        max_size_bytes=settings.max_video_upload_size,
    )
    try:
        job = ProcessingService(session).create_job(
            match_id=match_id,
            organizer_token=organizer_token,
            user=user,
            source_reference=stored.reference,
            source_media_type=stored.media_type,
            source_size_bytes=stored.size_bytes,
            provider=settings.analytics_provider,
        )
    except Exception:
        storage.delete(stored.reference)
        raise
    finally:
        await video.close()
    return ApiResponse(data=job)


@router.get(
    "/{match_id}/processing-jobs",
    response_model=ApiResponse[list[ProcessingJobResponse]],
)
def list_processing_jobs(
    match_id: uuid.UUID,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[list[ProcessingJobResponse]]:
    return ApiResponse(data=ProcessingService(session).list_jobs(match_id, organizer_token, user))


@router.post(
    "/{match_id}/join-token",
    response_model=ApiResponse[JoinTokenResponse],
    status_code=status.HTTP_201_CREATED,
)
def rotate_join_token(
    match_id: uuid.UUID,
    payload: JoinTokenCreate,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[JoinTokenResponse]:
    token, expires_at = MatchService(session).rotate_join_token(
        match_id, organizer_token, payload.expires_at, user
    )
    return ApiResponse(data=JoinTokenResponse(token=token, expires_at=expires_at))


@router.get(
    "/{match_id}/assignments",
    response_model=ApiResponse[list[AssignmentResponse]],
)
def list_assignments(
    match_id: uuid.UUID,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[list[AssignmentResponse]]:
    return ApiResponse(data=MatchService(session).list_assignments(match_id, organizer_token, user))


@router.patch(
    "/{match_id}/assignments/{assignment_id}",
    response_model=ApiResponse[AssignmentResponse],
)
def correct_assignment(
    match_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: AssignmentCorrection,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[AssignmentResponse]:
    return ApiResponse(
        data=MatchService(session).correct_assignment(
            match_id, assignment_id, organizer_token, payload, user
        )
    )


@router.post(
    "/{match_id}/assignments/{assignment_id}/change-jersey",
    response_model=ApiResponse[AssignmentResponse],
    status_code=status.HTTP_201_CREATED,
)
def change_jersey(
    match_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: JerseyChange,
    session: DatabaseSession,
    user: OptionalUser,
    organizer_token: OrganizerTokenHeader = None,
) -> ApiResponse[AssignmentResponse]:
    return ApiResponse(
        data=MatchService(session).change_jersey(
            match_id, assignment_id, organizer_token, payload, user
        )
    )
