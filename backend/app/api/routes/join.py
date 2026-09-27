from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import rate_limit_join
from app.schemas.common import ApiResponse
from app.schemas.matches import AssignmentCreate, AssignmentResponse, JoinContextResponse
from app.services.matches import MatchService

router = APIRouter(prefix="/join", tags=["public-join"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/{token}", response_model=ApiResponse[JoinContextResponse])
def get_join_context(
    token: str,
    session: DatabaseSession,
    request: Request,
) -> ApiResponse[JoinContextResponse]:
    rate_limit_join(request)
    return ApiResponse(data=MatchService(session).get_join_context(token))


@router.post(
    "/{token}/assignments",
    response_model=ApiResponse[AssignmentResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    token: str,
    payload: AssignmentCreate,
    session: DatabaseSession,
    request: Request,
) -> ApiResponse[AssignmentResponse]:
    rate_limit_join(request)
    return ApiResponse(data=MatchService(session).join_match(token, payload))
