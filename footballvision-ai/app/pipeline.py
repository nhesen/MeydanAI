from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.analytics.heatmap import render_heatmap, team_tracks
from app.analytics.stats import build_player_stats, build_team_stats
from app.calibration.camera import CameraCompensator
from app.calibration.homography import PitchMapper, detect_visible_pitch
from app.calibration.zones import PitchZones
from app.core.config import AppConfig, load_config
from app.core.types import (
    BallSample,
    Detection,
    MatchResult,
    PlayerTrack,
    Role,
    TeamId,
    TrackSample,
)
from app.detection.yolo import FootballDetector
from app.events.detector import EventDetector
from app.highlights.clips import cut_highlights, cut_player_clips
from app.reports.exporters import export_tables
from app.reports.html_report import write_html_report
from app.render import annotate_frame, write_minimap_frame
from app.tracking.ball_tracker import BallTracker
from app.tracking.player_tracker import PlayerTracker
from app.tracking.reid import IdentityRepair
from app.tracking.teams import TeamAssigner, lab_median, torso_hist


Progress = Callable[[int, str], None]


def analyze_video(
    video_path: str | Path,
    output_dir: str | Path,
    config: AppConfig | None = None,
    *,
    calibration_points: list[tuple[float, float]] | None = None,
    progress: Progress | None = None,
) -> MatchResult:
    cfg = config or load_config()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = progress or (lambda _pct, _msg: None)
    report(2, "video açılır")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Video could not be decoded.")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    detector = FootballDetector(cfg)
    tracker = PlayerTracker(cfg)
    ball_tracker = BallTracker(cfg)
    teams = TeamAssigner()
    camera = CameraCompensator(enabled=cfg.compensate_camera or cfg.camera_mode == "broadcast")
    mapper: PitchMapper | None = None
    points = calibration_points or list(map(tuple, cfg.raw.get("calibration", {}).get("points", [])))
    annotated = out / "annotated_raw.mp4"
    minimap = out / "minimap_raw.mp4"
    writer = cv2.VideoWriter(str(annotated), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    radar = cv2.VideoWriter(str(minimap), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 360))
    tracks: dict[int, PlayerTrack] = {}
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            time_s = frame_index / fps
            if mapper is None:
                mapper = _init_mapper(frame, cfg, width, height, points)
            detections = _read_detections(detector, tracker, frame)
            camera.update(frame, [item.bbox.as_xyxy() for item in detections])
            people = [item for item in detections if item.role is not Role.BALL]
            for detection in people:
                if detection.track_id is None:
                    continue
                pixel = camera.warp_point(*detection.bbox.foot())
                world = mapper.to_world(*pixel) if mapper else None
                hist = torso_hist(frame, detection.bbox)
                feature = lab_median(frame, detection.bbox)
                teams.observe(detection.track_id, feature, detection.role)
                track = tracks.setdefault(
                    detection.track_id,
                    PlayerTrack(track_id=detection.track_id, role=detection.role),
                )
                if detection.role is Role.GOALKEEPER:
                    track.role = Role.GOALKEEPER
                track.team = teams.team(detection.track_id)
                track.samples.append(
                    TrackSample(
                        frame=frame_index,
                        time_s=time_s,
                        pixel=pixel,
                        bbox=detection.bbox,
                        world=world,
                        confidence=detection.confidence,
                        team=track.team,
                        role=track.role,
                        color_hist=hist,
                    )
                )
            if frame_index and frame_index % max(1, int(fps * 2)) == 0:
                teams.fit()
            ball = ball_tracker.update(
                detections,
                frame_index,
                time_s,
                lambda x, y, _m=mapper: None if _m is None else _m.to_world(*camera.warp_point(x, y)),
            )
            for track in tracks.values():
                if track.last and ball.world and track.last.world:
                    dist = (
                        (ball.world[0] - track.last.world[0]) ** 2
                        + (ball.world[1] - track.last.world[1]) ** 2
                    ) ** 0.5
                    track.last.with_ball = dist <= cfg.events.possession_radius_m
            annotate_frame(frame, tracks, ball, cfg)
            writer.write(frame)
            radar_frame = np.zeros((360, 640, 3), dtype=np.uint8)
            write_minimap_frame(radar_frame, tracks, ball, cfg)
            radar.write(radar_frame)
            frame_index += 1
            if frame_index % 25 == 0:
                report(min(80, 5 + int(70 * frame_index / max(cap.get(cv2.CAP_PROP_FRAME_COUNT), 1))), "izləmə")
    finally:
        cap.release()
        writer.release()
        radar.release()
    if not teams.centers:
        teams.fit()
    for track in tracks.values():
        track.team = teams.team(track.track_id)
        for sample in track.samples:
            sample.team = track.team
    report(82, "ID bərpası")
    tracks = IdentityRepair(cfg).merge(tracks)
    result = finalize_match(
        tracks,
        ball_tracker.samples,
        cfg,
        output_dir=out,
        video_path=Path(video_path),
        fps=fps,
        frame_count=frame_index,
        frame_width=width,
        frame_height=height,
        calibrated=bool(mapper and mapper.calibrated),
        annotated_video=annotated,
        minimap_video=minimap,
        progress=report,
    )
    return result


