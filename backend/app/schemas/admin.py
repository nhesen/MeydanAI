import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.auth import UserResponse, UserRole
from app.schemas.platform import (
    HighlightType,
    MatchListItem,
    PageResponse,
    PlatformHighlightResponse,
    PlayerDirectoryItem,
    TeamDirectoryItem,
)
from app.schemas.processing import ProcessingJobResponse

AdminJobStatus = Literal["queued", "processing", "completed", "failed", "cancelled"]


class AdminDashboardResponse(BaseModel):
    total_matches: int
    total_users: int
    total_players: int
    total_teams: int
    failed_jobs: int
    active_jobs: int
    recent_matches: list[MatchListItem]


class UserRoleUpdate(BaseModel):
    role: UserRole


class HighlightWrite(BaseModel):
    match_id: uuid.UUID
    player_id: uuid.UUID | None = None
    highlight_type: HighlightType
    timestamp_ms: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=140)
    video_url: str | None = Field(default=None, max_length=1000)
    thumbnail_url: str | None = Field(default=None, max_length=1000)
    duration_ms: int | None = Field(default=None, gt=0)


class HighlightUpdate(BaseModel):
    player_id: uuid.UUID | None = None
    highlight_type: HighlightType | None = None
    timestamp_ms: int | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=140)
    video_url: str | None = Field(default=None, max_length=1000)
    thumbnail_url: str | None = Field(default=None, max_length=1000)
    duration_ms: int | None = Field(default=None, gt=0)


class AdminUserList(PageResponse[UserResponse]):
    pass


class AdminJobList(PageResponse[ProcessingJobResponse]):
    pass


class AdminHighlightList(PageResponse[PlatformHighlightResponse]):
    pass


class AdminMatchList(PageResponse[MatchListItem]):
    pass


class AdminPlayerList(PageResponse[PlayerDirectoryItem]):
    pass


class AdminTeamList(PageResponse[TeamDirectoryItem]):
    pass


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str
    created_at: datetime
    metadata: dict[str, object] | None = None
