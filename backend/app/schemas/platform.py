import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.matches import MatchResponse, TeamResponse

HighlightType = Literal[
    "goal",
    "top_run",
    "sprint",
    "key_moment",
    "manual",
    "ai_detected",
]


class PageResponse[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class MatchListItem(BaseModel):
    match: MatchResponse
    has_analytics: bool


class PlayerPerformanceSummary(BaseModel):
    match_id: uuid.UUID
    match_title: str | None
    venue_name: str
    starts_at: datetime
    team: TeamResponse
    rating: float | None
    distance_m: float | None
    avg_speed_kmh: float | None
    max_speed_kmh: float | None
    sprint_count: int | None
    active_seconds: int | None


class PlayerDirectoryItem(BaseModel):
    id: uuid.UUID
    display_name: str
    is_temporary: bool
    recent_performance: PlayerPerformanceSummary | None


class GlobalPlayerProfile(BaseModel):
    id: uuid.UUID
    display_name: str
    is_temporary: bool
    recent_performances: list[PlayerPerformanceSummary]


class TeamDirectoryItem(BaseModel):
    id: uuid.UUID
    name: str
    player_count: int
    match_count: int


class TeamDetailResponse(BaseModel):
    team: TeamDirectoryItem
    players: list[PlayerDirectoryItem]
    recent_matches: list[MatchListItem]


class PlatformHighlightResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    match_title: str | None
    player_id: uuid.UUID | None
    player_name: str | None
    highlight_type: HighlightType
    timestamp_ms: int
    title: str
    video_url: str | None
    thumbnail_url: str | None
    duration_ms: int | None
    created_at: datetime


class QuickStatsResponse(BaseModel):
    total_matches: int
    completed_matches: int
    total_players: int
    total_teams: int
    processed_matches: int


class DashboardResponse(BaseModel):
    quick_stats: QuickStatsResponse
    recent_matches: list[MatchListItem]
    upcoming_matches: list[MatchListItem]
    processing_matches: list[MatchListItem]
    top_players: list["LeaderboardEntry"]
    latest_highlights: list[PlatformHighlightResponse]


class LeaderboardEntry(BaseModel):
    player_id: uuid.UUID
    display_name: str
    match_count: int
    value: float


class TeamAnalyticsSummary(BaseModel):
    team_id: uuid.UUID
    team_name: str
    match_count: int
    total_distance_m: float | None
    average_speed_kmh: float | None
    maximum_speed_kmh: float | None
    sprint_count: int | None


class AnalyticsLeaderboardsResponse(BaseModel):
    rating_leaders: list[LeaderboardEntry]
    distance_leaders: list[LeaderboardEntry]
    speed_leaders: list[LeaderboardEntry]
    sprint_leaders: list[LeaderboardEntry]
    team_analytics: list[TeamAnalyticsSummary]
    date_from: date | None
    date_to: date | None