def analyze_observations(
    tracks: dict[int, PlayerTrack],
    ball: list[BallSample],
    config: AppConfig,
    output_dir: str | Path,
    *,
    fps: float = 25.0,
    frame_width: int = 1280,
    frame_height: int = 720,
    calibrated: bool = True,
    video_path: Path | None = None,
) -> MatchResult:
    return finalize_match(
        tracks,
        ball,
        config,
        output_dir=Path(output_dir),
        video_path=video_path,
        fps=fps,
        frame_count=max((sample.frame for sample in ball), default=0) + 1,
        frame_width=frame_width,
        frame_height=frame_height,
        calibrated=calibrated,
        annotated_video=None,
        minimap_video=None,
    )


def finalize_match(
    tracks: dict[int, PlayerTrack],
    ball: list[BallSample],
    config: AppConfig,
    *,
    output_dir: Path,
    video_path: Path | None,
    fps: float,
    frame_count: int,
    frame_width: int,
    frame_height: int,
    calibrated: bool,
    annotated_video: Path | None,
    minimap_video: Path | None,
    progress: Progress | None = None,
) -> MatchResult:
    report = progress or (lambda _pct, _msg: None)
    zones = PitchZones.from_config(config)
    detector = EventDetector(config, zones)
    track_by_frame: dict[int, dict[int, PlayerTrack]] = {}
    for track in tracks.values():
        for sample in track.samples:
            snapshot = track_by_frame.setdefault(sample.frame, {})
            view = PlayerTrack(track.track_id, track.role, track.team, track.jersey, track.name)
            view.samples = [sample]
            snapshot[track.track_id] = view
    for sample in ball:
        live = {}
        for track_id, view in track_by_frame.get(sample.frame, {}).items():
            full = tracks[track_id]
            live[track_id] = PlayerTrack(full.track_id, full.role, full.team, full.jersey, full.name)
            live[track_id].samples = full.samples[: len([s for s in full.samples if s.frame <= sample.frame])]
        live_tracks = live or tracks
        detector.update(sample, live_tracks)
        last_live = live_tracks
        last_ball = sample
    if ball:
        detector.flush(last_ball, last_live)
    report(88, "statistikalar")
    players = build_player_stats(
        tracks,
        detector.events,
        detector.possession.state.player_frames,
        sum(detector.possession.state.team_frames.values()),
        config,
        zones,
    )
    teams = build_team_stats(players, detector.events)
    home_goals = next((item.goals for item in teams if item.team is TeamId.HOME), 0)
    away_goals = next((item.goals for item in teams if item.team is TeamId.AWAY), 0)
    heat_dir = output_dir / "heatmaps"
    heatmaps = {
        "home": render_heatmap(
            team_tracks(tracks, TeamId.HOME), heat_dir / "home.png", config.pitch.length_m, config.pitch.width_m, title="Home"
        ),
        "away": render_heatmap(
            team_tracks(tracks, TeamId.AWAY), heat_dir / "away.png", config.pitch.length_m, config.pitch.width_m, title="Away"
        ),
    }
    for player in players:
        heatmaps[str(player.track_id)] = render_heatmap(
            [tracks[player.track_id]],
            heat_dir / f"player_{player.track_id}.png",
            config.pitch.length_m,
            config.pitch.width_m,
            title=player.name or f"ID {player.track_id}",
        )
        player.heatmap_path = heatmaps[str(player.track_id)]
    highlights: list[dict[str, Any]] = []
    if video_path is not None:
        report(92, "highlight kliplər")
        highlights = cut_highlights(video_path, detector.events, output_dir / "highlights", config, fps)
        player_clips = cut_player_clips(video_path, tracks, output_dir / "highlights" / "players", config, fps)
        for player in players:
            player.highlight_path = player_clips.get(player.track_id)
    report(96, "hesabat")
    tables = export_tables(output_dir, players, teams, detector.events, detector.possession.percentages())
    _write_tracks_json(output_dir / "tracks.json", tracks, config)
    result = MatchResult(
        fps=fps,
        frame_count=frame_count,
        duration_s=round(frame_count / max(fps, 1e-6), 3),
        frame_width=frame_width,
        frame_height=frame_height,
        pitch_length_m=config.pitch.length_m,
        pitch_width_m=config.pitch.width_m,
        calibrated=calibrated,
        home_name=config.home_name,
        away_name=config.away_name,
        score=(home_goals, away_goals),
        players=players,
        teams=teams,
        events=detector.events,
        tracks=tracks,
        ball=ball,
        possession_timeline=detector.possession.state.timeline,
        heatmaps=heatmaps,
        highlights=highlights,
        annotated_video=None if annotated_video is None else str(annotated_video),
        minimap_video=None if minimap_video is None else str(minimap_video),
        report_html=None,
        report_pdf=None,
        extras={"tables": tables, "possession": detector.possession.percentages()},
    )
    result.report_html = write_html_report(output_dir / "match_report.html", result)
    return result


