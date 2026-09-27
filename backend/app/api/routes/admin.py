import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.models.domain import User
from app.schemas.admin import (
    AdminDashboardResponse,
    HighlightUpdate,
    HighlightWrite,
    UserRoleUpdate,
)
from app.schemas.auth import UserResponse
from app.schemas.common import ApiResponse
from app.schemas.platform import (
    MatchListItem,
    PageResponse,
    PlatformHighlightResponse,
    PlayerDirectoryItem,
    TeamDirectoryItem,
)
from app.schemas.processing import ProcessingJobResponse
from app.services.admin import AdminService
from app.services.platform import PlatformService

router = APIRouter(prefix="/admin", tags=["admin"])
DatabaseSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_admin)]
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
JobStatus = Literal["queued", "processing", "completed", "failed", "cancelled"]


@router.get("/dashboard", response_model=ApiResponse[AdminDashboardResponse])
def admin_dashboard(
    session: DatabaseSession,
    _: AdminUser,
) -> ApiResponse[AdminDashboardResponse]:
    return ApiResponse(data=AdminService(session).dashboard())


@router.get("/users", response_model=ApiResponse[PageResponse[UserResponse]])
def admin_users(
    session: DatabaseSession,
    _: AdminUser,
    q: SearchQuery = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PageResponse[UserResponse]]:
    return ApiResponse(
        data=AdminService(session).list_users(query=q, page=page, page_size=page_size)
    )


@router.patch("/users/{user_id}", response_model=ApiResponse[UserResponse])
def admin_update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    session: DatabaseSession,
    _: AdminUser,
) -> ApiResponse[UserResponse]:
    return ApiResponse(data=AdminService(session).update_user_role(user_id, payload))


@router.get("/matches", response_model=ApiResponse[PageResponse[MatchListItem]])
def admin_matches(
    session: DatabaseSession,
    _: AdminUser,
    q: SearchQuery = None,
    status: MatchStatus | None = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PageResponse[MatchListItem]]:
    return ApiResponse(
        data=PlatformService(session).list_matches(
            query=q,
            status=status,
            team_id=None,
            date_from=None,
            date_to=None,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/players", response_model=ApiResponse[PageResponse[PlayerDirectoryItem]])
def admin_players(
    session: DatabaseSession,
    _: AdminUser,
    q: SearchQuery = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PageResponse[PlayerDirectoryItem]]:
    return ApiResponse(
        data=PlatformService(session).list_players(
            query=q,
            team_id=None,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/teams", response_model=ApiResponse[PageResponse[TeamDirectoryItem]])
def admin_teams(
    session: DatabaseSession,
    _: AdminUser,
    q: SearchQuery = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PageResponse[TeamDirectoryItem]]:
    return ApiResponse(
        data=PlatformService(session).list_teams(query=q, page=page, page_size=page_size)
    )


@router.get("/jobs", response_model=ApiResponse[PageResponse[ProcessingJobResponse]])
def admin_jobs(
    session: DatabaseSession,
    _: AdminUser,
    status: JobStatus | None = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PageResponse[ProcessingJobResponse]]:
    return ApiResponse(
        data=AdminService(session).list_jobs(
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=ApiResponse[ProcessingJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def admin_retry_job(
    job_id: uuid.UUID,
    session: DatabaseSession,
    admin: AdminUser,
) -> ApiResponse[ProcessingJobResponse]:
    return ApiResponse(data=AdminService(session).retry_job(job_id, admin))


@router.get("/highlights", response_model=ApiResponse[PageResponse[PlatformHighlightResponse]])
def admin_highlights(
    session: DatabaseSession,
    _: AdminUser,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PageResponse[PlatformHighlightResponse]]:
    return ApiResponse(
        data=PlatformService(session).list_highlights(
            match_id=None,
            player_id=None,
            highlight_type=None,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/highlights",
    response_model=ApiResponse[PlatformHighlightResponse],
    status_code=status.HTTP_201_CREATED,
)
def admin_create_highlight(
    payload: HighlightWrite,
    session: DatabaseSession,
    _: AdminUser,
) -> ApiResponse[PlatformHighlightResponse]:
    return ApiResponse(data=AdminService(session).create_highlight(payload))


@router.patch("/highlights/{highlight_id}", response_model=ApiResponse[PlatformHighlightResponse])
def admin_update_highlight(
    highlight_id: uuid.UUID,
    payload: HighlightUpdate,
    session: DatabaseSession,
    _: AdminUser,
) -> ApiResponse[PlatformHighlightResponse]:
    return ApiResponse(data=AdminService(session).update_highlight(highlight_id, payload))


@router.delete("/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_highlight(
    highlight_id: uuid.UUID,
    session: DatabaseSession,
    _: AdminUser,
) -> None:
    AdminService(session).delete_highlight(highlight_id)
