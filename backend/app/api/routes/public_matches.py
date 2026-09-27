import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.matches import MatchDetailResponse
from app.services.matches import MatchService

router = APIRouter(prefix="/public/matches", tags=["public-matches"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/{match_id}", response_model=ApiResponse[MatchDetailResponse])
def get_public_match_detail(
    match_id: uuid.UUID,
    session: DatabaseSession,
) -> ApiResponse[MatchDetailResponse]:
    return ApiResponse(data=MatchService(session).get_public_match_detail(match_id))
