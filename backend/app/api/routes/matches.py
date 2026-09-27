import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.core.database import get_db
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
from app.services.matches import MatchService

router = APIRouter(prefix="/matches", tags=["matches"])
DatabaseSession = Annotated[Session, Depends(get_db)]
OrganizerToken = Annotated[str, Header(alias="X-Organizer-Token")]


@router.post(
    "",
    response_model=ApiResponse[MatchCreatedResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_match(
    payload: MatchCreate, session: DatabaseSession
) -> ApiResponse[MatchCreatedResponse]:
    return ApiResponse(data=MatchService(session).create_match(payload))


@router.get("/{match_id}", response_model=ApiResponse[MatchResponse])
def get_match(
    match_id: uuid.UUID,
    session: DatabaseSession,
    organizer_token: OrganizerToken,
) -> ApiResponse[MatchResponse]:
    service = MatchService(session)
    match = service.get_organizer_match(match_id, organizer_token)
    return ApiResponse(data=service.to_match_response(match))


@router.patch("/{match_id}", response_model=ApiResponse[MatchResponse])
def update_match_state(
    match_id: uuid.UUID,
    payload: MatchStateUpdate,
    session: DatabaseSession,
    organizer_token: OrganizerToken,
) -> ApiResponse[MatchResponse]:
    return ApiResponse(
        data=MatchService(session).update_match_state(match_id, organizer_token, payload)
    )


@router.post(
    "/{match_id}/join-token",
    response_model=ApiResponse[JoinTokenResponse],
    status_code=status.HTTP_201_CREATED,
)
def rotate_join_token(
    match_id: uuid.UUID,
    payload: JoinTokenCreate,
    session: DatabaseSession,
    organizer_token: OrganizerToken,
) -> ApiResponse[JoinTokenResponse]:
    token, expires_at = MatchService(session).rotate_join_token(
        match_id, organizer_token, payload.expires_at
    )
    return ApiResponse(data=JoinTokenResponse(token=token, expires_at=expires_at))


@router.get(
    "/{match_id}/assignments",
    response_model=ApiResponse[list[AssignmentResponse]],
)
def list_assignments(
    match_id: uuid.UUID,
    session: DatabaseSession,
    organizer_token: OrganizerToken,
) -> ApiResponse[list[AssignmentResponse]]:
    return ApiResponse(data=MatchService(session).list_assignments(match_id, organizer_token))


@router.patch(
    "/{match_id}/assignments/{assignment_id}",
    response_model=ApiResponse[AssignmentResponse],
)
def correct_assignment(
    match_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: AssignmentCorrection,
    session: DatabaseSession,
    organizer_token: OrganizerToken,
) -> ApiResponse[AssignmentResponse]:
    return ApiResponse(
        data=MatchService(session).correct_assignment(
            match_id, assignment_id, organizer_token, payload
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
    organizer_token: OrganizerToken,
) -> ApiResponse[AssignmentResponse]:
    return ApiResponse(
        data=MatchService(session).change_jersey(match_id, assignment_id, organizer_token, payload)
    )
