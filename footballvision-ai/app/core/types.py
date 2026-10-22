from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    PLAYER = "player"
    GOALKEEPER = "goalkeeper"
    REFEREE = "referee"
    BALL = "ball"
    UNKNOWN = "unknown"


class TeamId(str, Enum):
    HOME = "home"
    AWAY = "away"
    UNKNOWN = "unknown"


class EventType(str, Enum):
    PASS = "pass"
    SUCCESSFUL_PASS = "successful_pass"
    FAILED_PASS = "failed_pass"
    KEY_PASS = "key_pass"
    SHOT = "shot"
    SHOT_ON_TARGET = "shot_on_target"
    SHOT_OFF_TARGET = "shot_off_target"
    GOAL = "goal"
    ASSIST = "assist"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    TURNOVER = "turnover"
    BALL_RECOVERY = "ball_recovery"
    DRIBBLE = "dribble"
    SAVE = "save"
    CORNER = "corner"
    FREE_KICK = "free_kick"
    PENALTY = "penalty"


@dataclass
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    def foot(self) -> tuple[float, float]:
        return self.cx, self.y2

    def area(self) -> float:
        return self.width * self.height

    def iou(self, other: BBox) -> float:
        ix1, iy1 = max(self.x1, other.x1), max(self.y1, other.y1)
        ix2, iy2 = min(self.x2, other.x2), min(self.y2, other.y2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        union = self.area() + other.area() - inter
        return inter / union if union > 0 else 0.0

    def as_xyxy(self) -> tuple[float, float, float, float]:
        return self.x1, self.y1, self.x2, self.y2


@dataclass
class Detection:
    bbox: BBox
    confidence: float
    role: Role
    track_id: int | None = None
    team: TeamId = TeamId.UNKNOWN
    class_name: str = ""


@dataclass
class TrackSample:
    frame: int
    time_s: float
    pixel: tuple[float, float]
    bbox: BBox
    world: tuple[float, float] | None
    confidence: float
    team: TeamId
    role: Role
    color_hist: list[float] | None = None
    with_ball: bool = False
    speed_mps: float | None = None


@dataclass
class PlayerTrack:
    track_id: int
    role: Role
    team: TeamId = TeamId.UNKNOWN
    jersey: int | None = None
    name: str | None = None
    samples: list[TrackSample] = field(default_factory=list)
    merged_from: list[int] = field(default_factory=list)

    @property
    def last(self) -> TrackSample | None:
        return self.samples[-1] if self.samples else None


@dataclass
class BallSample:
    frame: int
    time_s: float
    pixel: tuple[float, float] | None
    world: tuple[float, float] | None
    confidence: float
    interpolated: bool = False
    velocity_mps: tuple[float, float] | None = None


@dataclass
class MatchEvent:
    event_type: EventType
    time_s: float
    frame: int
    player_id: int | None
    team: TeamId | None
    related_player_id: int | None = None
    x: float | None = None
    y: float | None = None
    confidence: float = 0.5
    extra: dict[str, Any] = field(default_factory=dict)
    clip_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        import json

        return {
            "event_type": self.event_type.value,
            "time_s": round(self.time_s, 3),
            "frame": self.frame,
            "player_id": self.player_id,
            "team": None if self.team is None else self.team.value,
            "related_player_id": self.related_player_id,
            "x": None if self.x is None else round(self.x, 3),
            "y": None if self.y is None else round(self.y, 3),
            "confidence": round(self.confidence, 3),
            "clip_path": self.clip_path,
            "extra": json.dumps(self.extra, ensure_ascii=True),
        }


@dataclass
class PlayerStats:
    track_id: int
    team: TeamId
    role: Role
    name: str | None
    jersey: int | None
    distance_m: float | None
    avg_speed_kmh: float | None
    max_speed_kmh: float | None
    sprint_count: int
    active_seconds: float
    on_ball_seconds: float
    off_ball_seconds: float
    possession_pct: float
    passes: int
    successful_passes: int
    failed_passes: int
    pass_accuracy: float | None
    key_passes: int
    assists: int
    shots: int
    shots_on_target: int
    goals: int
    tackles: int
    interceptions: int
    turnovers: int
    recoveries: int
    dribbles: int
    saves: int
    zone_activity: dict[str, float]
    rating: float
    mvp_score: float
    heatmap_path: str | None = None
    highlight_path: str | None = None


@dataclass
class TeamStats:
    team: TeamId
    possession_pct: float
    passes: int
    pass_accuracy: float | None
    shots: int
    shots_on_target: int
    goals: int
    tackles: int
    interceptions: int
    corners: int
    distance_m: float | None


@dataclass
class MatchResult:
    fps: float
    frame_count: int
    duration_s: float
    frame_width: int
    frame_height: int
    pitch_length_m: float
    pitch_width_m: float
    calibrated: bool
    home_name: str
    away_name: str
    score: tuple[int, int]
    players: list[PlayerStats]
    teams: list[TeamStats]
    events: list[MatchEvent]
    tracks: dict[int, PlayerTrack]
    ball: list[BallSample]
    possession_timeline: list[dict[str, Any]]
    heatmaps: dict[str, str]
    highlights: list[dict[str, Any]]
    annotated_video: str | None
    minimap_video: str | None
    report_html: str | None
    report_pdf: str | None
    extras: dict[str, Any] = field(default_factory=dict)
