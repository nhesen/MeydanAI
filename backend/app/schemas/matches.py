import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MatchCreate(BaseModel):
    venue_name: str = Field(min_length=2, max_length=140)
    starts_at: datetime
    expected_ends_at: datetime | None = None
    title: str | None = Field(default=None, max_length=140)
    team_a_name: str = Field(min_length=1, max_length=100)
    team_b_name: str = Field(min_length=1, max_length=100)
    join_expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_match(self) -> "MatchCreate":
        if self.starts_at.tzinfo is None:
            raise ValueError("starts_at must include a timezone")
        if self.expected_ends_at is not None:
            if self.expected_ends_at.tzinfo is None:
                raise ValueError("expected_ends_at must include a timezone")
            if self.expected_ends_at <= self.starts_at:
                raise ValueError("expected_ends_at must be after starts_at")
        if self.join_expires_at is not None:
            if self.join_expires_at.tzinfo is None:
                raise ValueError("join_expires_at must include a timezone")
            if self.join_expires_at <= self.starts_at:
                raise ValueError("join_expires_at must be after starts_at")
        if self.team_a_name.strip().casefold() == self.team_b_name.strip().casefold():
            raise ValueError("Teams must be different")
        return self


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    side: str | None = None


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID
    team: TeamResponse
    player: PlayerResponse
    jersey_number: int
    started_at: datetime
    ended_at: datetime | None
    supersedes_id: uuid.UUID | None
    conflict_override: bool
    override_actor: str | None
    override_reason: str | None


class MatchResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    venue_name: str
    starts_at: datetime
    expected_ends_at: datetime | None
    ended_at: datetime | None
    home_score: int | None
    away_score: int | None
    status: str
    teams: list[TeamResponse]


class MatchStateUpdate(BaseModel):
    status: Literal["scheduled", "live", "processing", "completed", "failed", "cancelled"]
    home_score: int | None = Field(default=None, ge=0)
    away_score: int | None = Field(default=None, ge=0)
    ended_at: datetime | None = None


class JerseyHistoryResponse(BaseModel):
    assignment_id: uuid.UUID
    jersey_number: int
    started_at: datetime
    ended_at: datetime | None


class MatchPlayerResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    team: TeamResponse
    current_jersey: int | None
    jersey_history: list[JerseyHistoryResponse]
    rating: float | None = None
    distance_m: float | None = None
    sprint_count: int | None = None


class TeamStatsResponse(BaseModel):
    team_id: uuid.UUID
    total_distance_m: float | None = None
    average_speed_kmh: float | None = None
    maximum_speed_kmh: float | None = None
    sprint_count: int | None = None
    active_time_seconds: int | None = None


class TimelineEventResponse(BaseModel):
    id: str
    event_type: Literal[
        "goal",
        "substitution",
        "jersey_change",
        "high_intensity",
        "ai_moment",
        "custom",
    ]
    occurred_at: datetime
    minute: int | None
    title: str
    description: str | None
    player_id: uuid.UUID | None
    team_id: uuid.UUID | None


class HighlightResponse(BaseModel):
    id: uuid.UUID
    highlight_type: str
    title: str
    video_url: str | None
    thumbnail_url: str | None
    duration_seconds: int | None
    occurred_at: datetime | None
    player_id: uuid.UUID | None


class MatchDetailResponse(BaseModel):
    match: MatchResponse
    players: list[MatchPlayerResponse]
    team_stats: list[TeamStatsResponse] | None
    events: list[TimelineEventResponse]
    highlights: list[HighlightResponse]


class MatchCreatedResponse(BaseModel):
    match: MatchResponse
    join_token: str
    organizer_token: str


class JoinTokenCreate(BaseModel):
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_expiry(self) -> "JoinTokenCreate":
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return self


class JoinTokenResponse(BaseModel):
    token: str
    expires_at: datetime | None


class JoinContextResponse(BaseModel):
    match: MatchResponse
    players: list[PlayerResponse]


class AssignmentCreate(BaseModel):
    team_id: uuid.UUID
    player_id: uuid.UUID | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=100)
    jersey_number: int = Field(ge=0, le=99)

    @model_validator(mode="after")
    def validate_identity(self) -> "AssignmentCreate":
        if (self.player_id is None) == (self.display_name is None):
            raise ValueError("Provide exactly one of player_id or display_name")
        return self


class AssignmentCorrection(BaseModel):
    team_id: uuid.UUID | None = None
    jersey_number: int | None = Field(default=None, ge=0, le=99)
    effective_at: datetime | None = None
    close_only: bool = False
    override_conflict: bool = False
    override_reason: str | None = Field(default=None, min_length=5, max_length=500)
    override_actor: str | None = Field(default=None, min_length=2, max_length=100)

    @model_validator(mode="after")
    def validate_override(self) -> "AssignmentCorrection":
        if self.override_conflict and (not self.override_reason or not self.override_actor):
            raise ValueError("Override requires override_reason and override_actor")
        if not self.close_only and self.team_id is None and self.jersey_number is None:
            raise ValueError("Provide a correction or set close_only")
        return self


class JerseyChange(BaseModel):
    jersey_number: int = Field(ge=0, le=99)
    effective_at: datetime | None = None
    override_conflict: bool = False
    override_reason: str | None = Field(default=None, min_length=5, max_length=500)
    override_actor: str | None = Field(default=None, min_length=2, max_length=100)

    @model_validator(mode="after")
    def validate_override(self) -> "JerseyChange":
        if self.override_conflict and (not self.override_reason or not self.override_actor):
            raise ValueError("Override requires override_reason and override_actor")
        return self