def _init_mapper(
    frame: np.ndarray,
    config: AppConfig,
    width: int,
    height: int,
    points: list[tuple[float, float]],
) -> PitchMapper:
    if len(points) == 4:
        return PitchMapper.from_points(points, config, width, height)
    detected = detect_visible_pitch(frame)
    if detected is None:
        mapper = PitchMapper(config.pitch.length_m, config.pitch.width_m, frame_width=width, frame_height=height)
        return mapper
    return PitchMapper.from_points(detected, config, width, height)


def _read_detections(
    detector: FootballDetector, tracker: PlayerTracker, frame: np.ndarray
) -> list[Detection]:
    try:
        detections = detector.detect(frame)
    except Exception:
        detections = []
    if detections and all(item.track_id is not None or item.role is Role.BALL for item in detections):
        return detections
    return tracker.update(detections, frame.shape[:2])


def _write_tracks_json(path: Path, tracks: dict[int, PlayerTrack], config: AppConfig) -> None:
    import json

    payload = {}
    for track_id, track in tracks.items():
        points = []
        for sample in track.samples:
            if sample.world is None:
                continue
            points.append(
                {
                    "timestamp_ms": int(sample.time_s * 1000),
                    "x": round(sample.world[0] / config.pitch.length_m, 4),
                    "y": round(sample.world[1] / config.pitch.width_m, 4),
                }
            )
        payload[str(track_id)] = {
            "team": track.team.value,
            "role": track.role.value,
            "jersey": track.jersey,
            "name": track.name,
            "positions": points[:: max(1, len(points) // 400)] if points else [],
        }
    path.write_text(json.dumps(payload), encoding="utf-8")


def apply_manual_corrections(tracks: dict[int, PlayerTrack], corrections: dict[str, Any]) -> None:
    for raw_id, payload in corrections.items():
        track = tracks.get(int(raw_id))
        if track is None:
            continue
        if "team" in payload:
            track.team = TeamId(payload["team"])
        if "jersey" in payload:
            track.jersey = payload["jersey"]
        if "name" in payload:
            track.name = payload["name"]
        if "role" in payload:
            track.role = Role(payload["role"])
