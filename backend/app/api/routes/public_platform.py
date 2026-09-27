import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.platform import (
    AnalyticsLeaderboardsResponse,
    DashboardResponse,
    GlobalPlayerProfile,
    HighlightType,
    MatchListItem,
    PageResponse,
    PlatformHighlightResponse,
    PlayerDirectoryItem,
    TeamDetailResponse,
    TeamDirectoryItem,
)
from app.services.platform import PlatformService

router = APIRouter(prefix="/public", tags=["public-platform"])
DatabaseSession = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=50)]
SearchQuery = Annotated[str | None, Query(min_length=1, max_length=100)]
MatchStatus = Literal[
    "scheduled",
    "live",
    "processing",
    "completed",
    "failed",
    "cancelled",
]


@router.get("/dashboard", response_model=ApiResponse[DashboardResponse])
def get_dashboard(session: DatabaseSession) -> ApiResponse[DashboardResponse]:
    return ApiResponse(data=PlatformService(session).dashboard())


@router.get(
    "/matches",
    response_model=ApiResponse[PageResponse[MatchListItem]],
)
def list_matches(
    session: DatabaseSession,
    q: SearchQuery = None,
    status: MatchStatus | None = None,
    team_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Page = 1,
    page_size: PageSize = 12,
) -> ApiResponse[PageResponse[MatchListItem]]:
    return ApiResponse(
        data=PlatformService(session).list_matches(
            query=q,
            status=status,
            team_id=team_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/players",
    response_model=ApiResponse[PageResponse[PlayerDirectoryItem]],
)
def list_players(
    session: DatabaseSession,
    q: SearchQuery = None,
    team_id: uuid.UUID | None = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PageResponse[PlayerDirectoryItem]]:
    return ApiResponse(
        data=PlatformService(session).list_players(
            query=q,
            team_id=team_id,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/players/{player_id}",
    response_model=ApiResponse[GlobalPlayerProfile],
)
def get_player(
    player_id: uuid.UUID,
    session: DatabaseSession,
) -> ApiResponse[GlobalPlayerProfile]:
    return ApiResponse(data=PlatformService(session).get_player(player_id))


@router.get(
    "/teams",
    response_model=ApiResponse[PageResponse[TeamDirectoryItem]],
)
def list_teams(
    session: DatabaseSession,
    q: SearchQuery = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PageResponse[TeamDirectoryItem]]:
    return ApiResponse(
        data=PlatformService(session).list_teams(
            query=q,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/teams/{team_id}",
    response_model=ApiResponse[TeamDetailResponse],
)
def get_team(
    team_id: uuid.UUID,
    session: DatabaseSession,
) -> ApiResponse[TeamDetailResponse]:
    return ApiResponse(data=PlatformService(session).get_team(team_id))


@router.get(
    "/analytics/leaderboards",
    response_model=ApiResponse[AnalyticsLeaderboardsResponse],
)
def get_analytics_leaderboards(
    session: DatabaseSession,
    team_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    minimum_matches: Annotated[int, Query(ge=1, le=100)] = 1,
) -> ApiResponse[AnalyticsLeaderboardsResponse]:
    return ApiResponse(
        data=PlatformService(session).analytics_leaderboards(
            team_id=team_id,
            date_from=date_from,
            date_to=date_to,
            minimum_matches=minimum_matches,
        )
    )


@router.get(
    "/highlights",
    response_model=ApiResponse[PageResponse[PlatformHighlightResponse]],
)
def list_highlights(
    session: DatabaseSession,
    match_id: uuid.UUID | None = None,
    player_id: uuid.UUID | None = None,
    highlight_type: HighlightType | None = None,
    page: Page = 1,
    page_size: PageSize = 12,
) -> ApiResponse[PageResponse[PlatformHighlightResponse]]:
    return ApiResponse(
        data=PlatformService(session).list_highlights(
            match_id=match_id,
            player_id=player_id,
            highlight_type=highlight_type,
            page=page,
            page_size=page_size,
        )
    )
