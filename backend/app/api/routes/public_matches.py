import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.services.recordings import match_recording
from app.schemas.common import ApiResponse
from app.schemas.matches import (
    MatchDetailResponse,
    PlayerAnalyticsDetailResponse,
    PlayerComparisonResponse,
)
from app.services.matches import MatchService

router = APIRouter(prefix="/public/matches", tags=["public-matches"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/{match_id}", response_model=ApiResponse[MatchDetailResponse])
def get_public_match_detail(
    match_id: uuid.UUID,
    session: DatabaseSession,
) -> ApiResponse[MatchDetailResponse]:
    return ApiResponse(data=MatchService(session).get_public_match_detail(match_id))


@router.get("/{match_id}/recording")
def get_match_recording(match_id: uuid.UUID, request: Request, session: DatabaseSession) -> FileResponse:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    path = match_recording(session, match_id, settings.video_storage_path)
    if path is None:
        raise HTTPException(status_code=404, detail="Match recording was not found.")
    return FileResponse(path, media_type="video/mp4", filename=path.name, content_disposition_type="inline")


@router.get(
    "/{match_id}/players/compare",
    response_model=ApiResponse[PlayerComparisonResponse],
)
def compare_match_players(
    match_id: uuid.UUID,
    left_player_id: uuid.UUID,
    right_player_id: uuid.UUID,
    session: DatabaseSession,
) -> ApiResponse[PlayerComparisonResponse]:
    return ApiResponse(
        data=MatchService(session).compare_players(
            match_id,
            left_player_id,
            right_player_id,
        )
    )


@router.get(
    "/{match_id}/players/{player_id}/analytics",
    response_model=ApiResponse[PlayerAnalyticsDetailResponse],
)
def get_player_analytics(
    match_id: uuid.UUID,
    player_id: uuid.UUID,
    session: DatabaseSession,
) -> ApiResponse[PlayerAnalyticsDetailResponse]:
    return ApiResponse(data=MatchService(session).get_player_analytics_detail(match_id, player_id))
