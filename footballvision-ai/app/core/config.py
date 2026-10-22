from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass
class PitchConfig:
    mode: str = "hali_saha"
    length_m: float = 40.0
    width_m: float = 20.0
    goal_width_m: float = 3.0
    goal_depth_m: float = 1.0
    grid_rows: int = 3
    grid_cols: int = 3
    fine_grid_rows: int = 4
    fine_grid_cols: int = 6


@dataclass
class DetectionConfig:
    model: str = "yolo11n.pt"
    pitch_model: str = ""
    image_size: int = 1280
    confidence: float = 0.25
    ball_confidence: float = 0.12
    device: str = "auto"
    player_classes: tuple[str, ...] = ("player", "person", "goalkeeper")
    keeper_classes: tuple[str, ...] = ("goalkeeper",)
    referee_classes: tuple[str, ...] = ("referee",)
    ball_classes: tuple[str, ...] = ("ball", "sports ball", "football")


@dataclass
class TrackingConfig:
    tracker: str = "bytetrack"
    lost_track_buffer: int = 30
    match_threshold: float = 0.55
    min_iou: float = 0.3
    ball_max_gap_frames: int = 12
    reid_hist_weight: float = 0.45
    reid_motion_weight: float = 0.35
    reid_color_weight: float = 0.20
    reid_max_distance_m: float = 6.0
    max_speed_kmh: float = 36.0
    sprint_kmh: float = 18.0
    standing_kmh: float = 1.2


@dataclass
class EventConfig:
    possession_radius_m: float = 1.6
    possession_min_frames: int = 4
    pass_min_distance_m: float = 2.0
    pass_max_time_s: float = 3.5
    pass_min_time_s: float = 0.12
    shot_min_speed_kmh: float = 28.0
    shot_goal_align: float = 0.35
    shot_min_frames: int = 3
    goal_min_frames: int = 2
    dribble_min_distance_m: float = 3.0
    tackle_radius_m: float = 1.8
    key_pass_shot_window_s: float = 8.0
    set_piece_stop_s: float = 2.2


@dataclass
class AppConfig:
    pitch: PitchConfig = field(default_factory=PitchConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    events: EventConfig = field(default_factory=EventConfig)
    home_name: str = "Home"
    away_name: str = "Away"
    output_fps_cap: int = 30
    highlight_pre_s: float = 3.0
    highlight_post_s: float = 3.0
    sqlite_path: str = "var/footballvision.sqlite"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: str = "var/jobs"
    camera_mode: str = "fixed"
    compensate_camera: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_hali_saha(self) -> bool:
        return self.pitch.mode in {"hali_saha", "futsal", "5v5"}


def load_config(path: str | Path | None = None) -> AppConfig:
    data: dict[str, Any] = {}
    if path is not None:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError("config.yaml must contain a mapping")
        data = payload
    pitch = data.get("pitch", {})
    detection = data.get("detection", {})
    tracking = data.get("tracking", {})
    events = data.get("events", {})
    return AppConfig(
        pitch=PitchConfig(
            mode=str(pitch.get("mode", "hali_saha")),
            length_m=float(pitch.get("length_m", 40.0)),
            width_m=float(pitch.get("width_m", 20.0)),
            goal_width_m=float(pitch.get("goal_width_m", 3.0)),
            goal_depth_m=float(pitch.get("goal_depth_m", 1.0)),
            grid_rows=int(pitch.get("grid_rows", 3)),
            grid_cols=int(pitch.get("grid_cols", 3)),
            fine_grid_rows=int(pitch.get("fine_grid_rows", 4)),
            fine_grid_cols=int(pitch.get("fine_grid_cols", 6)),
        ),
        detection=DetectionConfig(
            model=str(detection.get("model", "yolo11n.pt")),
            pitch_model=str(detection.get("pitch_model", "")),
            image_size=int(detection.get("image_size", 1280)),
            confidence=float(detection.get("confidence", 0.25)),
            ball_confidence=float(detection.get("ball_confidence", 0.12)),
            device=str(detection.get("device", "auto")),
            player_classes=tuple(detection.get("player_classes", ["player", "person", "goalkeeper"])),
            keeper_classes=tuple(detection.get("keeper_classes", ["goalkeeper"])),
            referee_classes=tuple(detection.get("referee_classes", ["referee"])),
            ball_classes=tuple(detection.get("ball_classes", ["ball", "sports ball", "football"])),
        ),
        tracking=TrackingConfig(
            tracker=str(tracking.get("tracker", "bytetrack")),
            lost_track_buffer=int(tracking.get("lost_track_buffer", 30)),
            match_threshold=float(tracking.get("match_threshold", 0.55)),
            min_iou=float(tracking.get("min_iou", 0.3)),
            ball_max_gap_frames=int(tracking.get("ball_max_gap_frames", 12)),
            reid_hist_weight=float(tracking.get("reid_hist_weight", 0.45)),
            reid_motion_weight=float(tracking.get("reid_motion_weight", 0.35)),
            reid_color_weight=float(tracking.get("reid_color_weight", 0.20)),
            reid_max_distance_m=float(tracking.get("reid_max_distance_m", 6.0)),
            max_speed_kmh=float(tracking.get("max_speed_kmh", 36.0)),
            sprint_kmh=float(tracking.get("sprint_kmh", 18.0)),
            standing_kmh=float(tracking.get("standing_kmh", 1.2)),
        ),
        events=EventConfig(
            possession_radius_m=float(events.get("possession_radius_m", 1.6)),
            possession_min_frames=int(events.get("possession_min_frames", 4)),
            pass_min_distance_m=float(events.get("pass_min_distance_m", 2.0)),
            pass_max_time_s=float(events.get("pass_max_time_s", 3.5)),
            pass_min_time_s=float(events.get("pass_min_time_s", 0.12)),
            shot_min_speed_kmh=float(events.get("shot_min_speed_kmh", 28.0)),
            shot_goal_align=float(events.get("shot_goal_align", 0.35)),
            shot_min_frames=int(events.get("shot_min_frames", 3)),
            goal_min_frames=int(events.get("goal_min_frames", 2)),
            dribble_min_distance_m=float(events.get("dribble_min_distance_m", 3.0)),
            tackle_radius_m=float(events.get("tackle_radius_m", 1.8)),
            key_pass_shot_window_s=float(events.get("key_pass_shot_window_s", 8.0)),
            set_piece_stop_s=float(events.get("set_piece_stop_s", 2.2)),
        ),
        home_name=str(data.get("home_name", "Home")),
        away_name=str(data.get("away_name", "Away")),
        output_fps_cap=int(data.get("output_fps_cap", 30)),
        highlight_pre_s=float(data.get("highlight_pre_s", 3.0)),
        highlight_post_s=float(data.get("highlight_post_s", 3.0)),
        sqlite_path=str(
            os.environ.get("FOOTBALLVISION_SQLITE", data.get("sqlite_path", "var/footballvision.sqlite"))
        ),
        redis_url=str(os.environ.get("FOOTBALLVISION_REDIS", data.get("redis_url", "redis://localhost:6379/0"))),
        storage_dir=str(os.environ.get("FOOTBALLVISION_STORAGE", data.get("storage_dir", "var/jobs"))),
        camera_mode=str(data.get("camera_mode", "fixed")),
        compensate_camera=bool(data.get("compensate_camera", False)),
        raw=data,
    )
