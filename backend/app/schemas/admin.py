import uuid

from pydantic import BaseModel, Field

from app.schemas.auth import UserRole
from app.schemas.platform import HighlightType, MatchListItem


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
