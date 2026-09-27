import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.processing import ProcessingStatus


class CalibrationMetadata(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    source_frame_width: int = Field(gt=0)
    source_frame_height: int = Field(gt=0)
    pitch_length_m: float | None = Field(default=None, gt=0)
    pitch_width_m: float | None = Field(default=None, gt=0)
    transform_metadata: dict[
        str,
        float | int | str | bool | list[float],
    ] = Field(default_factory=dict)


class AnalyticsMetricsIngest(BaseModel):
    rating: float | None = Field(default=None, ge=0, le=10)
    distance_m: float | None = Field(default=None, ge=0)
    avg_speed_kmh: float | None = Field(default=None, ge=0)
    max_speed_kmh: float | None = Field(default=None, ge=0)
    sprint_count: int | None = Field(default=None, ge=0)
    active_seconds: int | None = Field(default=None, ge=0)
    activity_count: int | None = Field(default=None, ge=0)
    peak_speed_at_ms: int | None = Field(default=None, ge=0)


class PositionSampleIngest(BaseModel):
    timestamp_ms: int = Field(ge=0)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class IntensityBucketIngest(BaseModel):
    from_minute: int = Field(ge=0)
    to_minute: int = Field(gt=0)
    intensity: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_interval(self) -> "IntensityBucketIngest":
        if self.to_minute <= self.from_minute:
            raise ValueError("to_minute must be after from_minute")
        return self


class AnalyticsEventIngest(BaseModel):
    event_type: Literal[
        "sprint",
        "peak_speed",
        "high_intensity_period",
        "custom",
    ]
    timestamp_ms: int = Field(ge=0)
    speed_kmh: float | None = Field(default=None, ge=0)
    title: str = Field(min_length=1, max_length=140)


class TrackMappingIngest(BaseModel):
    provider_track_id: str = Field(min_length=1, max_length=120)
    mapping_status: Literal["mapped", "unresolved"]
    player_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    observed_jersey: int | None = Field(default=None, ge=0, le=99)

    @model_validator(mode="after")
    def validate_mapping(self) -> "TrackMappingIngest":
        has_identity = self.player_id is not None or self.team_id is not None
        if self.mapping_status == "unresolved" and has_identity:
            raise ValueError("Unresolved tracks cannot contain player identity")
        if self.mapping_status == "mapped" and (self.player_id is None or self.team_id is None):
            raise ValueError("Mapped tracks require player_id and team_id")
        return self


class PlayerAnalyticsIngest(BaseModel):
    player_id: uuid.UUID
    team_id: uuid.UUID
    provider_track_id: str | None = Field(default=None, min_length=1, max_length=120)
    metrics: AnalyticsMetricsIngest
    positions: list[PositionSampleIngest] = Field(default_factory=list)
    intensity: list[IntensityBucketIngest] = Field(
        default_factory=list,
        max_length=1000,
    )
    events: list[AnalyticsEventIngest] = Field(
        default_factory=list,
        max_length=2000,
    )
    track_mappings: list[TrackMappingIngest] = Field(
        default_factory=list,
        max_length=500,
    )
    calibration: CalibrationMetadata | None = None
    complete_job: bool = False


class AnalyticsIngestionResponse(BaseModel):
    batch_id: uuid.UUID
    duplicate: bool
    player_id: uuid.UUID
    position_count: int
    intensity_bucket_count: int
    event_count: int
    job_status: ProcessingStatus
