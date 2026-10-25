import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
ReviewStatus = Literal["pending", "confirmed", "rejected"]


class UploadCalibrationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: Literal["manual", "automatic", "relative"] = "relative"
    pitch_mode: Literal["hali_saha", "11v11", "futsal"] = "hali_saha"
    camera_mode: Literal["fixed", "broadcast"] = "fixed"
    length_m: float = Field(default=40, ge=5, le=130)
    width_m: float = Field(default=20, ge=5, le=90)
    points: list[tuple[Unit, Unit]] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_geometry(self) -> "UploadCalibrationConfig":
        if self.mode == "automatic" and self.pitch_mode != "11v11":
            raise ValueError("Automatic landmark calibration requires an 11v11 pitch")
        if self.mode == "automatic" and not (
            90 <= self.length_m <= 120 and 45 <= self.width_m <= 90
        ):
            raise ValueError("Automatic calibration requires an actual 90-120 x 45-90 m pitch")
        if self.mode != "manual":
            if self.points:
                raise ValueError("Only manual calibration accepts pitch corners")
            return self
        if self.camera_mode != "fixed":
            raise ValueError("Manual calibration requires a fixed camera")
        if len(self.points) != 4:
            raise ValueError("Select exactly four pitch corners in perimeter order")
        crosses = []
        for index in range(4):
            a, b, c = (self.points[(index + step) % 4] for step in range(3))
            crosses.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
        if not (all(value > 1e-6 for value in crosses) or all(value < -1e-6 for value in crosses)):
            raise ValueError("Pitch corners must form a convex quadrilateral without crossing")
        area = (
            abs(
                sum(
                    self.points[index][0] * self.points[(index + 1) % 4][1]
                    - self.points[(index + 1) % 4][0] * self.points[index][1]
                    for index in range(4)
                )
            )
            / 2
        )
        if area < 0.005:
            raise ValueError("The selected pitch area is too small for reliable calibration")
        return self


class TrackEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_url: str | None = Field(
        default=None,
        max_length=300,
        pattern=r"^/api/v1/public/media/tracks/[a-z0-9]+(?:-[a-z0-9]+)*\.(?:jpg|png)$",
    )
    first_seen_ms: int | None = Field(default=None, ge=0)
    last_seen_ms: int | None = Field(default=None, ge=0)
    jersey_candidate: int | None = Field(default=None, ge=0, le=99)
    jersey_confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    ocr_observations: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_interval(self) -> "TrackEvidence":
        if (
            self.first_seen_ms is not None
            and self.last_seen_ms is not None
            and self.last_seen_ms < self.first_seen_ms
        ):
            raise ValueError("last_seen_ms must follow first_seen_ms")
        return self


class AnalysisQuality(BaseModel):
    job_id: uuid.UUID | None = None
    calibrated: bool = False
    source: str = "unavailable"
    physical_metrics_available: bool = False
    identity_mapping: Literal["estimated", "confirmed", "unavailable"] = "unavailable"
    pitch_length_m: float | None = None
    pitch_width_m: float | None = None
    calibration_coverage: float | None = None
    measured_seconds: float | None = None
    ball_observed_coverage: float | None = None
    sprint_threshold_kmh: float | None = None
    sprint_min_duration_s: float | None = None


class EventReviewUpdate(BaseModel):
    status: Literal["confirmed", "rejected"]


class IdentityReviewUpdate(BaseModel):
    player_id: uuid.UUID
    team_id: uuid.UUID
    display_name: str | None = Field(default=None, min_length=2, max_length=100)


class IdentityReviewItem(BaseModel):
    id: uuid.UUID
    provider_track_id: str
    player_id: uuid.UUID | None
    team_id: uuid.UUID | None
    display_name: str | None
    jersey_number: int | None
    review_status: Literal["estimated", "confirmed"]
    evidence: TrackEvidence | None = None
    can_rename: bool = False


class EventReviewItem(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    team_id: uuid.UUID
    event_type: str
    timestamp_ms: int
    title: str
    review_status: ReviewStatus = "pending"
    video_url: str | None = None


class AnalysisReviewResponse(BaseModel):
    job_id: uuid.UUID | None
    status: str | None
    calibration_config: UploadCalibrationConfig | None
    analysis_quality: AnalysisQuality
    mappings: list[IdentityReviewItem]
    events: list[EventReviewItem]
